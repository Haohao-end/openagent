import { describe, it, expect } from 'vitest'
import { validatePythonSyntax, checkCodeQuality } from '@/utils/python-validator'

describe('Python Validator', () => {
  describe('validatePythonSyntax', () => {
    it('should validate correct Python code', () => {
      const code = `def main(params):
    x = int(params.get('x', 0))
    y = int(params.get('y', 0))
    return {'result': x + y}`

      const result = validatePythonSyntax(code)
      expect(result.isValid).toBe(true)
      expect(result.errors.length).toBe(0)
    })

    it('should detect missing main function', () => {
      const code = `def test():
    pass`

      const result = validatePythonSyntax(code)
      expect(result.isValid).toBe(false)
      expect(result.errors.some(e => e.message.includes('main(params)'))).toBe(true)
    })

    it('should detect incorrect main function signature', () => {
      const code = `def main():
    return {}`

      const result = validatePythonSyntax(code)
      expect(result.isValid).toBe(false)
      expect(result.errors.some(e => e.message.includes('main 函数必须接受 params 参数'))).toBe(true)
    })

    it('should detect indentation errors', () => {
      const code = `def main(params):
return {}`

      const result = validatePythonSyntax(code)
      expect(result.isValid).toBe(false)
      expect(result.errors.some(e => e.message.includes('IndentationError'))).toBe(true)
    })

    it('should detect unmatched brackets', () => {
      const code = `def main(params):
    result = (x + y
    return {'result': result}`

      const result = validatePythonSyntax(code)
      expect(result.isValid).toBe(false)
      expect(result.errors.some(e => e.message.includes('未闭合'))).toBe(true)
    })

    it('should warn about missing return statement', () => {
      const code = `def main(params):
    x = 1
    y = 2`

      const result = validatePythonSyntax(code)
      expect(result.warnings.some(w => w.message.includes('返回'))).toBe(true)
    })

    it('should warn about incorrect indentation spacing', () => {
      const code = `def main(params):
  return {}`

      const result = validatePythonSyntax(code)
      expect(result.warnings.some(w => w.message.includes('PEP 8'))).toBe(true)
    })
  })

  describe('checkCodeQuality', () => {
    it('should suggest using params.get()', () => {
      const code = `def main(params):
    x = params['x']
    return {'result': x}`

      const suggestions = checkCodeQuality(code)
      expect(suggestions.some(s => s.message.includes('params.get'))).toBe(true)
    })

    it('should suggest type conversion', () => {
      const code = `def main(params):
    x = params.get('x')
    return {'result': x}`

      const suggestions = checkCodeQuality(code)
      expect(suggestions.some(s => s.message.includes('类型转换'))).toBe(true)
    })

    it('should suggest exception handling', () => {
      const code = `def main(params):
    x = int(params.get('x', 0))
    return {'result': x}`

      const suggestions = checkCodeQuality(code)
      expect(suggestions.some(s => s.message.includes('异常处理'))).toBe(true)
    })
  })
})
