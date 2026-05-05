export const WORKFLOW_TOOL_CALL_NAME_REGEX = /^[A-Za-z_][A-Za-z0-9_]*$/

export const isValidWorkflowToolCallName = (value: string): boolean => {
  return WORKFLOW_TOOL_CALL_NAME_REGEX.test(String(value || '').trim())
}

