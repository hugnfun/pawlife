<script setup lang="ts">
/**
 * 宠物档案详情页
 * 展示宠物基本信息、疫苗记录、当前饮食方案
 * 每个区块支持点击编辑跳转到 AI 对话并预填提示语
 */
import { ref, onMounted, computed } from 'vue'
import { usePetStore } from '@/stores/pet'
import { getPetProfile, getVaccineRecords, getDietRecipe } from '@/api/pet-profile'
import type { Pet, VaccineRecord, DietRecipe } from '@/types/api'

const petStore = usePetStore()

// 状态
const loading = ref(false)
const currentPet = ref<Pet | null>(null)
const vaccineRecords = ref<VaccineRecord[]>([])
const currentDiet = ref<DietRecipe | null>(null)

// 当前宠物 ID 从路由获取
const pages = getCurrentPages()
const currentPage = pages[pages.length - 1]
// getCurrentPages()[i].options 是 uni-app 私有字段，官方类型未导出，使用 any 断言
const query = (currentPage as any).options
const petId = computed(() => query.pet_id || petStore.currentSelectedPet?.id || null)

// 加载数据
async function loadData() {
  if (!petId.value) {
    uni.showToast({ title: '未选择宠物', icon: 'none' })
    uni.navigateBack()
    return
  }

  loading.value = true
  try {
    // 获取宠物基本信息
    const profile = await getPetProfile(petId.value)
    currentPet.value = profile

    // 获取疫苗记录
    const vaccines = await getVaccineRecords(petId.value)
    vaccineRecords.value = vaccines

    // 获取当前饮食方案
    const recipe = await getDietRecipe(petId.value)
    currentDiet.value = recipe
  } catch (error) {
    console.error('加载档案失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

// 编辑宠物档案
function editProfile() {
  if (!currentPet.value) return
  const prompt = `帮我更新 ${currentPet.value.name} 的基本档案信息`
  uni.redirectTo({
    url: `/pages/chat/index?prompt=${encodeURIComponent(prompt)}&pet_id=${currentPet.value.id}`
  })
}

// 添加/编辑疫苗记录
function editVaccines() {
  if (!currentPet.value) return
  const prompt = `帮我管理 ${currentPet.value.name} 的疫苗接种记录`
  uni.redirectTo({
    url: `/pages/chat/index?prompt=${encodeURIComponent(prompt)}&pet_id=${currentPet.value.id}`
  })
}

// 调整饮食方案
function editDiet() {
  if (!currentPet.value) return
  const prompt = `帮我调整 ${currentPet.value.name} 的饮食方案`
  uni.redirectTo({
    url: `/pages/chat/index?prompt=${encodeURIComponent(prompt)}&pet_id=${currentPet.value.id}`
  })
}

// 格式化日期
function formatDate(dateStr: string) {
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

// 格式化数字
function formatNumber(value: number, decimals: number = 0) {
  return value.toFixed(decimals)
}

onMounted(() => {
  petStore.fetchMyPets()
  loadData()
})
</script>

<template>
  <view class="pet-profile-page">
    <!-- 骨架屏加载 -->
    <view v-if="loading" class="skeleton-loading">
      <view class="skeleton-card"></view>
      <view class="skeleton-card" style="height: 160px;"></view>
      <view class="skeleton-card" style="height: 200px;"></view>
    </view>

    <template v-else>
      <!-- 基本信息区块 -->
      <view class="section card" v-if="currentPet">
        <view class="section-header">
          <view class="title-with-accent">
            <view class="accent-bar"></view>
            <text class="section-title">基本信息</text>
          </view>
          <button class="edit-btn" @click="editProfile">编辑</button>
        </view>
        <view class="pet-basic-info">
          <view class="pet-avatar" v-if="currentPet.avatar_url">
            <image :src="currentPet.avatar_url" mode="aspectFill" />
          </view>
          <view class="pet-avatar default-avatar" v-else>
            <text v-if="currentPet.species === 'dog'">🐶</text>
            <text v-else-if="currentPet.species === 'cat'">🐱</text>
            <text v-else>🐾</text>
          </view>
          <view class="info-grid">
            <view class="info-item">
              <text class="label">名称</text>
              <text class="value">{{ currentPet.name }}</text>
            </view>
            <view class="info-item">
              <text class="label">品种</text>
              <text class="value">{{ currentPet.breed || '未填写' }}</text>
            </view>
            <view class="info-item">
              <text class="label">性别</text>
              <text class="value">{{ currentPet.gender === 'male' ? '公' : '母' }}</text>
            </view>
            <view class="info-item">
              <text class="label">生日</text>
              <text class="value">{{ currentPet.birthday ? formatDate(currentPet.birthday) : '未填写' }}</text>
            </view>
            <view class="info-item">
              <text class="label">当前体重</text>
              <text class="value">{{ currentPet.current_weight ? `${currentPet.current_weight}kg` : '未填写' }}</text>
            </view>
            <view class="info-item">
              <text class="label">理想体重</text>
              <text class="value">{{ currentPet.ideal_weight ? `${currentPet.ideal_weight}kg` : '未填写' }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 疫苗记录区块 -->
      <view class="section card">
        <view class="section-header">
          <view class="title-with-accent">
            <view class="accent-bar accent-warning"></view>
            <text class="section-title">疫苗接种记录</text>
          </view>
          <button class="edit-btn" @click="editVaccines">管理</button>
        </view>
        <view class="vaccine-list" v-if="vaccineRecords.length > 0">
          <view v-for="record in vaccineRecords" :key="record.id" class="vaccine-item">
            <view class="vaccine-header">
              <text class="vaccine-name">{{ record.vaccine_name }}</text>
              <text class="vaccine-type">{{ record.vaccine_type }}</text>
            </view>
            <view class="vaccine-date">
              接种日期: {{ formatDate(record.vaccine_date) }}
            </view>
            <view v-if="record.next_dose_date" class="next-dose">
              <text class="pulse-dot"></text>
              下次接种: {{ formatDate(record.next_dose_date) }}
            </view>
            <view v-if="record.notes" class="notes">{{ record.notes }}</view>
          </view>
        </view>
        <view class="empty-hint" v-else>
          暂无疫苗记录，点击上方管理按钮添加
        </view>
      </view>

      <!-- 当前饮食方案区块 -->
      <view class="section card">
        <view class="section-header">
          <view class="title-with-accent">
            <view class="accent-bar accent-success"></view>
            <text class="section-title">当前饮食方案</text>
          </view>
          <button class="edit-btn" @click="editDiet">调整</button>
        </view>
        <view v-if="currentDiet" class="diet-info">
          <view class="diet-header">
            <text class="diet-name">{{ currentDiet.name }}</text>
            <text class="daily-calories">{{ currentDiet.daily_calories }} 大卡/天</text>
          </view>
          <view class="nutrition-ratios">
            <view class="ratio-item">
              <text class="ratio-label">蛋白质</text>
              <view class="ratio-bar-wrap">
                <view class="ratio-bar protein" :style="{ width: `${currentDiet.protein_ratio * 100}%` }"></view>
              </view>
              <text class="ratio-value">{{ formatNumber(currentDiet.protein_ratio * 100, 1) }}%</text>
            </view>
            <view class="ratio-item">
              <text class="ratio-label">脂肪</text>
              <view class="ratio-bar-wrap">
                <view class="ratio-bar fat" :style="{ width: `${currentDiet.fat_ratio * 100}%` }"></view>
              </view>
              <text class="ratio-value">{{ formatNumber(currentDiet.fat_ratio * 100, 1) }}%</text>
            </view>
            <view class="ratio-item">
              <text class="ratio-label">碳水</text>
              <view class="ratio-bar-wrap">
                <view class="ratio-bar carb" :style="{ width: `${currentDiet.carb_ratio * 100}%` }"></view>
              </view>
              <text class="ratio-value">{{ formatNumber(currentDiet.carb_ratio * 100, 1) }}%</text>
            </view>
          </view>
          <view v-if="currentDiet.description" class="diet-description">
            {{ currentDiet.description }}
          </view>
          <view class="meal-list" v-if="currentDiet.meals.length > 0">
            <text class="meal-list-title">每日用餐安排</text>
            <view v-for="(meal, index) in currentDiet.meals" :key="index" class="meal-item">
              <text class="meal-time">{{ meal.time }}</text>
              <text class="meal-content">{{ meal.food }} {{ meal.amount }}{{ meal.unit }}</text>
            </view>
          </view>
        </view>
        <view class="empty-hint" v-else>
          暂无饮食方案，点击上方调整按钮让 AI 生成个性化方案
        </view>
      </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.pet-profile-page {
  min-height: 100vh;
  background-color: $bg-page;
  padding: $spacing-md;
  padding-bottom: 40px;
}

// 骨架屏
.skeleton-loading {
  padding: 0;
}

// 区块标题带彩色装饰线
.title-with-accent {
  display: flex;
  align-items: center;
  gap: $spacing-sm;

  .accent-bar {
    width: 4px;
    height: 18px;
    border-radius: 2px;
    background: $primary-color;

    &.accent-warning { background: $warning-color; }
    &.accent-success { background: $success-color; }
  }

  .section-title {
    font-size: $font-size-xl;
    font-weight: 600;
    color: $text-primary;
  }
}

.section {
  margin-bottom: $spacing-lg;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-lg;

    .edit-btn {
      font-size: $font-size-base;
      color: $primary-color;
      background: none;
      border: none;
      padding: $spacing-xs $spacing-md;
      line-height: 24px;
      font-weight: 500;

      &::after { border: none; }
    }
  }
}

.pet-basic-info {
  display: flex;
  gap: $spacing-lg;

  .pet-avatar {
    width: 80px;
    height: 80px;
    border-radius: $radius-md;
    overflow: hidden;
    flex-shrink: 0;
    box-shadow: $shadow-xs;

    image {
      width: 100%;
      height: 100%;
    }

    &.default-avatar {
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, $primary-color-light, $primary-color-lighter);
      font-size: 32px;
    }
  }

  .info-grid {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: $spacing-md $spacing-sm;

    .info-item {
      .label {
        font-size: $font-size-sm;
        color: $text-secondary;
        display: block;
        margin-bottom: 2px;
      }
      .value {
        font-size: $font-size-md;
        color: $text-primary;
        font-weight: 500;
      }
    }
  }
}

.vaccine-list {
  .vaccine-item {
    padding: $spacing-md;
    background-color: $bg-page;
    border-radius: $radius-sm;
    margin-bottom: $spacing-sm;

    &:last-child { margin-bottom: 0; }

    .vaccine-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: $spacing-xs;

      .vaccine-name {
        font-size: $font-size-md;
        font-weight: 500;
        color: $text-primary;
      }

      .vaccine-type {
        font-size: $font-size-sm;
        padding: 2px 10px;
        background-color: $primary-color-light;
        color: $primary-color;
        border-radius: $radius-xs;
        font-weight: 500;
      }
    }

    .vaccine-date {
      font-size: $font-size-base;
      color: $text-regular;
      margin-bottom: $spacing-xs;
    }

    .next-dose {
      font-size: $font-size-md;
      color: $warning-color;
      margin-bottom: $spacing-xs;
      display: flex;
      align-items: center;
      gap: 6px;
      font-weight: 500;

      .pulse-dot {
        width: 6px;
        height: 6px;
        border-radius: $radius-full;
        background-color: $warning-color;
        animation: pulse 1.5s infinite;
      }
    }

    .notes {
      font-size: $font-size-md;
      color: $text-secondary;
    }
  }
}

.empty-hint {
  text-align: center;
  color: $text-secondary;
  font-size: $font-size-base;
  padding: $spacing-xl 0;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.3); }
}

.diet-info {
  .diet-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-md;

    .diet-name {
      font-size: $font-size-lg;
      font-weight: 600;
      color: $text-primary;
    }

    .daily-calories {
      font-size: $font-size-base;
      padding: 4px 12px;
      background-color: $success-color-light;
      color: darken($success-color, 15%);
      border-radius: $radius-xs;
      font-weight: 500;
    }
  }

  .nutrition-ratios {
    display: flex;
    flex-direction: column;
    gap: $spacing-sm;
    padding: $spacing-md;
    margin-bottom: $spacing-md;
    background-color: $bg-page;
    border-radius: $radius-sm;

    .ratio-item {
      display: flex;
      align-items: center;
      gap: $spacing-sm;

      .ratio-label {
        width: 44px;
        font-size: $font-size-sm;
        color: $text-secondary;
        flex-shrink: 0;
      }

      .ratio-bar-wrap {
        flex: 1;
        height: 6px;
        background-color: $divider-color;
        border-radius: 3px;
        overflow: hidden;

        .ratio-bar {
          height: 100%;
          border-radius: 3px;
          transition: width 0.6s ease;
          background: $primary-color;

          &.fat { background: $warning-color; }
          &.carb { background: $secondary-color; }
        }
      }

      .ratio-value {
        width: 45px;
        text-align: right;
        font-size: $font-size-sm;
        font-weight: 600;
        color: $text-primary;
      }
    }
  }

  .diet-description {
    font-size: $font-size-base;
    color: $text-regular;
    margin-bottom: $spacing-lg;
    line-height: 1.6;
  }

  .meal-list {
    .meal-list-title {
      display: block;
      font-size: $font-size-base;
      font-weight: 600;
      color: $text-regular;
      margin-bottom: $spacing-sm;
    }

    .meal-item {
      display: flex;
      padding: $spacing-sm 0;
      border-bottom: 1px solid $divider-color;

      &:last-child { border-bottom: none; }

      .meal-time {
        width: 60px;
        font-size: $font-size-base;
        color: $text-secondary;
        flex-shrink: 0;
        font-weight: 500;
      }

      .meal-content {
        flex: 1;
        font-size: $font-size-base;
        color: $text-primary;
      }
    }
  }
}
</style>
