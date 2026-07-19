import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '@/stores/chat'

// mock uni 全局对象（uni-app SDK 未在 vitest 环境注入）
;(globalThis as any).uni = {
  setStorageSync: vi.fn(),
  getStorageSync: vi.fn(() => ''),
  removeStorageSync: vi.fn(),
}

describe('Chat Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should initialize with empty messages', () => {
    const store = useChatStore()
    expect(store.currentMessages).toEqual([])
    expect(store.isLoading).toBe(false)
    expect(store.isStreaming).toBe(false)
  })

  it('should add a user message', () => {
    const store = useChatStore()
    store.addMessage('user', 'Hello')
    expect(store.currentMessages).toHaveLength(1)
    expect(store.currentMessages[0].role).toBe('user')
    expect(store.currentMessages[0].content).toBe('Hello')
  })

  it('should add an assistant message with suggestions', () => {
    const store = useChatStore()
    store.addMessage('assistant', 'Hi there!', ['suggestion 1', 'suggestion 2'])
    expect(store.currentMessages).toHaveLength(1)
    expect(store.currentMessages[0].suggestions).toEqual(['suggestion 1', 'suggestion 2'])
  })

  it('should set loading state', () => {
    const store = useChatStore()
    store.setLoading(true)
    expect(store.isLoading).toBe(true)
    store.setLoading(false)
    expect(store.isLoading).toBe(false)
  })

  it('should set streaming state and append content', () => {
    const store = useChatStore()
    store.setStreaming(true)
    expect(store.isStreaming).toBe(true)

    store.appendStreamingContent('Hello')
    expect(store.streamingContent).toBe('Hello')

    store.appendStreamingContent(' World')
    expect(store.streamingContent).toBe('Hello World')

    store.setStreaming(false)
    expect(store.isStreaming).toBe(false)
  })

  it('should clear messages', () => {
    const store = useChatStore()
    store.addMessage('user', 'Hello')
    store.addMessage('assistant', 'Hi')
    expect(store.currentMessages).toHaveLength(2)

    store.clearMessages()
    expect(store.currentMessages).toHaveLength(0)
  })

  it('should manage session ID', () => {
    const store = useChatStore()
    store.setSessionId('session-123')
    expect(store.currentSessionId).toBe('session-123')
  })

  it('should manage active pet', () => {
    const store = useChatStore()
    store.setActivePet('pet-123')
    expect(store.activePetId).toBe('pet-123')
  })

  // 双通道输入：确认草稿相关方法
  it('should attach pending confirmation to last assistant message', () => {
    const store = useChatStore()
    store.addMessage('assistant', 'AI 回复')
    store.attachPendingConfirmation({
      draft_id: 'd1',
      log_type: 'meal',
      pet_id: 'pet-1',
      payload: { food_name: '鸡胸肉', amount: 50 },
      summary: '记录一次饮食：鸡胸肉 50g',
    })
    const msg = store.currentMessages[0]
    expect(msg.pendingConfirmation?.draft_id).toBe('d1')
    expect(msg.confirmationStatus).toBe('pending')
  })

  it('should not attach confirmation when last message is user', () => {
    const store = useChatStore()
    store.addMessage('user', '我给三花喂了 50g 鸡胸肉')
    store.attachPendingConfirmation({
      draft_id: 'd2',
      log_type: 'meal',
      pet_id: 'pet-1',
      payload: {},
      summary: '',
    })
    // 用户消息不应被附加
    expect(store.currentMessages[0].pendingConfirmation).toBeUndefined()
  })

  it('should update confirmation status', () => {
    const store = useChatStore()
    store.addMessage('assistant', 'AI 回复')
    store.attachPendingConfirmation({
      draft_id: 'd3',
      log_type: 'weight',
      pet_id: 'pet-1',
      payload: { weight_kg: 5.0 },
      summary: '记录体重：5.0 kg',
    })
    store.updateConfirmationStatus('d3', 'confirmed')
    expect(store.currentMessages[0].confirmationStatus).toBe('confirmed')

    store.updateConfirmationStatus('d3', 'cancelled')
    expect(store.currentMessages[0].confirmationStatus).toBe('cancelled')
  })

  it('should silently ignore updateConfirmationStatus for unknown draft', () => {
    const store = useChatStore()
    store.addMessage('assistant', 'AI 回复')
    // 不应抛异常
    expect(() => store.updateConfirmationStatus('nonexistent', 'confirmed')).not.toThrow()
  })
})
