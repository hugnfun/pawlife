// AI 对话状态 store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage } from '@/types/api'

// 简单 ID 生成，兼容微信小程序
function nanoid(size = 21) {
  let result = ''
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  const charactersLength = characters.length
  for (let i = 0; i < size; i++) {
    result += characters.charAt(Math.floor(Math.random() * charactersLength))
  }
  return result
}

export const useChatStore = defineStore(
  'chat',
  () => {
    // 状态
    const messages = ref<ChatMessage[]>([])
    const currentSessionId = ref<string | null>(null)
    const isLoading = ref(false)
    const isStreaming = ref(false)
    const streamingContent = ref('')
    const activePetId = ref<string | null>(null)
    const onboardingStep = ref<string | null>(null)
    const onboardingData = ref<Record<string, any> | null>(null)

    // 计算属性
    const hasMessages = computed(() => messages.value.length > 0)
    const currentMessages = computed(() => messages.value)

    // 添加消息
    function addMessage(role: ChatMessage['role'], content: string, suggestions?: string[]): ChatMessage {
      const message: ChatMessage = {
        id: nanoid(),
        role,
        content,
        timestamp: Date.now(),
        suggestions,
      }
      messages.value.push(message)
      return message
    }

    // 清空对话
    function clearMessages() {
      messages.value = []
      currentSessionId.value = null
      streamingContent.value = ''
    }

    // 设置当前会话 ID
    function setSessionId(sessionId: string) {
      currentSessionId.value = sessionId
    }

    // 设置加载状态
    function setLoading(loading: boolean) {
      isLoading.value = loading
    }

    // 设置流式输出状态
    function setStreaming(streaming: boolean) {
      isStreaming.value = streaming
      if (!streaming && streamingContent.value) {
        // 流式输出完成，将内容添加到最后一条消息
        if (messages.value.length > 0) {
          const lastMsg = messages.value[messages.value.length - 1]
          if (lastMsg.role === 'assistant' && lastMsg.content === '') {
            lastMsg.content = streamingContent.value
          }
        }
        streamingContent.value = ''
      }
    }

    // 追加流式内容
    function appendStreamingContent(chunk: string) {
      streamingContent.value += chunk
    }

    // 设置活跃宠物
    function setActivePet(petId: string | null) {
      activePetId.value = petId
      // 保存到本地
      if (petId) {
        uni.setStorageSync('active_pet_id', petId)
      } else {
        uni.removeStorageSync('active_pet_id')
      }
    }

    // 设置 onboarding 状态
    function setOnboarding(step: string | null, data: Record<string, any> | null = null) {
      onboardingStep.value = step
      onboardingData.value = data
    }

    // 从本地恢复活跃宠物
    function restoreActivePet() {
      const petId = uni.getStorageSync('active_pet_id')
      if (petId) {
        activePetId.value = petId
      }
    }

    return {
      messages,
      currentSessionId,
      isLoading,
      isStreaming,
      streamingContent,
      activePetId,
      onboardingStep,
      onboardingData,
      hasMessages,
      currentMessages,
      addMessage,
      clearMessages,
      setSessionId,
      setLoading,
      setStreaming,
      appendStreamingContent,
      setActivePet,
      restoreActivePet,
      setOnboarding,
    }
  }
)
