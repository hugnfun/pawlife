<script setup lang="ts">
/**
 * 体重趋势折线图
 * 使用 uCharts 展示宠物体重变化趋势
 */
import { ref, onMounted, watch } from 'vue'

interface WeightData {
  date: string
  weight: number
}

const props = defineProps<{
  data: WeightData[]
  petName?: string
  idealWeight?: number
  height?: number
}>()

const canvasId = ref(`weight-line-${Date.now()}`)

const chartData = ref({
  categories: [] as string[],
  series: [
    {
      name: '体重',
      data: [] as number[],
      color: '#1677ff',
    },
  ],
})

watch(() => props.data, (newData) => {
  if (newData && newData.length > 0) {
    updateChart(newData)
  }
}, { immediate: true })

function updateChart(data: WeightData[]) {
  chartData.value = {
    categories: data.map(d => {
      const date = new Date(d.date)
      return `${date.getMonth() + 1}/${date.getDate()}`
    }),
    series: [
      {
        name: '体重',
        data: data.map(d => d.weight),
        color: '#1677ff',
      },
    ],
  }

  if (props.idealWeight) {
    chartData.value.series.push({
      name: '理想体重',
      data: data.map(() => props.idealWeight!),
      color: '#52c41a',
      lineType: 'dash',
    } as any)
  }
}

onMounted(() => {
  if (props.data && props.data.length > 0) {
    updateChart(props.data)
  }
})
</script>

<template>
  <view class="weight-chart">
    <view class="chart-header" v-if="petName">
      <text class="chart-title">{{ petName }} 的体重趋势</text>
      <text v-if="idealWeight" class="chart-subtitle">理想体重: {{ idealWeight }}kg</text>
    </view>
    <canvas
      :canvas-id="canvasId"
      :id="canvasId"
      class="chart-canvas"
      :style="{ height: (height || 200) + 'px' }"
    />
    <view class="chart-empty" v-if="!data || data.length === 0">
      <text class="empty-text">暂无体重记录</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.weight-chart {
  background-color: white;
  border-radius: 12px;
  padding: 12px;

  .chart-header {
    margin-bottom: 8px;

    .chart-title {
      display: block;
      font-size: 15px;
      font-weight: 500;
      color: #333;
    }

    .chart-subtitle {
      font-size: 12px;
      color: #52c41a;
      margin-top: 4px;
    }
  }

  .chart-canvas {
    width: 100%;
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
