export type TextDiffSegment = {
  type: 'equal' | 'removed' | 'added'
  text: string
}

export type PromptCompareErrorType = 'error' | 'timeout'

export const getPromptCompareErrorType = (event: unknown): PromptCompareErrorType | undefined =>
  event === 'error' || event === 'timeout' ? event : undefined

export const buildPromptCompareDiff = (
  baseline: string,
  candidate: string,
  side: 'baseline' | 'candidate',
): TextDiffSegment[] => {
  const baselineChars = Array.from(baseline)
  const candidateChars = Array.from(candidate)
  let prefixLength = 0

  while (
    prefixLength < baselineChars.length &&
    prefixLength < candidateChars.length &&
    baselineChars[prefixLength] === candidateChars[prefixLength]
  ) {
    prefixLength += 1
  }

  let suffixLength = 0
  while (
    suffixLength < baselineChars.length - prefixLength &&
    suffixLength < candidateChars.length - prefixLength &&
    baselineChars[baselineChars.length - suffixLength - 1] ===
      candidateChars[candidateChars.length - suffixLength - 1]
  ) {
    suffixLength += 1
  }

  const source = side === 'baseline' ? baselineChars : candidateChars
  const middleEnd = source.length - suffixLength
  const changedType = side === 'baseline' ? 'removed' : 'added'
  const segments: TextDiffSegment[] = []

  if (prefixLength > 0) {
    segments.push({ type: 'equal', text: source.slice(0, prefixLength).join('') })
  }
  if (middleEnd > prefixLength) {
    segments.push({ type: changedType, text: source.slice(prefixLength, middleEnd).join('') })
  }
  if (suffixLength > 0) {
    segments.push({ type: 'equal', text: source.slice(middleEnd).join('') })
  }

  return segments
}

export const getPromptCompareLatencyDelta = (baselineSeconds: number, candidateSeconds: number) => {
  if (!Number.isFinite(baselineSeconds) || !Number.isFinite(candidateSeconds)) return null
  if (baselineSeconds < 0 || candidateSeconds < 0) return null
  return Number((candidateSeconds - baselineSeconds).toFixed(2))
}
