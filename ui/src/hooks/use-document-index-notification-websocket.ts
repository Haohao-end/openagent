import type { DocumentIndexNotification } from '@/models/notification'
import { createNotificationWebSocket } from '@/hooks/use-notification-websocket'

export const useDocumentIndexNotificationWebSocket =
  createNotificationWebSocket<DocumentIndexNotification>({
    connectLogMessage: '[WebSocket] Connected',
    notificationEvent: 'document_index_notification',
    receiveLogMessage: '[WebSocket] Received notification:',
    subscribeEvent: 'subscribe_document_index_notification',
    subscribeFailureLogMessage: '[WebSocket] Failed to subscribe document notifications:',
    unsubscribeEvent: 'unsubscribe_document_index_notification',
  })
