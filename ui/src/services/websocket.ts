import { io } from 'socket.io-client'

const socket = io(import.meta.env.VITE_API_URL || 'http://localhost:5001', {
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: 5,
})

export function setupAgentNotificationListener(agentNotificationRef: any) {
  // 监听Agent通知事件
  socket.on('agent_notification', (data: any) => {
    if (agentNotificationRef.value) {
      agentNotificationRef.value.addNotification(data)
    }
  })
}

export default socket
