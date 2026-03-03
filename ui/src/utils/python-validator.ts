/**
 * Python 代码验证工具
 * 提供基础的 Python 语法检查和代码质量分析
 */

export interface ValidationError {
  severity: number // 8: Error, 4: Warning, 2: Info, 1: Hint
  startLineNumber: number
  startColumn: number
  endLineNumber: number
  endColumn: number
  message: string
}

export interface ValidationResult {
  isValid: boolean
  errors: ValidationError[]
  warnings: ValidationError[]
}

/**
 * 检查 Python 代码的基础语法
 */
export function validatePythonSyntax(code: string): ValidationResult {
  const errors: ValidationError[] = []
  const warnings: ValidationError[] = []

  if (!code || code.trim() === '') {
    return { isValid: true, errors: [], warnings: [] }
  }

  const lines = code.split('\n')

  // 1. 检查是否定义了 main 函数
  const hasMainFunction = /def\s+main\s*\(\s*params\s*\)\s*:/.test(code)
  if (!hasMainFunction) {
    errors.push({
      severity: 8,
      startLineNumber: 1,
      startColumn: 1,
      endLineNumber: 1,
      endColumn: 1,
      message: '代码必须包含 main(params) 函数定义',
    })
  }

  // 2. 检查是否有 return 语句
  const hasReturn = /return\s+\{/.test(code)
  if (!hasReturn) {
    warnings.push({
      severity: 4,
      startLineNumber: lines.length,
      startColumn: 1,
      endLineNumber: lines.length,
      endColumn: 1,
      message: 'main 函数应该返回一个字典对象',
    })
  }

  // 3. 逐行检查
  let inMultilineString = false
  let multilineStringChar = ''
  const openBracketsStack: Array<{ char: string; line: number; col: number }> = []

  lines.forEach((line, index) => {
    const lineNumber = index + 1
    const trimmedLine = line.trim()

    // 跳过空行和注释
    if (trimmedLine === '' || trimmedLine.startsWith('#')) {
      return
    }

    // 处理多行字符串
    const tripleQuotes = line.match(/"""|'''/g)
    if (tripleQuotes) {
      tripleQuotes.forEach((quote) => {
        if (!inMultilineString) {
          inMultilineString = true
          multilineStringChar = quote
        } else if (quote === multilineStringChar) {
          inMultilineString = false
          multilineStringChar = ''
        }
      })
    }

    if (inMultilineString) {
      return
    }

    // 检查缩进（Python 对缩进敏感）
    if (line.length > 0 && line[0] === ' ') {
      const spaces = line.match(/^ */)?.[0].length || 0
      if (spaces % 4 !== 0) {
        warnings.push({
          severity: 4,
          startLineNumber: lineNumber,
          startColumn: 1,
          endLineNumber: lineNumber,
          endColumn: spaces + 1,
          message: 'PEP 8: 缩进应该是 4 个空格',
        })
      }
    }

    // 检查制表符
    if (line.includes('\t')) {
      warnings.push({
        severity: 4,
        startLineNumber: lineNumber,
        startColumn: line.indexOf('\t') + 1,
        endLineNumber: lineNumber,
        endColumn: line.indexOf('\t') + 2,
        message: 'PEP 8: 不应使用制表符，请使用空格',
      })
    }

    // 检查冒号后的缩进
    if (trimmedLine.endsWith(':') && index < lines.length - 1) {
      const nextLine = lines[index + 1]
      const currentIndent = line.match(/^ */)?.[0].length || 0
      const nextIndent = nextLine.match(/^ */)?.[0].length || 0

      if (nextLine.trim() !== '' && nextIndent <= currentIndent) {
        errors.push({
          severity: 8,
          startLineNumber: lineNumber + 1,
          startColumn: 1,
          endLineNumber: lineNumber + 1,
          endColumn: nextLine.length + 1,
          message: 'IndentationError: 预期缩进块',
        })
      }
    }

    // 检查括号匹配
    for (let i = 0; i < line.length; i++) {
      const char = line[i]
      if (char === '(' || char === '[' || char === '{') {
        openBracketsStack.push({ char, line: lineNumber, col: i + 1 })
      } else if (char === ')' || char === ']' || char === '}') {
        const last = openBracketsStack.pop()
        if (!last) {
          errors.push({
            severity: 8,
            startLineNumber: lineNumber,
            startColumn: i + 1,
            endLineNumber: lineNumber,
            endColumn: i + 2,
            message: `SyntaxError: 未匹配的 '${char}'`,
          })
        } else {
          const pairs: Record<string, string> = { '(': ')', '[': ']', '{': '}' }
          if (pairs[last.char] !== char) {
            errors.push({
              severity: 8,
              startLineNumber: lineNumber,
              startColumn: i + 1,
              endLineNumber: lineNumber,
              endColumn: i + 2,
              message: `SyntaxError: 括号不匹配，期望 '${pairs[last.char]}' 但得到 '${char}'`,
            })
          }
        }
      }
    }

    // 检查常见的语法错误
    if (trimmedLine.match(/^(if|elif|else|for|while|def|class|try|except|finally|with)\s/)) {
      if (!trimmedLine.endsWith(':')) {
        errors.push({
          severity: 8,
          startLineNumber: lineNumber,
          startColumn: line.length,
          endLineNumber: lineNumber,
          endColumn: line.length + 1,
          message: "SyntaxError: 语句末尾缺少 ':'",
        })
      }
    }

    // 检查 main 函数签名
    if (trimmedLine.includes('def main') && !trimmedLine.match(/def\s+main\s*\(\s*params\s*\)\s*:/)) {
      errors.push({
        severity: 8,
        startLineNumber: lineNumber,
        startColumn: 1,
        endLineNumber: lineNumber,
        endColumn: line.length + 1,
        message: 'main 函数必须接受 params 参数: def main(params):',
      })
    }

    // 检查行长度（PEP 8 建议不超过 79 字符）
    if (line.length > 79) {
      warnings.push({
        severity: 2,
        startLineNumber: lineNumber,
        startColumn: 80,
        endLineNumber: lineNumber,
        endColumn: line.length + 1,
        message: `PEP 8: 行长度超过 79 字符 (当前 ${line.length} 字符)`,
      })
    }

    // 检查常见的拼写错误
    if (trimmedLine.match(/\bimort\b/)) {
      errors.push({
        severity: 8,
        startLineNumber: lineNumber,
        startColumn: line.indexOf('imort') + 1,
        endLineNumber: lineNumber,
        endColumn: line.indexOf('imort') + 6,
        message: "NameError: 可能是拼写错误，是否想输入 'import'?",
      })
    }

    // 检查未使用的导入（简单检查）
    const importMatch = trimmedLine.match(/^import\s+(\w+)|^from\s+\w+\s+import\s+(\w+)/)
    if (importMatch) {
      const importedName = importMatch[1] || importMatch[2]
      const restOfCode = lines.slice(index + 1).join('\n')
      if (!restOfCode.includes(importedName)) {
        warnings.push({
          severity: 2,
          startLineNumber: lineNumber,
          startColumn: 1,
          endLineNumber: lineNumber,
          endColumn: line.length + 1,
          message: `未使用的导入: ${importedName}`,
        })
      }
    }
  })

  // 检查未闭合的括号
  if (openBracketsStack.length > 0) {
    openBracketsStack.forEach((bracket) => {
      errors.push({
        severity: 8,
        startLineNumber: bracket.line,
        startColumn: bracket.col,
        endLineNumber: bracket.line,
        endColumn: bracket.col + 1,
        message: `SyntaxError: 未闭合的 '${bracket.char}'`,
      })
    })
  }

  return {
    isValid: errors.length === 0,
    errors: [...errors, ...warnings],
    warnings,
  }
}

/**
 * 检查代码质量和最佳实践
 */
export function checkCodeQuality(code: string): ValidationError[] {
  const suggestions: ValidationError[] = []
  const lines = code.split('\n')

  lines.forEach((line, index) => {
    const lineNumber = index + 1
    const trimmedLine = line.trim()

    // 检查是否使用了 params.get() 而不是直接访问
    if (trimmedLine.match(/params\[['"][\w]+['"]\]/)) {
      suggestions.push({
        severity: 2,
        startLineNumber: lineNumber,
        startColumn: 1,
        endLineNumber: lineNumber,
        endColumn: line.length + 1,
        message: "建议使用 params.get('key', default) 代替 params['key'] 以避免 KeyError",
      })
    }

    // 检查是否有类型转换
    if (trimmedLine.match(/params\.get\(['"][\w]+['"]\)/) && !trimmedLine.match(/int\(|float\(|str\(|bool\(/)) {
      suggestions.push({
        severity: 2,
        startLineNumber: lineNumber,
        startColumn: 1,
        endLineNumber: lineNumber,
        endColumn: line.length + 1,
        message: '建议对输入参数进行类型转换（如 int(), float() 等）',
      })
    }

    // 检查是否有异常处理
    if (trimmedLine.includes('int(') || trimmedLine.includes('float(')) {
      const hasExceptionHandling = code.includes('try:') && code.includes('except')
      if (!hasExceptionHandling) {
        suggestions.push({
          severity: 2,
          startLineNumber: lineNumber,
          startColumn: 1,
          endLineNumber: lineNumber,
          endColumn: line.length + 1,
          message: '建议添加异常处理（try-except）以处理类型转换错误',
        })
      }
    }
  })

  return suggestions
}

/**
 * 格式化 Python 代码（基础版本）
 */
export function formatPythonCode(code: string): string {
  const lines = code.split('\n')
  const formattedLines: string[] = []
  let indentLevel = 0

  lines.forEach((line) => {
    const trimmedLine = line.trim()

    // 跳过空行
    if (trimmedLine === '') {
      formattedLines.push('')
      return
    }

    // 减少缩进（对于 else, elif, except, finally 等）
    if (trimmedLine.match(/^(else|elif|except|finally):/)) {
      indentLevel = Math.max(0, indentLevel - 1)
    }

    // 添加缩进
    const indentedLine = '    '.repeat(indentLevel) + trimmedLine

    formattedLines.push(indentedLine)

    // 增加缩进（对于以冒号结尾的行）
    if (trimmedLine.endsWith(':')) {
      indentLevel++
    }

    // 减少缩进（对于 return, break, continue, pass 等）
    if (trimmedLine.match(/^(return|break|continue|pass)\b/)) {
      indentLevel = Math.max(0, indentLevel - 1)
    }
  })

  return formattedLines.join('\n')
}
