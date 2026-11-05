export const parsePositiveIntegerQuery = (value: unknown, fallbackValue: number): number => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 1) return fallbackValue
  return Math.floor(parsed)
}
