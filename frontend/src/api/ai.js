import request from './request'

/**
 * AI 助手 API
 */
export function sendMessage(messages) {
  return request.post('/ai/chat', { messages, stream: false })
}

export function testConnection() {
  return request.get('/ai/test')
}
