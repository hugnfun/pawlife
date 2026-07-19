<template>
  <view class="confirm-card" :class="`confirm-card--${statusClass}`">
    <!-- 待确认状态：可编辑字段 + 确认/取消按钮 -->
    <template v-if="statusClass === 'pending'">
      <view class="confirm-card__header">
        <text class="confirm-card__title">{{ typeTitle }}</text>
        <text class="confirm-card__subtitle">请确认或修改以下内容</text>
      </view>

      <view class="confirm-card__body">
        <!-- meal -->
        <template v-if="draft.log_type === 'meal'">
          <view class="field">
            <text class="field__label">食物</text>
            <input
              class="field__input"
              type="text"
              v-model="editable.food_name"
              placeholder="例：鸡胸肉"
            />
          </view>
          <view class="field">
            <text class="field__label">分量（克）</text>
            <input
              class="field__input"
              type="digit"
              v-model.number="editable.amount"
              placeholder="例：50"
            />
          </view>
        </template>

        <!-- weight -->
        <template v-else-if="draft.log_type === 'weight'">
          <view class="field">
            <text class="field__label">体重（公斤）</text>
            <input
              class="field__input"
              type="digit"
              v-model.number="editable.weight_kg"
              placeholder="例：5.2"
            />
          </view>
        </template>

        <!-- activity -->
        <template v-else-if="draft.log_type === 'activity'">
          <view class="field">
            <text class="field__label">运动类型</text>
            <input
              class="field__input"
              type="text"
              v-model="editable.activity_type"
              placeholder="例：散步"
            />
          </view>
          <view class="field">
            <text class="field__label">时长（分钟）</text>
            <input
              class="field__input"
              type="number"
              v-model.number="editable.duration_minutes"
              placeholder="例：30"
            />
          </view>
        </template>
      </view>

      <view class="confirm-card__actions">
        <button
          class="btn btn--secondary"
          :disabled="submitting"
          @tap="handleCancel"
        >
          取消
        </button>
        <button
          class="btn btn--primary"
          :disabled="submitting"
          @tap="handleConfirm"
        >
          {{ submitting ? '提交中...' : '确认' }}
        </button>
      </view>
    </template>

    <!-- 已确认：只读回执 -->
    <template v-else-if="statusClass === 'confirmed'">
      <view class="confirm-card__receipt">
        <text class="confirm-card__receipt-icon">✓</text>
        <text class="confirm-card__receipt-text">已记录：{{ receiptSummary }}</text>
      </view>
    </template>

    <!-- 已取消 -->
    <template v-else-if="statusClass === 'cancelled'">
      <view class="confirm-card__receipt confirm-card__receipt--muted">
        <text class="confirm-card__receipt-text">已取消记录</text>
      </view>
    </template>

    <!-- 已过期 -->
    <template v-else-if="statusClass === 'expired'">
      <view class="confirm-card__receipt confirm-card__receipt--muted">
        <text class="confirm-card__receipt-text">草稿已过期，如需记录请重新说一次</text>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, reactive, watch } from 'vue'
import type { PendingLogConfirmation } from '@/types/api'
import { confirmLogDraft, cancelLogDraft } from '@/api/logs'
import { useChatStore } from '@/stores/chat'

const props = defineProps<{
  draft: PendingLogConfirmation
  status: 'pending' | 'confirmed' | 'cancelled' | 'expired' | undefined
}>()

const chatStore = useChatStore()
const submitting = ref(false)

// 可编辑字段（初始化为 draft.payload 的浅拷贝）
const editable = reactive<Record<string, any>>({ ...props.draft.payload })

// 若 draft 变更（例如页面切换回来重新拉草稿），重置 editable
watch(
  () => props.draft.draft_id,
  () => {
    Object.keys(editable).forEach((k) => delete editable[k])
    Object.assign(editable, props.draft.payload)
  },
)

const statusClass = computed(() => props.status ?? 'pending')

const typeTitle = computed(() => {
  switch (props.draft.log_type) {
    case 'meal':
      return '记录饮食'
    case 'weight':
      return '记录体重'
    case 'activity':
      return '记录运动'
    default:
      return '待确认'
  }
})

// 已确认状态的摘要文本（优先展示用户实际提交的内容）
const receiptSummary = computed(() => {
  const p = props.draft.payload
  switch (props.draft.log_type) {
    case 'meal':
      return `${p.food_name} ${p.amount}${p.unit || 'g'}`
    case 'weight':
      return `${p.weight_kg} kg`
    case 'activity':
      return `${p.activity_type} ${p.duration_minutes} 分钟`
    default:
      return props.draft.summary || '已记录'
  }
})

// 计算 override（只把和原 payload 不同的字段发送）
function computeOverride(): Record<string, any> | null {
  const original = props.draft.payload
  const changed: Record<string, any> = {}
  let hasChange = false
  for (const key of Object.keys(editable)) {
    if (editable[key] !== original[key]) {
      changed[key] = editable[key]
      hasChange = true
    }
  }
  return hasChange ? changed : null
}

async function handleConfirm() {
  if (submitting.value) return
  submitting.value = true
  try {
    const override = computeOverride()
    // 用编辑后的值同步更新 draft.payload，回执展示会正确
    if (override) {
      Object.assign(props.draft.payload, override)
    }
    await confirmLogDraft(props.draft.draft_id, override)
    chatStore.updateConfirmationStatus(props.draft.draft_id, 'confirmed')
    uni.showToast({ title: '已记录', icon: 'success' })
  } catch (e: any) {
    // 404 → 过期，标记为 expired
    if (e?.message?.includes('404') || e?.message?.includes('过期')) {
      chatStore.updateConfirmationStatus(props.draft.draft_id, 'expired')
      uni.showToast({ title: '草稿已过期', icon: 'none' })
    } else {
      uni.showToast({ title: '记录失败，请重试', icon: 'none' })
    }
  } finally {
    submitting.value = false
  }
}

async function handleCancel() {
  if (submitting.value) return
  submitting.value = true
  try {
    await cancelLogDraft(props.draft.draft_id)
    chatStore.updateConfirmationStatus(props.draft.draft_id, 'cancelled')
  } catch (e) {
    // cancel 幂等，失败也直接标记为 cancelled
    chatStore.updateConfirmationStatus(props.draft.draft_id, 'cancelled')
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.confirm-card {
  margin-top: 16rpx;
  padding: 24rpx;
  background: #fff8f5;
  border: 2rpx solid #ffd7c2;
  border-radius: 16rpx;

  &--confirmed {
    background: #f0f9f4;
    border-color: #b8e6c8;
  }

  &--cancelled,
  &--expired {
    background: #f4f4f6;
    border-color: #e0e0e5;
  }

  &__header {
    margin-bottom: 16rpx;
  }

  &__title {
    display: block;
    font-size: 30rpx;
    font-weight: 600;
    color: #ff8c69;
  }

  &__subtitle {
    display: block;
    margin-top: 4rpx;
    font-size: 24rpx;
    color: #888;
  }

  &__body {
    margin-bottom: 20rpx;
  }

  .field {
    display: flex;
    align-items: center;
    margin-bottom: 16rpx;

    &__label {
      width: 160rpx;
      font-size: 26rpx;
      color: #555;
    }

    &__input {
      flex: 1;
      height: 64rpx;
      padding: 0 16rpx;
      background: #fff;
      border: 2rpx solid #e5d5cc;
      border-radius: 8rpx;
      font-size: 28rpx;
    }
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    gap: 16rpx;
  }

  .btn {
    padding: 0 32rpx;
    height: 64rpx;
    line-height: 64rpx;
    font-size: 26rpx;
    border-radius: 32rpx;
    border: none;

    &--secondary {
      background: #f0f0f2;
      color: #555;
    }

    &--primary {
      background: #ff8c69;
      color: #fff;
    }

    &[disabled] {
      opacity: 0.5;
    }
  }

  &__receipt {
    display: flex;
    align-items: center;
    gap: 12rpx;
  }

  &__receipt-icon {
    font-size: 32rpx;
    color: #4caf50;
  }

  &__receipt-text {
    font-size: 26rpx;
    color: #333;
  }

  &__receipt--muted &__receipt-text {
    color: #888;
  }
}
</style>
