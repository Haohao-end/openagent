import type { AgentNotification } from '@/models/agent-notification'
import { createNotificationWebSocket } from '@/hooks/use-notification-websocket'

export const useAgentNotificationWebSocket = createNotificationWebSocket<AgentNotification>({
  connectLogMessage: '[WebSocket] Connected for Agent notifications',
  notificationEvent: 'agent_notification',
  receiveLogMessage: '[WebSocket] Received agent notification:',
  subscribeEvent: 'subscribe_agent_notification',
  subscribeFailureLogMessage: '[WebSocket] Failed to subscribe agent notifications:',
  unsubscribeEvent: 'unsubscribe_agent_notification',
})
