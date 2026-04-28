<script setup lang="ts">
/**
 * 通用骨架屏组件
 * 用于数据加载时展示占位效果
 */
defineProps<{
  rows?: number      // 骨架行数，默认 3
  showAvatar?: boolean // 是否显示头像占位
  showTitle?: boolean  // 是否显示标题占位
  cardStyle?: boolean  // 是否带卡片包裹，默认 true
}>()
</script>

<template>
  <view :class="['skeleton-wrap', { card: cardStyle !== false }]">
    <!-- 头像 + 标题行 -->
    <view v-if="showAvatar || showTitle" class="skeleton-header">
      <view v-if="showAvatar" class="skeleton-avatar skeleton-pulse"></view>
      <view class="skeleton-header-text">
        <view v-if="showTitle" class="skeleton-title skeleton-pulse"></view>
        <view class="skeleton-subtitle skeleton-pulse"></view>
      </view>
    </view>

    <!-- 内容行 -->
    <view class="skeleton-rows">
      <view
        v-for="i in rows || 3"
        :key="i"
        :class="['skeleton-row skeleton-pulse', { short: i === rows }]"
      ></view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.skeleton-wrap {
  padding: $spacing-lg;
  margin-bottom: $spacing-md;

  &.card {
    background-color: white;
    border-radius: $radius-md;
    box-shadow: $shadow-sm;
  }
}

.skeleton-header {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  margin-bottom: $spacing-lg;
}

.skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: $radius-full;
  flex-shrink: 0;
}

.skeleton-header-text {
  flex: 1;
}

.skeleton-title {
  width: 40%;
  height: 18px;
  border-radius: 9px;
  margin-bottom: $spacing-sm;
}

.skeleton-subtitle {
  width: 60%;
  height: 14px;
  border-radius: 7px;
}

.skeleton-rows {
  display: flex;
  flex-direction: column;
  gap: $spacing-sm;
}

.skeleton-row {
  width: 100%;
  height: 14px;
  border-radius: 7px;

  &.short {
    width: 65%;
  }
}

.skeleton-pulse {
  background: linear-gradient(90deg, $bg-page 25%, darken(#FAF7F5, 3%) 37%, $bg-page 63%);
  background-size: 400% 100%;
  animation: skeleton-loading 1.4s ease infinite;
}

@keyframes skeleton-loading {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
</style>
