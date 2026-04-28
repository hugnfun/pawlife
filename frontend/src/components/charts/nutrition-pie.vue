<script setup lang="ts">
/**
 * 营养占比饼图（环形图）
 * 使用 uCharts 展示食物营养成分占比
 */
import { ref, computed, watch } from 'vue'

interface NutritionData {
  name: string
  value: number
  color?: string
}

const props = defineProps<{
  data: NutritionData[]
  totalCalories?: number
  height?: number
}>()

const canvasId = ref(`nutrition-pie-${Date.now()}`)
const defaultColors = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2', '#eb2f96']

const chartData = computed(() => ({
  series: props.data.map((item, index) => ({
    name: item.name,
    data: item.value,
    color: item.color || defaultColors[index % defaultColors.length],
  })),
}))

watch(() => props.data, () => {}, { immediate: true })
</script>

<template>
  <view class="nutrition-chart">
    <view class="chart-header">
      <text class="chart-title">营养成分占比</text>
      <text v-if="totalCalories" class="chart-subtitle">总计 {{ totalCalories }} kcal</text>
    </view>
    <canvas
      :canvas-id="canvasId"
      :id="canvasId"
      class="chart-canvas"
      :style="{ height: (height || 200) + 'px' }"
    />
    <view class="legend">
      <view v-for="(item, index) in data" :key="item.name" class="legend-item">
        <view class="legend-dot" :style="{ backgroundColor: item.color || defaultColors[index % defaultColors.length] }"></view>
        <text class="legend-name">{{ item.name }}</text>
        <text class="legend-value">{{ item.value }}g</text>
      </view>
    </view>
    <view class="chart-empty" v-if="!data || data.length === 0">
      <text class="empty-text">暂无营养数据</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.nutrition-chart {
  background-color: white;
  border-radius: 12px;
  padding: 12px;

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;

    .chart-title {
      font-size: 15px;
      font-weight: 500;
      color: #333;
    }

    .chart-subtitle {
      font-size: 12px;
      color: #666;
    }
  }

  .chart-canvas {
    width: 100%;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid #f0f0f0;

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;

      .legend-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .legend-name {
        font-size: 13px;
        color: #666;
      }

      .legend-value {
        font-size: 13px;
        color: #333;
        font-weight: 500;
      }
    }
  }

  .chart-empty {
    padding: 40px 0;
    text-align: center;

    .empty-text {
      font-size: 14px;
      color: #999;
    }
  }
}
</style>
