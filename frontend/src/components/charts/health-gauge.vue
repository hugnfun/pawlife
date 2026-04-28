<script setup lang="ts">
/**
 * 健康评分仪表盘
 * 使用 uCharts 展示宠物综合健康评分
 */
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  score: number
  label?: string
  height?: number
}>()

const canvasId = ref(`health-gauge-${Date.now()}`)

const scoreColor = computed(() => {
  if (props.score >= 80) return '#52c41a'
  if (props.score >= 60) return '#faad14'
  return '#ff4d4f'
})

const scoreLabel = computed(() => {
  if (props.score >= 90) return '优秀'
  if (props.score >= 80) return '良好'
  if (props.score >= 60) return '一般'
  if (props.score >= 40) return '需关注'
  return '需就医'
})

const chartData = computed(() => ({
  series: [
    {
      name: '健康评分',
      data: [props.score],
      color: scoreColor.value,
    },
  ],
}))

watch(() => props.score, () => {}, { immediate: true })
</script>

<template>
  <view class="health-gauge">
    <view class="gauge-container">
      <canvas
        :canvas-id="canvasId"
        :id="canvasId"
        class="gauge-canvas"
        :style="{ height: (height || 180) + 'px' }"
      />
      <view class="gauge-center">
        <text class="gauge-score" :style="{ color: scoreColor }">{{ score }}</text>
        <text class="gauge-label">{{ scoreLabel }}</text>
      </view>
    </view>
    <view v-if="label" class="gauge-desc">
      <text class="desc-text">{{ label }}</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.health-gauge {
  background-color: white;
  border-radius: 12px;
  padding: 16px;
  text-align: center;

  .gauge-container {
    position: relative;
    width: 100%;
    max-width: 240px;
    margin: 0 auto;
  }

  .gauge-canvas {
    width: 100%;
  }

  .gauge-center {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;

    .gauge-score {
      font-size: 40px;
      font-weight: 700;
      line-height: 1;
    }

    .gauge-label {
      font-size: 14px;
      color: #666;
      margin-top: 4px;
    }
  }

  .gauge-desc {
    margin-top: 12px;

    .desc-text {
      font-size: 13px;
      color: #999;
    }
  }
}
</style>
