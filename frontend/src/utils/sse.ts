/**
 * SSE 流式响应客户端
 * 用于 AI 对话的实时流式输出
 */

export interface SSEEvent {
  id?: string
  event?: string
  data: string
}

export interface SSEOptions {
  onMessage?: (event: SSEEvent) => void
  onChunk?: (chunk: string, isFinal: boolean) => void
  // 双通道输入：结构化事件（如 confirmation_card），会带 event 字段和 data 载荷
  onEvent?: (eventType: string, data: any) => void
  onOpen?: () => void
  onError?: (error: Error) => void
  onComplete?: () => void
}

export class SSEClient {
  private url: string
  private options: SSEOptions
  private eventSource: EventSource | null = null
  private connected: boolean = false

  constructor(url: string, options: SSEOptions) {
    this.url = url
    this.options = options
  }

  connect(): void {
    if (this.eventSource) {
      this.close()
    }

    this.eventSource = new EventSource(this.url)
    this.connected = true

    this.eventSource.onopen = () => {
      this.options.onOpen?.()
    }

    this.eventSource.onerror = (error) => {
      this.options.onError?.(new Error('SSE connection error'))
      this.close()
    }

    this.eventSource.onmessage = (event) => {
      this.options.onMessage?.(event)

      try {
        const data = JSON.parse(event.data)
        // 双通道输入：识别结构化事件（如 confirmation_card）
        if (data.event && this.options.onEvent) {
          this.options.onEvent(data.event, data.data)
        } else if (data.chunk && this.options.onChunk) {
          this.options.onChunk(data.chunk, data.is_final || false)
        }

        if (data === '[DONE]') {
          this.options.onComplete?.()
          this.close()
        }
      } catch (e) {
        // 如果不是 JSON，直接作为纯文本处理
        if (event.data === '[DONE]') {
          this.options.onComplete?.()
          this.close()
        } else if (this.options.onChunk) {
          this.options.onChunk(event.data, false)
        }
      }
    }
  }

  // 微信小程序环境的兼容连接方式（使用 uni.request 流式读取）
  connectWechat(): void {
    const token = uni.getStorageSync('access_token')
    const requestTask = uni.request({
      url: this.url,
      method: 'POST',
      header: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      responseType: 'text',
      enableChunked: true,
      success: () => {
        this.options.onOpen?.()
      },
      fail: (error) => {
        this.options.onError?.(new Error(error.errMsg))
      },
    })

    // onChunkReceived 是微信小程序原生 API，uni-app 的 RequestTask 类型未涵盖，使用 any 断言
    ;(requestTask as any).onChunkReceived((res: any) => {
      try {
        const text = this.arrayBufferToUtf8(res.data)
        this.parseSSEChunk(text, this.options)
      } catch (e) {
        console.error('SSE chunk parse error:', e)
      }
    })
  }

  private arrayBufferToUtf8(buffer: ArrayBuffer): string {
    return new TextDecoder('utf-8').decode(buffer)
  }

  private parseSSEChunk(chunk: string, options: SSEOptions): void {
    const lines = chunk.split('\n')
    let currentData = ''
    let isFinal = false

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()
        if (data === '[DONE]') {
          isFinal = true
          options.onComplete?.()
          this.close()
          return
        }

        try {
          const json = JSON.parse(data)
          // 双通道输入：识别结构化事件（如 confirmation_card）
          if (json.event && options.onEvent) {
            options.onEvent(json.event, json.data)
          } else if (json.chunk && options.onChunk) {
            options.onChunk(json.chunk, json.is_final || false)
            if (json.is_final) {
              isFinal = true
            }
          }
        } catch (e) {
          currentData += data
        }
      }
    }

    if (currentData && !isFinal && options.onChunk) {
      options.onChunk(currentData, false)
    }
  }

  close(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
    this.connected = false
  }

  isConnected(): boolean {
    return this.connected
  }
}

/**
 * 创建 SSE 客户端并自动适配环境
 */
export function createSSEClient(
  url: string,
  options: SSEOptions
): SSEClient {
  const client = new SSEClient(url, options)

  // #ifdef MP-WEIXIN
  client.connectWechat()
  // #endif

  // #ifndef MP-WEIXIN
  client.connect()
  // #endif

  return client
}
