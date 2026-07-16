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
})
