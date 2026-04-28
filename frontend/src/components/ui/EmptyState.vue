<script setup lang="ts">
/**
 * 通用空状态组件
 * 用于列表无数据、页面无内容等场景
 */
defineProps<{
  icon?: string        // Emoji 图标，默认 🐾
  title?: string       // 主标题
  description?: string // 描述文字
  actionText?: string  // 操作按钮文字
}>()

defineEmits<{
  (e: 'action'): void
}>()
</script>

<template>
  <view class="empty-state">
    <view class="empty-icon-wrap">
      <text class="empty-icon">{{ icon || '🐾' }}</text>
    </view>
    <text class="empty-title">{{ title || '暂无数据' }}</text>
    <text class="empty-desc" v-if="description">{{ description }}</text>
    <button v-if="actionText" class="empty-action-btn" @click="$emit('action')">
      {{ actionText }}
    </button>
  </view>
</template>

<style lang="scss" scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;

  .empty-icon-wrap {
    width: 88px;
    height: 88px;
    border-radius: $radius-full;
    background: linear-gradient(135deg, $primary-color-light, $primary-color-lighter);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: $spacing-lg;
  }

  .empty-icon {
    font-size: 40px;
  }

  .empty-title {
    font-size: $font-size-xl;
    font-weight: 500;
    color: $text-primary;
    margin-bottom: $spacing-sm;
  }

  .empty-desc {
    font-size: $font-size-md;
    color: $text-secondary;
    text-align: center;
    line-height: 1.5;
    margin-bottom: $spacing-xl;
  }

  .empty-action-btn {
    padding: $spacing-sm $spacing-xxl;
    background: linear-gradient(135deg, $primary-color, $primary-color-dark);
    color: white;
    border-radius: $radius-lg;
    font-size: $font-size-base;
    font-weight: 500;
    box-shadow: 0 2px 8px rgba($primary-color, 0.25);
    transition: all 0.2s ease;

    &:active {
      transform: scale(0.97);
    }

    &::after { border: none; }
  }
}
</style>
