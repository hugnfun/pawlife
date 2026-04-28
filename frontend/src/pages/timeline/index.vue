<script setup lang="ts">
/**
 * 记录流页面
 * 展示所有宠物记录的时间线
 */
import { ref, onMounted } from 'vue'
import { usePetStore } from '@/stores/pet'
import { getTimeline, getTodayStats } from '@/api/logs'
import type { MealLog } from '@/types/api'

const petStore = usePetStore()

// 状态
const loading = ref(false)
const refreshing = ref(false)
const hasMore = ref(true)
const currentPage = ref(1)
const pageSize = 20
const timelineData = ref<MealLog[]>([])

// 今日统计
const todayStats = ref<{
  total_calories: number
  nutrition_completeness: number
} | null>(null)

// 当前筛选宠物
const selectedPetId = ref<string | null>(null)

// 加载记录
async function loadData(pullDown: boolean = false) {
  if (loading.value) return

  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize,
    }
    if (selectedPetId.value) {
      params.pet_id = selectedPetId.value
    }

    const data = await getTimeline(params)

    if (pullDown || currentPage.value === 1) {
      timelineData.value = data.list
    } else {
      timelineData.value.push(...data.list)
    }

    hasMore.value = data.list.length >= pageSize
    currentPage.value++
  } catch (error) {
    console.error('加载记录失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

// 加载今日统计
async function loadTodayStats() {
  if (!selectedPetId.value) {
    todayStats.value = null
    return
  }

  try {
    const stats = await getTodayStats(selectedPetId.value)
    todayStats.value = stats
  } catch (error) {
    console.error('加载今日统计失败:', error)
  }
}

// 下拉刷新
function onPullDownRefresh() {
  refreshing.value = true
  currentPage.value = 1
  loadData(true)
  uni.stopPullDownRefresh()
}

// 上拉加载更多
function onReachBottom() {
  if (hasMore.value && !loading.value) {
    loadData()
  }
}

// 切换宠物筛选
function changePet(petId: string | null) {
  selectedPetId.value = petId
  currentPage.value = 1
  timelineData.value = []
  loadData()
  loadTodayStats()
}

// 获取图标
function getLogIcon(log: MealLog) {
  switch (log.food_type) {
    case 'main':
      return '🍚'
    case 'snack':
      return '🍖'
    case 'treat':
      return '🍬'
    default:
      return '🍴'
  }
}

// 格式化时间
function formatTime(timeStr: string) {
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  } else if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  } else if (diff < 604800000) {
    return `${Math.floor(diff / 86400000)}天前`
  } else {
    return `${date.getMonth() + 1}/${date.getDate()}`
  }
}

// 格式化数字
function formatNumber(value: number, decimals: number = 0) {
  return value.toFixed(decimals)
}

// 营养完整度颜色类名
function completenessClass(value: number) {
  if (value >= 0.9) return 'good'
  if (value >= 0.7) return 'medium'
  return 'bad'
}

onMounted(() => {
  petStore.fetchMyPets()
  if (petStore.currentSelectedPet) {
    selectedPetId.value = petStore.currentSelectedPet.id
    loadTodayStats()
  }
  loadData()
})
</script>

<template>
  <view class="timeline-page">
    <!-- 宠物筛选器 -->
    <view class="pet-filter">
      <scroll-view class="pet-filter-scroll" scroll-x>
        <view
          :class="['pet-filter-item', { active: selectedPetId === null }]"
          @click="changePet(null)"
        >
          全部
        </view>
        <view
          v-for="pet in petStore.pets"
          :key="pet.id"
          :class="['pet-filter-item', { active: selectedPetId === pet.id }]"
          @click="changePet(pet.id)"
        >
          {{ pet.name }}
        </view>
      </scroll-view>
    </view>

    <!-- 今日统计卡片 -->
    <view class="today-stats" v-if="todayStats && selectedPetId">
      <view class="stat-item">
        <text class="stat-value calories">{{ formatNumber(todayStats.total_calories, 0) }}</text>
        <text class="stat-label">今日热量 (大卡)</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value" :class="completenessClass(todayStats.nutrition_completeness)">
          {{ formatNumber(todayStats.nutrition_completeness * 100, 0) }}%
        </text>
        <text class="stat-label">营养完整度</text>
      </view>
    </view>

    <!-- 时间线列表 -->
    <view class="timeline-list" v-if="timelineData.length > 0">
      <view v-for="(item, index) in timelineData" :key="item.id"
        class="timeline-item stagger-enter"
        :style="{ animationDelay: `${Math.min(index * 0.06, 0.5)}s` }"
      >
        <view class="timeline-dot">
          <text class="timeline-icon">{{ getLogIcon(item) }}</text>
        </view>
        <view class="timeline-content card">
          <view class="timeline-header">
            <text class="food-name">{{ item.food_name }}</text>
            <text class="time">{{ formatTime(item.created_at) }}</text>
          </view>
          <view class="timeline-body">
            <text class="amount">
              {{ item.amount }} {{ item.unit }}
              <text v-if="item.food_type" class="food-type">({{ item.food_type }})</text>
            </text>
            <text v-if="item.notes" class="notes">{{ item.notes }}</text>
            <text v-if="item.operator_nickname" class="operator">
              👤 {{ item.operator_nickname }}
            </text>
          </view>
          <image v-if="item.image_url" :src="item.image_url" class="food-image" mode="aspectFill" />
        </view>
      </view>

      <!-- 加载更多提示 -->
      <view class="load-more" v-if="hasMore">
        <text v-if="!loading">上拉加载更多</text>
        <text v-if="loading">加载中...</text>
      </view>
      <view class="load-more no-more" v-if="!hasMore">
        没有更多了
      </view>
    </view>

    <!-- 空状态 -->
    <view class="empty-state" v-else-if="!loading">
      <text class="empty-icon">📝</text>
      <text class="empty-text">暂无记录</text>
      <text class="empty-hint">通过 AI 对话开始记录吧</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.timeline-page {
  min-height: 100vh;
  background-color: $bg-page;
  padding-bottom: 20px;
}

.pet-filter {
  background-color: white;
  padding: $spacing-md 0;
  margin-bottom: $spacing-md;

  .pet-filter-scroll {
    white-space: nowrap;
    padding: 0 $spacing-md;
  }

  .pet-filter-item {
    display: inline-block;
    padding: 6px 18px;
    margin-right: $spacing-sm;
    border-radius: $radius-lg;
    font-size: $font-size-base;
    background-color: $bg-page;
    color: $text-secondary;
    transition: all 0.25s ease;

    &.active {
      background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
      color: white;
      box-shadow: 0 2px 8px rgba($primary-color, 0.25);
    }
  }
}

.today-stats {
  display: flex;
  justify-content: space-around;
  align-items: center;
  margin: 0 $spacing-md $spacing-md;
  padding: $spacing-xl $spacing-lg;
  background: white;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;

  .stat-item {
    text-align: center;
    flex: 1;

    .stat-value {
      display: block;
      font-size: $font-size-display;
      font-weight: 600;
      color: $primary-color;
      margin-bottom: $spacing-xs;

      &.good { color: $success-color; }
      &.medium { color: $warning-color; }
      &.bad { color: $error-color; }

      &.calories {
        background: linear-gradient(135deg, $primary-color, $primary-color-dark);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
    }

    .stat-label {
      font-size: $font-size-sm;
      color: $text-secondary;
    }
  }

  .stat-divider {
    width: 1px;
    height: 40px;
    background-color: $divider-color;
  }
}

.timeline-list {
  padding: 0 $spacing-md;
}

.timeline-item {
  display: flex;
  margin-bottom: $spacing-lg;
  position: relative;

  .timeline-dot {
    width: 48px;
    display: flex;
    justify-content: center;
    flex-shrink: 0;
    position: relative;

    .timeline-icon {
      width: 40px;
      height: 40px;
      line-height: 40px;
      text-align: center;
      font-size: 20px;
      background-color: $primary-color-light;
      border-radius: $radius-full;
      box-shadow: $shadow-xs;
    }

    &::after {
      content: '';
      position: absolute;
      top: 46px;
      left: 50%;
      transform: translateX(-50%);
      width: 2px;
      height: calc(100% + 8px);
      background: linear-gradient(180deg, $border-color, transparent);
    }
  }

  .timeline-content {
    flex: 1;
    margin-bottom: 0;

    .timeline-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: $spacing-sm;

      .food-name {
        font-size: $font-size-lg;
        font-weight: 500;
        color: $text-primary;
      }

      .time {
        font-size: $font-size-sm;
        color: $text-secondary;
      }
    }

    .timeline-body {
      .amount {
        font-size: $font-size-base;
        color: $text-regular;

        .food-type {
          color: $text-secondary;
        }
      }

      .notes {
        display: block;
        margin-top: $spacing-xs;
        font-size: $font-size-md;
        color: $text-secondary;
      }

      .operator {
        display: inline-block;
        margin-top: $spacing-xs;
        font-size: $font-size-sm;
        color: $primary-color;
        background-color: $primary-color-light;
        padding: 2px 10px;
        border-radius: $radius-sm;
        font-weight: 500;
      }
    }

    .food-image {
      width: 80px;
      height: 80px;
      border-radius: $radius-sm;
      margin-top: $spacing-sm;
      box-shadow: $shadow-xs;
    }
  }
}

.load-more {
  text-align: center;
  padding: $spacing-lg;
  font-size: $font-size-md;
  color: $text-secondary;

  &.no-more {
    color: $text-disabled;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: 100px;

  .empty-icon {
    font-size: 56px;
    margin-bottom: $spacing-lg;
    opacity: 0.6;
  }

  .empty-text {
    font-size: $font-size-lg;
    color: $text-regular;
    margin-bottom: $spacing-sm;
  }

  .empty-hint {
    font-size: $font-size-md;
    color: $text-secondary;
  }
}
</style>
