import { socketConnectionUrl, socketPath } from '@/config'
import { io } from 'socket.io-client'

const socket = io(socketConnectionUrl, {
  path: socketPath,
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: 5,
})

export function setupAgentNotificationListener(agentNotificationRef: any) {
  // 监听Agent通知事件
  socket.on('agent_notification', (data: any) => {
    try {
      if (!data || !data.id || !data.app_id) {
        console.warn('[Agent Notification] Invalid notification data:', data)
        return
      }
      if (agentNotificationRef.value) {
        agentNotificationRef.value.addNotification(data)
      }
    } catch (error) {
      console.error('[Agent Notification] Error handling notification:', error)
    }
  })
}

export default socket
