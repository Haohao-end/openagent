import { audioToText, messageToAudio, textToAudio } from '@/services/audio'
import { Message } from '@arco-design/web-vue'
import { computed, ref } from 'vue'

export const useAudioToText = () => {
  // 1.定义自定义hooks所需数据
  const loading = ref(false)
  const text = ref('')

  // 2.定义语音转文本处理器
  const handleAudioToText = async (file: Blob) => {
    try {
      loading.value = true
      const resp = await audioToText(file)
      Message.success('语音转文本成功')
      text.value = resp.data.text
    } finally {
      loading.value = false
    }
  }

  return { loading, text, handleAudioToText }
}

export const useMessageToAudio = () => {
  // 1.定义hooks所需数据
  const pendingCount = ref(0)
  const loading = computed(() => pendingCount.value > 0)

  // 2.定义消息转音频处理器
  const handleMessageToAudio = async (
    message_id: string,
    onData: (event_response: Record<string, any>) => void,
  ) => {
    try {
      pendingCount.value += 1
      await messageToAudio(message_id, onData)
    } finally {
      pendingCount.value = Math.max(0, pendingCount.value - 1)
    }
  }

  return { loading, handleMessageToAudio }
}

export const useTextToAudio = () => {
  // 1.定义hooks所需数据
  const pendingCount = ref(0)
  const loading = computed(() => pendingCount.value > 0)

  // 2.定义文本转音频处理器
  const handleTextToAudio = async (
    message_id: string = '',
    text: string,
    onData: (event_response: Record<string, any>) => void,
  ) => {
    try {
      pendingCount.value += 1
      await textToAudio(message_id, text, onData)
    } finally {
      pendingCount.value = Math.max(0, pendingCount.value - 1)
    }
  }

  return { loading, handleTextToAudio }
}

type TtsRequestFn = (
  onData: (event_response: Record<string, any>) => void,
) => Promise<void>

// 全局单例播放器状态，确保整个应用只会有一个音频在播放
const audioElement = ref<HTMLAudioElement | null>(null)
const isAudioLoaded = ref(false)
const isPlaying = ref(false)
const activeMessageId = ref('')
const activeThoughtId = ref('')
const activeStreamType = ref<'message' | 'thought' | ''>('')
const playSessionId = ref(0)
const { loading: messageAudioLoading, handleMessageToAudio } = useMessageToAudio()
const { loading: thoughtAudioLoading, handleTextToAudio } = useTextToAudio()

const resetActiveState = () => {
  activeMessageId.value = ''
  activeThoughtId.value = ''
  activeStreamType.value = ''
}

const onAudioPlay = () => {
  isPlaying.value = true
}

const onAudioPause = () => {
  isPlaying.value = false
}

const onAudioEnded = () => {
  isPlaying.value = false
  resetActiveState()
}

const onAudioError = () => {
  isPlaying.value = false
  resetActiveState()
}

const clearAudioElement = () => {
  const audio = audioElement.value
  if (!audio) return

  audio.pause()
  audio.currentTime = 0
  audio.removeEventListener('play', onAudioPlay)
  audio.removeEventListener('pause', onAudioPause)
  audio.removeEventListener('ended', onAudioEnded)
  audio.removeEventListener('error', onAudioError)

  if (audio.src && audio.src.startsWith('blob:')) {
    URL.revokeObjectURL(audio.src)
  }

  audio.src = ''
  audioElement.value = null
}

const base64ToUint8Array = (base64Data: string) => {
  if (!base64Data) return null

  try {
    const binaryString = atob(base64Data)
    const uint8Array = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      uint8Array[i] = binaryString.charCodeAt(i)
    }
    return uint8Array
  } catch (_error: unknown) {
    return null
  }
}

const mergeChunks = (chunks: Uint8Array[]) => {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const merged = new Uint8Array(totalLength)
  let offset = 0

  chunks.forEach((chunk) => {
    merged.set(chunk, offset)
    offset += chunk.length
  })

  return merged
}

const collectAudioBuffer = async (sessionId: number, request: TtsRequestFn) => {
  const chunks: Uint8Array[] = []
  let hasStreamError = false

  try {
    await request((event_response) => {
      if (sessionId !== playSessionId.value) return

      const event = event_response?.event
      const data = event_response?.data

      if (event === 'tts_error') {
        hasStreamError = true
        return
      }

      if (event !== 'tts_message') return
      const chunk = base64ToUint8Array(data?.audio || '')
      if (chunk && chunk.byteLength > 0) {
        chunks.push(chunk)
      }
    })
  } catch (_error: unknown) {
    if (sessionId !== playSessionId.value) return null
    return null
  }

  if (sessionId !== playSessionId.value || hasStreamError || chunks.length === 0) {
    return null
  }

  return mergeChunks(chunks)
}

const playAudioBuffer = async (audioBuffer: Uint8Array, sessionId: number) => {
  if (sessionId !== playSessionId.value) return

  const audio = audioElement.value
  if (!audio) return

  const audioBlob = new Blob([audioBuffer], { type: 'audio/mpeg' })
  const audioUrl = URL.createObjectURL(audioBlob)

  if (sessionId !== playSessionId.value) {
    URL.revokeObjectURL(audioUrl)
    return
  }

  if (audio.src && audio.src.startsWith('blob:')) {
    URL.revokeObjectURL(audio.src)
  }

  audio.src = audioUrl
  audio.currentTime = 0

  try {
    await audio.play()
  } catch (_error: unknown) {
    if (sessionId !== playSessionId.value) return
    isPlaying.value = false
    resetActiveState()
  }
}

const consumeTtsStream = async (sessionId: number, request: TtsRequestFn) => {
  const audioBuffer = await collectAudioBuffer(sessionId, request)

  if (sessionId !== playSessionId.value) return
  isAudioLoaded.value = true

  if (!audioBuffer) {
    isPlaying.value = false
    resetActiveState()
    return
  }

  await playAudioBuffer(audioBuffer, sessionId)
}

const fetchMessageAudioStream = async (messageId: string, sessionId: number) => {
  await consumeTtsStream(sessionId, (onData) => handleMessageToAudio(messageId, onData))
}

const fetchThoughtAudioStream = async (messageId: string, text: string, sessionId: number) => {
  await consumeTtsStream(sessionId, (onData) => handleTextToAudio(messageId, text, onData))
}

const createAudioStream = async (
  messageId: string,
  streamType: 'message' | 'thought',
  thoughtId: string,
  fetcher: (sessionId: number) => Promise<void>,
  allowEmptyMessageId: boolean = false,
) => {
  if (!allowEmptyMessageId && !messageId) return

  stopAudioStream()
  const sessionId = playSessionId.value

  isAudioLoaded.value = false
  isPlaying.value = false
  activeMessageId.value = messageId
  activeThoughtId.value = thoughtId
  activeStreamType.value = streamType

  audioElement.value = new Audio()
  audioElement.value.addEventListener('play', onAudioPlay)
  audioElement.value.addEventListener('pause', onAudioPause)
  audioElement.value.addEventListener('ended', onAudioEnded)
  audioElement.value.addEventListener('error', onAudioError)

  await fetcher(sessionId)
}

const stopAudioStream = () => {
  playSessionId.value += 1
  clearAudioElement()
  isAudioLoaded.value = false
  isPlaying.value = false
  resetActiveState()
}

const startAudioStream = async (messageId: string) => {
  if (!messageId) return
  if (
    activeStreamType.value === 'message' &&
    activeMessageId.value === messageId &&
    (isPlaying.value || messageAudioLoading.value)
  ) {
    return
  }

  await createAudioStream(messageId, 'message', '', (sessionId) =>
    fetchMessageAudioStream(messageId, sessionId),
  )
}

const startThoughtAudioStream = async (messageId: string, thoughtId: string, text: string) => {
  const normalizedText = text.trim()
  if (!messageId || !thoughtId || !normalizedText) return
  if (
    activeStreamType.value === 'thought' &&
    activeThoughtId.value === thoughtId &&
    (isPlaying.value || thoughtAudioLoading.value)
  ) {
    return
  }

  await createAudioStream(messageId, 'thought', thoughtId, (sessionId) =>
    fetchThoughtAudioStream(messageId, normalizedText, sessionId),
  )
}

const startTextAudioStream = async (
  text: string,
  messageId: string = '',
  streamId: string = 'text-audio',
) => {
  const normalizedText = text.trim()
  if (!streamId || !normalizedText) return
  if (
    activeStreamType.value === 'thought' &&
    activeMessageId.value === messageId &&
    activeThoughtId.value === streamId &&
    (isPlaying.value || thoughtAudioLoading.value)
  ) {
    return
  }

  await createAudioStream(
    messageId,
    'thought',
    streamId,
    (sessionId) => fetchThoughtAudioStream(messageId, normalizedText, sessionId),
    true,
  )
}

export const useAudioPlayer = () => {
  return {
    isAudioLoaded,
    isPlaying,
    activeMessageId,
    activeThoughtId,
    activeStreamType,
    messageAudioLoading,
    thoughtAudioLoading,
    startAudioStream,
    startThoughtAudioStream,
    startTextAudioStream,
    stopAudioStream,
  }
}
