<script setup lang="ts">
/**
 * AI 对话主界面
 * 对话优先，AI 作为主要交互入口
 */
import { ref, computed, nextTick, onMounted, watch, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { usePetStore } from '@/stores/pet'
import { aiConversation } from '@/api/ai'
import { createSSEClient } from '@/utils/sse'
import { getAIConversationStreamUrl } from '@/api/ai'
import { audioRecorder } from '@/utils/audio'
import { uploadAudio, uploadImage } from '@/utils/upload'
import ConfirmationCard from '@/components/chat/ConfirmationCard.vue'
import type { PendingLogConfirmation } from '@/types/api'

const chatStore = useChatStore()
const authStore = useAuthStore()
const petStore = usePetStore()

// 输入框
const inputText = ref('')
const isInputDisabled = computed(() => chatStore.isLoading || !authStore.isLoggedIn)

// 等待回复动画：. .. ... 循环（loading 或 streaming 都触发）
const typingDotsText = ref('.')
let typingDotsTimer: number | null = null

function startTypingAnimation() {
  if (typingDotsTimer) return
  let count = 0
  typingDotsTimer = setInterval(() => {
    count = (count + 1) % 3
    typingDotsText.value = '.'.repeat(count + 1)
  }, 400) as unknown as number
}

function stopTypingAnimation() {
  if (typingDotsTimer) {
    clearInterval(typingDotsTimer)
    typingDotsTimer = null
  }
  typingDotsText.value = '.'
}

watch(
  () => chatStore.isLoading || chatStore.isStreaming,
  (active) => {
    if (active) startTypingAnimation()
    else stopTypingAnimation()
  },
)

// 录音状态
const isRecording = ref(false)
const recordingDuration = ref(0)
const uploadingFile = ref(false)

// 消息列表容器
const messageContainer = ref<HTMLElement | null>(null)

// 当前活跃宠物
const activePetName = computed(() => {
  if (!chatStore.activePetId) return null
  return petStore.pets.find(p => p.id === chatStore.activePetId)?.name
})

// 滚动到底部
async function scrollToBottom() {
  await nextTick()
  // #ifdef H5
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
  // #endif
}

// 发送消息
async function sendMessage() {
  const message = inputText.value.trim()
  if (!message) return
  if (!authStore.isLoggedIn) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  // 添加用户消息
  chatStore.addMessage('user', message)
  inputText.value = ''
  chatStore.setLoading(true)

  try {
    // 使用流式响应
    await sendMessageStream(message)
  } catch (error) {
    console.error('发送消息失败:', error)
    uni.showToast({ title: '发送失败，请重试', icon: 'none' })
    chatStore.setLoading(false)
    chatStore.setStreaming(false)
  }
}

// 流式发送消息
async function sendMessageStream(message: string) {
  // 添加空的助手消息占位
  const assistantMsg = chatStore.addMessage('assistant', '')
  chatStore.setLoading(true)
  chatStore.setStreaming(true)

  // H5 环境使用 SSE
  // #ifdef H5
  const requestData = {
    message,
    input_type: 'text' as const,
    session_id: chatStore.currentSessionId || undefined,
    pet_id: chatStore.activePetId || undefined,
    onboarding_step: chatStore.onboardingStep || undefined,
    onboarding_data: chatStore.onboardingData || undefined,
  }
  const url = getAIConversationStreamUrl()
  const client = createSSEClient(url, {
    onChunk: (chunk, isFinal) => {
      chatStore.appendStreamingContent(chunk)
      if (isFinal) {
        assistantMsg.content = chatStore.streamingContent
        chatStore.setStreaming(false)
        chatStore.setLoading(false)
      }
      scrollToBottom()
    },
    // 双通道输入：识别 confirmation_card 事件，把 draft 挂到当前 assistant 消息上
    onEvent: (eventType, data) => {
      if (eventType === 'confirmation_card' && data) {
        // 确保消息体已定型（把 streamingContent 落到 msg.content 上）
        if (assistantMsg.content === '' && chatStore.streamingContent) {
          assistantMsg.content = chatStore.streamingContent
        }
        chatStore.attachPendingConfirmation(data as PendingLogConfirmation)
      }
    },
    onComplete: () => {
      chatStore.setStreaming(false)
      chatStore.setLoading(false)
    },
    onError: (error) => {
      console.error('SSE error:', error)
      // 降级到非流式请求
      sendMessageNonStream(message)
    },
  })
  // #endif

  // 微信小程序或 SSE 失败时降级非流式
  // #ifdef MP-WEIXIN
  await sendMessageNonStream(message)
  // #endif
}

// 非流式请求（降级方案）
async function sendMessageNonStream(message: string) {
  const requestData = {
    message,
    input_type: 'text' as const,
    session_id: chatStore.currentSessionId || undefined,
    pet_id: chatStore.activePetId || undefined,
  }

  const response = await aiConversation(requestData)
  chatStore.addMessage('assistant', response.response, response.suggestions)
  if (response.session_id) {
    chatStore.setSessionId(response.session_id)
  }
  // 双通道输入：非流式响应可能带 pending_confirmations 数组
  const pendingList = (response as any).pending_confirmations
  if (Array.isArray(pendingList) && pendingList.length > 0) {
    for (const item of pendingList) {
      if (item?.type === 'confirmation_card' && item.data) {
        chatStore.attachPendingConfirmation(item.data as PendingLogConfirmation)
      }
    }
  }
  chatStore.setLoading(false)
  scrollToBottom()
}

// 发送带媒体的消息（语音/图片）- 两步流程：先上传，再对话
async function sendMessageWithMedia(inputType: 'voice' | 'image', inputUrl: string) {
  const message = inputType === 'voice' ? '[语音消息]' : '[图片消息]'

  const requestData = {
    message,
    input_type: inputType,
    input_url: inputUrl,
    session_id: chatStore.currentSessionId || undefined,
    pet_id: chatStore.activePetId || undefined,
  }

  try {
    const response = await aiConversation(requestData)
    chatStore.addMessage('assistant', response.response, response.suggestions)
    if (response.session_id) {
      chatStore.setSessionId(response.session_id)
    }
  } catch (error: any) {
    console.error('媒体消息发送失败:', error)
    uni.showToast({ title: '发送失败，请重试', icon: 'none' })
  } finally {
    chatStore.setLoading(false)
    scrollToBottom()
  }
}

// 点击建议快捷发送
function quickSend(suggestion: string) {
  inputText.value = suggestion
  sendMessage()
}

// 清空对话
function clearChat() {
  uni.showModal({
    title: '确认清空',
    content: '确定要清空当前对话吗？',
    success: (res) => {
      if (res.confirm) {
        chatStore.clearMessages()
      }
    },
  })
}

// 格式化录音时长
function formatDuration(seconds: number): string {
  const min = Math.floor(seconds / 60)
  const sec = seconds % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

// 开始语音输入
async function startVoiceInput() {
  if (!authStore.isLoggedIn) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  if (isRecording.value) {
    // 正在录音 -> 停止录音
    audioRecorder.stop()
    return
  }

  // 初始化并开始录音
  audioRecorder.init({
    onStart: () => {
      isRecording.value = true
      recordingDuration.value = 0
      uni.showToast({ title: '开始录音...', icon: 'none', duration: 1000 })
    },
    onStop: async (filePath, duration) => {
      isRecording.value = false
      if (duration < 1) {
        uni.showToast({ title: '录音时间太短', icon: 'none' })
        return
      }

      // 添加用户消息（显示"语音消息"占位）
      chatStore.addMessage('user', `[语音消息 ${duration}秒]`)
      chatStore.setLoading(true)

      try {
        // 第一步：上传音频文件到后端
        uploadingFile.value = true
        const uploadResult = await uploadAudio({ filePath })
        // 第二步：将音频 URL 发送到对话流
        await sendMessageWithMedia('voice', uploadResult.url)
      } catch (error: any) {
        console.error('语音处理失败:', error)
        uni.showToast({ title: '语音处理失败', icon: 'none' })
        chatStore.setLoading(false)
      } finally {
        uploadingFile.value = false
      }
    },
    onError: (error) => {
      isRecording.value = false
      uni.showToast({ title: error || '录音失败', icon: 'none' })
    },
    onDurationUpdate: (duration) => {
      recordingDuration.value = duration
    },
  })

  audioRecorder.start()
}

// 拍照识别食物
async function takePhoto() {
  if (!authStore.isLoggedIn) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }

  try {
    const res = await new Promise<UniApp.ChooseImageSuccessCallbackResult>((resolve, reject) => {
      uni.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['camera', 'album'],
        success: resolve,
        fail: reject,
      })
    })

    const tempFilePath = res.tempFilePaths[0]
    if (!tempFilePath) return

    // 添加用户消息（显示图片预览）
    chatStore.addMessage('user', '[图片]')
    chatStore.setLoading(true)
    uploadingFile.value = true

    try {
      // 第一步：上传图片到后端
      const uploadResult = await uploadImage({ filePath: tempFilePath })
      // 第二步：将图片 URL 发送到对话流
      await sendMessageWithMedia('image', uploadResult.url)
    } catch (error: any) {
      console.error('图片处理失败:', error)
      uni.showToast({ title: '图片处理失败', icon: 'none' })
      chatStore.setLoading(false)
    } finally {
      uploadingFile.value = false
    }
  } catch (error: any) {
    console.error('选择图片失败:', error)
    if (error.errMsg?.includes('cancel')) return
    uni.showToast({ title: '选择图片失败', icon: 'none' })
  }
}

onMounted(async () => {
  authStore.restoreFromStorage()
  chatStore.restoreActivePet()

  // 从路由参数读取预填提示语和宠物 ID
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  // getCurrentPages()[i].options 是 uni-app 私有字段，官方类型未导出，使用 any 断言
  const query = (currentPage as any).options
  if (query.prompt) {
    inputText.value = decodeURIComponent(query.prompt)
  }
  if (query.pet_id) {
    chatStore.setActivePet(query.pet_id)
  }

  // 欢迎消息 - 即使 API 请求失败也要显示欢迎
  if (chatStore.messages.length === 0) {
    const username = authStore.userInfo?.nickname || '朋友'
    let welcome = `你好${username}！👋\n我是你的 AI 宠物健康助手，有什么我可以帮你的吗？\n\n你可以：\n• 询问宠物喂养建议\n• 记录喂食/活动/体重\n• 生成健康分析报告\n• 分析食物营养成分`
    chatStore.addMessage('assistant', welcome, [
      '我想记录今天的喂食',
      '帮我生成一份健康报告',
      '推荐一下猫粮配方',
    ])
  }

  // 异步加载宠物列表，失败不影响页面显示
  try {
    await petStore.fetchMyPets()
  } catch (error) {
    console.error('加载宠物列表失败:', error)
    uni.showToast({ title: '网络连接失败', icon: 'none' })
  }

  scrollToBottom()

  // #ifdef H5
  // 修复 uni-input 在 H5 下内部 input 元素宽度异常的问题
  setTimeout(() => {
    let isFixing = false
    const fixInputWidth = () => {
      if (isFixing) return
      isFixing = true
      document.querySelectorAll('uni-input').forEach((el) => {
        const wrapper = el.querySelector('.uni-input-wrapper') as HTMLElement | null
        const input = el.querySelector('input.uni-input-input') as HTMLInputElement | null
        if (wrapper && wrapper.style.width !== '100%') {
          wrapper.style.cssText += 'width:100%!important;flex:1 1 0!important;min-width:0!important;'
        }
        if (input && input.style.width !== '100%') {
          input.style.cssText += 'width:100%!important;flex:1 1 0!important;min-width:0!important;box-sizing:border-box!important;font-size:14px!important;line-height:1.5!important;color:#2D2D2D!important;height:32px!important;'
        }
      })
      isFixing = false
    }
    fixInputWidth()
    // 仅监听新节点插入，避免 style 变化引起的无限循环
    const observer = new MutationObserver(fixInputWidth)
    observer.observe(document.body, { childList: true, subtree: true })
  }, 100)
  // #endif
})

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

onUnmounted(() => {
  audioRecorder.destroy()
  if (typingDotsTimer) {
    clearInterval(typingDotsTimer)
    typingDotsTimer = null
  }
})
</script>

<template>
  <view class="chat-page">
    <!-- 消息列表 -->
    <scroll-view
      ref="messageContainer"
      class="message-list"
      scroll-y
      :scroll-top="scrollToBottom"
    >
      <view class="message-list-inner">
        <view
          v-for="msg in chatStore.currentMessages"
          :key="msg.id"
          :class="['message-item', `message-${msg.role}`]"
        >
          <view class="message-bubble">
            <text v-if="msg.role === 'user'" class="message-content">{{ msg.content }}</text>
            <mp-html v-else :content="msg.content" class="message-content" />
          </view>
          <!-- 双通道输入：AI 提取的日志草稿确认卡片 -->
          <ConfirmationCard
            v-if="msg.role === 'assistant' && msg.pendingConfirmation"
            :draft="msg.pendingConfirmation"
            :status="msg.confirmationStatus"
          />
          <!-- 建议快捷按钮 -->
          <view v-if="msg.suggestions && msg.suggestions.length > 0" class="suggestions">
            <button
              v-for="suggestion in msg.suggestions"
              :key="suggestion"
              class="suggestion-btn"
              @click="quickSend(suggestion)"
            >
              {{ suggestion }}
            </button>
          </view>
        </view>

        <!-- 流式输出占位 -->
        <view v-if="chatStore.isStreaming" class="message-item message-assistant">
          <view class="message-bubble">
            <mp-html :content="chatStore.streamingContent" class="message-content" />
            <text class="streaming-dots">{{ typingDotsText }}</text>
          </view>
        </view>

        <!-- 加载占位 -->
        <!-- 加载中（仅在非流式模式下显示） -->
        <view v-if="chatStore.isLoading && !chatStore.isStreaming" class="message-item message-assistant">
          <view class="message-bubble typing">
            <text class="typing-text">思考中</text>
            <text class="typing-dots">{{ typingDotsText }}</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 活跃宠物提示 -->
    <view v-if="activePetName" class="active-pet-bar">
      <view class="pet-tag">
        <text class="pet-tag-icon">🐾</text>
        <text class="pet-tag-text">{{ activePetName }}</text>
      </view>
    </view>

    <!-- 输入框区域 -->
    <view class="input-area">
      <view class="input-wrapper">
        <input
          v-model="inputText"
          class="text-input"
          type="text"
          placeholder="输入问题..."
          @confirm="sendMessage"
          :disabled="isInputDisabled"
        />
        <!-- #ifndef H5 -->
        <view class="input-actions">
          <button class="action-btn" @click="takePhoto" :disabled="isInputDisabled || uploadingFile">
            📷
          </button>
          <button
            :class="['action-btn', { recording: isRecording }]"
            @click="startVoiceInput"
            :disabled="isInputDisabled || uploadingFile"
          >
            🎤
          </button>
        </view>
        <!-- 录音状态指示器 -->
        <view v-if="isRecording" class="recording-indicator">
          <view class="recording-dot"></view>
          <text class="recording-time">{{ formatDuration(recordingDuration) }}</text>
          <text class="recording-hint">点击停止</text>
        </view>
        <!-- #endif -->
      </view>
      <button
        class="send-btn"
        @click="sendMessage"
        :disabled="isInputDisabled || !inputText.trim()"
      >
        发送
      </button>
      <!-- #ifndef H5 -->
      <button class="clear-btn" @click="clearChat" title="清空对话">
        🗑️
      </button>
      <!-- #endif -->
    </view>
  </view>
</template>

<style lang="scss" scoped>
.chat-page {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background-color: $bg-page;
  box-sizing: border-box;
}

.message-list {
  flex: 1;
  width: 100%;
  min-height: 0;
}

.message-list-inner {
  padding: $spacing-md;
}

.message-item {
  margin-bottom: $spacing-md;
  display: flex;
  animation: stagger-fade-in 0.3s ease-out both;

  &.message-user {
    justify-content: flex-end;

    .message-bubble {
      background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
      color: white;
      border-radius: $radius-lg $radius-lg 6px $radius-lg;
      box-shadow: 0 2px 8px rgba($primary-color, 0.2);
    }
  }

  &.message-assistant {
    justify-content: flex-start;

    .message-bubble {
      background-color: white;
      color: $text-primary;
      border-radius: $radius-lg $radius-lg $radius-lg 6px;
      box-shadow: $shadow-sm;
    }
  }
}

.message-bubble {
  max-width: 75%;
  padding: 12px 16px;
  border-radius: $radius-lg;
  line-height: 1.6;
  word-wrap: break-word;

  .message-content {
    // mp-html 渲染时不需要 pre-wrap
    &:deep(h1),
    &:deep(h2),
    &:deep(h3) {
      font-weight: 600;
      margin: 8px 0 4px;
    }
    &:deep(h1) { font-size: 18px; }
    &:deep(h2) { font-size: 16px; }
    &:deep(h3) { font-size: 14px; }
    &:deep(ul),
    &:deep(ol) {
      padding-left: 20px;
      margin: 4px 0;
    }
    &:deep(li) {
      margin: 2px 0;
    }
    &:deep(strong) {
      font-weight: 600;
    }
    &:deep(p) {
      margin: 4px 0;
    }
    &:deep(code) {
      font-size: 12px;
      background-color: rgba(0, 0, 0, 0.05);
      padding: 1px 4px;
      border-radius: 3px;
    }
    &:deep(table) {
      border-collapse: collapse;
      margin: 6px 0;
      font-size: 12px;
    }
    &:deep(th),
    &:deep(td) {
      border: 1px solid #e0e0e0;
      padding: 4px 8px;
    }
    &:deep(th) {
      background-color: rgba(0, 0, 0, 0.03);
      font-weight: 600;
    }
  }

  // 用户消息保持 pre-wrap
  &.message-user .message-content {
    white-space: pre-wrap;
  }

  .cursor {
    display: inline-block;
    width: 8px;
    color: $primary-color;
    animation: blink 1s infinite;
  }
}

.typing {
  padding: 12px 20px;
  display: inline-flex;
  align-items: center;
  gap: 4px;

  .typing-text {
    color: $primary-color;
    font-size: $font-size-base;
  }

  .typing-dots {
    display: inline-block;
    color: $primary-color;
    font-size: $font-size-base;
    width: 24px;
    text-align: left;
    font-weight: bold;
  }
}

.streaming-dots {
  display: inline-block;
  color: $primary-color;
  font-size: $font-size-base;
  font-weight: bold;
  margin-left: 4px;
  vertical-align: baseline;
}

.suggestions {
  margin-top: $spacing-sm;
  display: flex;
  flex-wrap: wrap;
  gap: $spacing-sm;

  .suggestion-btn {
    font-size: $font-size-sm;
    padding: 4px 14px;
    border: 1px solid $primary-color;
    border-radius: $radius-lg;
    background-color: white;
    color: $primary-color;
    line-height: 1.5;
    transition: all 0.2s;

    &:active {
      background-color: $primary-color;
      color: white;
    }
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.active-pet-bar {
  padding: $spacing-sm $spacing-md;
  text-align: center;

  .pet-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 14px;
    background-color: $primary-color-light;
    border-radius: $radius-lg;
    border: 1px solid rgba($primary-color, 0.15);

    .pet-tag-icon {
      font-size: 14px;
    }

    .pet-tag-text {
      font-size: $font-size-sm;
      color: $primary-color;
      font-weight: 500;
    }
  }
}

.input-area {
  display: flex;
  align-items: center;
  width: 100%;
  box-sizing: border-box;
  padding: $spacing-md;
  background-color: white;
  border-top: 1px solid $border-color;
  gap: $spacing-sm;

  .input-wrapper {
    flex: 1 1 0;
    width: 100%;
    display: flex;
    align-items: center;
    background-color: $bg-page;
    border-radius: $radius-xl;
    padding: 4px 8px;
    border: 1px solid $border-color;
    transition: border-color 0.2s;
    min-width: 0;
    box-sizing: border-box;

    &:focus-within {
      border-color: $primary-color;
    }

    .text-input {
      flex: 1 1 0;
      width: 100%;
      min-width: 0;
      padding: 8px 12px;
      font-size: $font-size-base;
      background-color: transparent;
      box-sizing: border-box;
      /* uni-app H5: 强制 input 内部元素填满 */
      :deep(.uni-input-input),
      :deep(input) {
        width: 100% !important;
        min-width: 0 !important;
      }
    }

    .input-actions {
      display: flex;
      gap: 2px;

      .action-btn {
        width: 34px;
        height: 34px;
        line-height: 34px;
        padding: 0;
        border-radius: $radius-full;
        background-color: transparent;
        font-size: 18px;

        &:active {
          background-color: $bg-hover;
        }

        &.recording {
          background-color: $error-color;
          color: white;
          animation: pulse 1.5s infinite;
        }
      }
    }
  }

  .send-btn {
    padding: $spacing-sm $spacing-lg;
    background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
    color: white;
    border-radius: $radius-lg;
    font-size: $font-size-base;
    line-height: 1.5;
    font-weight: 500;
    box-shadow: 0 2px 8px rgba($primary-color, 0.25);
    transition: all 0.2s;

    &:active {
      transform: scale(0.95);
    }

    &:disabled {
      background: linear-gradient(135deg, $text-disabled 0%, #bbb 100%);
      color: white;
      box-shadow: none;
      transform: none;
    }
  }

  .clear-btn {
    width: 36px;
    height: 36px;
    padding: 0;
    line-height: 36px;
    background-color: transparent;
    border-radius: $radius-full;
    font-size: 18px;

    &:active {
      background-color: $bg-page;
    }
  }
}

.recording-indicator {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background-color: rgba(0, 0, 0, 0.75);
  border-radius: $radius-md;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: $spacing-sm;
  z-index: 999;

  .recording-dot {
    width: 12px;
    height: 12px;
    border-radius: $radius-full;
    background-color: $error-color;
    animation: pulse 1s infinite;
  }

  .recording-time {
    font-size: 28px;
    color: white;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .recording-hint {
    font-size: $font-size-sm;
    color: rgba(255, 255, 255, 0.6);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

@keyframes stagger-fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
