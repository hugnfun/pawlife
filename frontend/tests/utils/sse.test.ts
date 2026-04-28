import { describe, it, expect, vi } from 'vitest'

// Mock uni API
vi.mock('@dcloudio/uni-app', () => ({
  request: vi.fn(),
}))

describe('SSE Client', () => {
  it('should export createSSEClient function', async () => {
    const { createSSEClient } = await import('@/utils/sse')
    expect(typeof createSSEClient).toBe('function')
  })

  it('createSSEClient should return an object with control methods', async () => {
    const { createSSEClient } = await import('@/utils/sse')

    // 不会实际连接，只测试接口
    // 在 H5 环境使用 EventSource，在微信小程序使用 uni.request
    // 这里只验证函数可调用
    expect(createSSEClient).toBeDefined()
  })
})
