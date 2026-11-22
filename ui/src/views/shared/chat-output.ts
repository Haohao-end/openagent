const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg', '.tif', '.tiff', '.avif']
const MARKDOWN_IMAGE_URL_PATTERN = /!\[[^\]]*\]\((https?:\/\/[^\s)]+)\)/giu
const STRUCTURED_IMAGE_URL_PATTERN = /图片\s*\d+\s*:\s*(?:\n\s*)?URL\s*:\s*(https?:\/\/[^\s)]+)/giu
const RAW_IMAGE_URL_PATTERN = /https?:\/\/[^\s<>()]+?\.(?:png|jpg|jpeg|gif|webp|bmp|svg|tiff|tif|avif)(?:\?[^\s<>()]*)?/giu
const TRAILING_URL_PUNCTUATION = /[.,;)\]}]+$/u

export type ChatArtifact = {
  id?: string
  name: string
  url: string
  mime_type?: string
  extension?: string
  size?: number
  group_id?: string
  group_name?: string
}

export type ChatOutputPart =
  | {
    type: 'text'
    text: string
  }
  | ({
    type: 'image'
    url: string
    name?: string
    mime_type?: string
    extension?: string
    group_id?: string
    group_name?: string
  })
  | ({
    type: 'artifact'
    name: string
    url: string
    mime_type?: string
    extension?: string
    size?: number
    group_id?: string
    group_name?: string
  })

export type ChatImageGalleryGroup = {
  id: string
  title: string
  images: ChatArtifact[]
}

type MutableChatImageGalleryGroup = ChatImageGalleryGroup & {
  seenUrls: Set<string>
}

const cleanUrl = (value: unknown) => {
  return String(value || '').trim().replace(TRAILING_URL_PUNCTUATION, '')
}

const isImageUrl = (value: unknown) => {
  const url = cleanUrl(value)
  if (!url) return false
  try {
    const parsed = new URL(url)
    const pathname = parsed.pathname.toLowerCase()
    return IMAGE_EXTENSIONS.some(extension => pathname.endsWith(extension))
  } catch {
    return false
  }
}

export const normalizeChatArtifact = (value: unknown): ChatArtifact | null => {
  if (!value || typeof value !== 'object')
    return null

  const record = value as Record<string, unknown>
  const url = cleanUrl(record.url)
  if (!url)
    return null

  const path = String(record.path || '').trim()
  const pathName = path ? path.split('/').pop() || '' : ''
  const urlName = (() => {
    try {
      return new URL(url).pathname.split('/').pop() || ''
    } catch {
      return ''
    }
  })()
  const name = String(record.name || '').trim() || pathName || urlName || url

  const artifact: ChatArtifact = {
    name,
    url,
  }

  for (const key of ['id', 'mime_type', 'extension'] as const) {
    const fieldValue = String(record[key] || '').trim()
    if (fieldValue)
      artifact[key] = fieldValue
  }

  for (const key of ['group_id', 'group_name'] as const) {
    const fieldValue = String(record[key] || '').trim()
    if (fieldValue)
      artifact[key] = fieldValue
  }

  const size = Number(record.size)
  if (Number.isFinite(size) && size >= 0)
    artifact.size = Math.floor(size)

  return artifact
}

export const isImageArtifact = (artifact: ChatArtifact) => {
  const mimeType = String(artifact.mime_type || '').trim().toLowerCase()
  const extension = String(artifact.extension || '').trim().toLowerCase()
  if (mimeType.startsWith('image/'))
    return true
  if (extension) {
    const normalizedExtension = extension.startsWith('.') ? extension : `.${extension}`
    if (IMAGE_EXTENSIONS.includes(normalizedExtension))
      return true
  }
  return isImageUrl(artifact.url)
}

const buildImagePart = (url: string, options: Partial<ChatArtifact> = {}): ChatOutputPart => {
  return {
    type: 'image',
    url: cleanUrl(url),
    ...(options.name ? { name: options.name } : {}),
    ...(options.mime_type ? { mime_type: options.mime_type } : {}),
    ...(options.extension ? { extension: options.extension } : {}),
    ...(options.group_id ? { group_id: options.group_id } : {}),
    ...(options.group_name ? { group_name: options.group_name } : {}),
  }
}

const buildArtifactPart = (artifact: ChatArtifact): ChatOutputPart => {
  return {
    type: 'artifact',
    name: artifact.name,
    url: artifact.url,
    ...(artifact.mime_type ? { mime_type: artifact.mime_type } : {}),
    ...(artifact.extension ? { extension: artifact.extension } : {}),
    ...(typeof artifact.size === 'number' ? { size: artifact.size } : {}),
    ...(artifact.group_id ? { group_id: artifact.group_id } : {}),
    ...(artifact.group_name ? { group_name: artifact.group_name } : {}),
  }
}

const dedupeArtifacts = (artifacts: ChatArtifact[]) => {
  const artifactsByUrl = new Map<string, ChatArtifact>()
  for (const artifact of artifacts) {
    const previous = artifactsByUrl.get(artifact.url)
    if (!previous) {
      artifactsByUrl.set(artifact.url, artifact)
      continue
    }
    artifactsByUrl.set(artifact.url, {
      ...previous,
      ...artifact,
      id: previous.id || artifact.id,
      name: previous.name || artifact.name,
      mime_type: previous.mime_type || artifact.mime_type,
      extension: previous.extension || artifact.extension,
      size: previous.size ?? artifact.size,
      group_id: previous.group_id || artifact.group_id,
      group_name: previous.group_name || artifact.group_name,
    })
  }
  return [...artifactsByUrl.values()]
}

export function extractInlineImageUrls(answer: string, existingUrls: string[] = []) {
  const seenUrls = new Set(existingUrls.map(url => cleanUrl(url)).filter(Boolean))
  const imageUrls: string[] = []
  for (const pattern of [MARKDOWN_IMAGE_URL_PATTERN, STRUCTURED_IMAGE_URL_PATTERN, RAW_IMAGE_URL_PATTERN]) {
    for (const match of answer.matchAll(pattern)) {
      const url = cleanUrl(match[1] || match[0] || '')
      if (!url || seenUrls.has(url))
        continue
      seenUrls.add(url)
      imageUrls.push(url)
    }
  }
  return imageUrls
}

const collectInlineImageParts = (answer: string, existingUrls: Set<string>) => {
  const parts: ChatOutputPart[] = []
  for (const url of extractInlineImageUrls(answer, [...existingUrls]))
    parts.push(buildImagePart(url))
  return parts
}

export const buildChatOutputParts = (answer: string, artifacts: unknown[] = []): ChatOutputPart[] => {
  const normalizedAnswer = String(answer || '')
  const normalizedArtifacts = mergeChatArtifacts([], artifacts)
  const parts: ChatOutputPart[] = []

  if (normalizedAnswer.trim())
    parts.push({ type: 'text', text: normalizedAnswer })

  const imageUrls = new Set<string>()
  for (const artifact of normalizedArtifacts) {
    if (!isImageArtifact(artifact))
      continue
    imageUrls.add(artifact.url)
    parts.push(buildImagePart(artifact.url, artifact))
  }

  parts.push(...collectInlineImageParts(normalizedAnswer, imageUrls))

  for (const artifact of normalizedArtifacts) {
    if (isImageArtifact(artifact))
      continue
    parts.push(buildArtifactPart(artifact))
  }

  return parts
}

export const normalizeChatOutputParts = (value: unknown, fallbackAnswer: string, fallbackArtifacts: ChatArtifact[] = []) => {
  if (!Array.isArray(value) || value.length === 0)
    return buildChatOutputParts(fallbackAnswer, fallbackArtifacts)

  const parts = value
    .map((item) => {
      if (!item || typeof item !== 'object')
        return null

      const record = item as Record<string, unknown>
      const type = String(record.type || '').trim()
      if (type === 'text') {
        return {
          type: 'text',
          text: String(record.text || ''),
        } satisfies ChatOutputPart
      }
      if (type === 'image') {
        const url = cleanUrl(record.url)
        if (!url)
          return null
        return buildImagePart(url, {
          name: String(record.name || '').trim(),
          mime_type: String(record.mime_type || '').trim(),
          extension: String(record.extension || '').trim(),
          group_id: String(record.group_id || '').trim(),
          group_name: String(record.group_name || '').trim(),
        })
      }
      if (type === 'artifact') {
        const artifact = normalizeChatArtifact(record)
        if (!artifact)
          return null
        return buildArtifactPart(artifact)
      }
      return null
    })
    .filter(Boolean) as ChatOutputPart[]

  return parts.length > 0 ? parts : buildChatOutputParts(fallbackAnswer, fallbackArtifacts)
}

export const mergeChatArtifacts = (existing: unknown, additions: unknown) => {
  const normalized = [
    ...(Array.isArray(existing) ? existing : []),
    ...(Array.isArray(additions) ? additions : []),
  ]
    .map(item => normalizeChatArtifact(item))
    .filter(Boolean) as ChatArtifact[]
  return dedupeArtifacts(normalized)
}

export const groupChatImageArtifacts = (artifacts: unknown[] = []): ChatImageGalleryGroup[] => {
  const normalized = (Array.isArray(artifacts) ? artifacts : [])
    .map(item => normalizeChatArtifact(item))
    .filter(Boolean) as ChatArtifact[]

  const groups: MutableChatImageGalleryGroup[] = []
  const groupsById = new Map<string, MutableChatImageGalleryGroup>()
  let anonymousGroup: MutableChatImageGalleryGroup | null = null
  let anonymousIndex = 0

  for (const artifact of normalized) {
    if (!isImageArtifact(artifact))
      continue

    const explicitGroupId = String(artifact.group_id || '').trim()
    const explicitGroupName = String(artifact.group_name || '').trim()
    if (explicitGroupId) {
      anonymousGroup = null
      const key = `group:${explicitGroupId}`
      let group = groupsById.get(key)
      if (!group) {
        group = {
          id: explicitGroupId,
          title: explicitGroupName || artifact.name || '生成图片',
          images: [],
          seenUrls: new Set<string>(),
        }
        groupsById.set(key, group)
        groups.push(group)
      } else if (!group.title && (explicitGroupName || artifact.name)) {
        group.title = explicitGroupName || artifact.name || group.title
      }
      if (!group.seenUrls.has(artifact.url)) {
        group.seenUrls.add(artifact.url)
        group.images.push(artifact)
      }
      continue
    }

    if (!anonymousGroup) {
      anonymousGroup = {
        id: `anonymous-${anonymousIndex++}`,
        title: explicitGroupName || artifact.name || '生成图片',
        images: [],
        seenUrls: new Set<string>(),
      }
      groups.push(anonymousGroup)
    }
    if (!anonymousGroup.seenUrls.has(artifact.url)) {
      anonymousGroup.seenUrls.add(artifact.url)
      anonymousGroup.images.push(artifact)
    }
  }

  return groups.map(({ id, title, images }) => ({ id, title, images }))
}
