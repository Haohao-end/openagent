import { onBeforeUnmount } from 'vue'

export const useWorkflowRefreshTimer = () => {
  let timer: ReturnType<typeof setTimeout>
  const cancel = () => clearTimeout(timer)

  const schedule = (refresh: () => void | Promise<void>) => {
    cancel()
    timer = setTimeout(refresh, 500)
  }

  onBeforeUnmount(cancel)

  return schedule
}
