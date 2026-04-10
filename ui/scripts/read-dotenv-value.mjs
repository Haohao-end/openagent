import { readFileSync } from 'node:fs'

const [, , filePath, targetKey] = process.argv

if (!filePath || !targetKey) {
  console.error('Usage: node scripts/read-dotenv-value.mjs <file> <key>')
  process.exit(1)
}

const content = readFileSync(filePath, 'utf8')
let value = ''

for (const rawLine of content.split(/\r?\n/u)) {
  const line = rawLine.trim()

  if (!line || line.startsWith('#') || !line.includes('=')) {
    continue
  }

  const separatorIndex = line.indexOf('=')
  const key = line.slice(0, separatorIndex).trim()

  if (key !== targetKey) {
    continue
  }

  value = line.slice(separatorIndex + 1).trim()

  if (
    (value.startsWith('"') && value.endsWith('"'))
    || (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1)
  }

  break
}

if (!value) {
  console.error(`ERROR: ${targetKey} is required in ${filePath}`)
  process.exit(1)
}

process.stdout.write(value)
