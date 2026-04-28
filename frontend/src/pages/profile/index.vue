<script setup lang="ts">
/**
 * 宠物档案页
 * 展示当前用户的所有宠物，支持切换活跃宠物
 */
import { ref, onMounted } from 'vue'
import { usePetStore } from '@/stores/pet'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { switchActivePet } from '@/api/pet'
import type { Pet } from '@/types/api'

const petStore = usePetStore()
const chatStore = useChatStore()
const authStore = useAuthStore()

// 加载状态
const loading = ref(false)

// 切换活跃宠物
async function handleSwitchActive(pet: Pet) {
  if (pet.is_active) {
    chatStore.setActivePet(pet.id)
    uni.showToast({ title: `已切换到 ${pet.name}`, icon: 'success' })
    return
  }

  try {
    loading.value = true
    await switchActivePet(pet.id)
    petStore.updatePet(pet.id, { is_active: true })
    chatStore.setActivePet(pet.id)

    // 更新其他宠物为非活跃
    petStore.pets.forEach(p => {
      if (p.id !== pet.id && p.is_active) {
        petStore.updatePet(p.id, { is_active: false })
      }
    })

    uni.showToast({ title: `已切换到 ${pet.name}`, icon: 'success' })
  } catch (error) {
    console.error('切换失败:', error)
    uni.showToast({ title: '切换失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

// 添加宠物
function addNewPet() {
  uni.navigateTo({ url: '/pages/pet-edit/index?mode=add' })
}

// 编辑宠物
function editPet(pet: Pet) {
  uni.navigateTo({ url: `/pages/pet-edit/index?mode=edit&id=${pet.id}` })
}

// 生成健康报告
function generateReport(pet: Pet) {
  uni.navigateTo({ url: `/pages/pet-profile/index?id=${pet.id}&action=report` })
}

// 退出登录
function logout() {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) {
        authStore.logout()
        uni.reLaunch({ url: '/pages/login/index' })
      }
    },
  })
}

onMounted(() => {
  petStore.fetchMyPets()
  authStore.restoreFromStorage()
})
</script>

<template>
  <view class="profile-page">
    <!-- 用户信息头部 -->
    <view class="user-header card">
      <view class="user-avatar" v-if="authStore.userInfo?.avatar_url">
        <image :src="authStore.userInfo?.avatar_url" mode="aspectFill" />
      </view>
      <view class="user-avatar default-avatar" v-else>
        <text>🐾</text>
      </view>
      <view class="user-info">
        <text class="user-nickname">{{ authStore.userInfo?.nickname || '未登录' }}</text>
        <text class="user-desc">PawLife 用户</text>
      </view>
      <button class="logout-btn" @click="logout">退出</button>
    </view>

    <!-- 宠物列表 -->
    <view class="section-title">
      <text>我的宠物 ({{ petStore.pets.length }})</text>
      <button class="add-btn" @click="addNewPet">+ 添加</button>
    </view>

    <view class="pet-list">
      <view
        v-for="(pet, index) in petStore.pets"
        :key="pet.id"
        :class="['pet-card card', { active: pet.is_active }]"
      >
        <view class="pet-header">
          <view class="pet-avatar" v-if="pet.avatar_url">
            <image :src="pet.avatar_url" mode="aspectFill" />
          </view>
          <view class="pet-avatar default-pet-avatar" v-else>
            <text v-if="pet.species === 'dog'">🐶</text>
            <text v-else-if="pet.species === 'cat'">🐱</text>
            <text v-else>🐾</text>
          </view>
          <view class="pet-info">
            <view class="pet-name-row">
              <text class="pet-name">{{ pet.name }}</text>
              <text v-if="pet.is_active" class="active-badge">当前活跃</text>
            </view>
            <text class="pet-meta">
              {{ pet.breed || (pet.species === 'dog' ? '狗狗' : pet.species === 'cat' ? '猫咪' : '宠物') }}
              <text v-if="pet.current_weight"> · {{ pet.current_weight }}kg</text>
            </text>
          </view>
          <view class="pet-actions">
            <button class="action-btn" @click.stop="editPet(pet)">✏️</button>
            <button class="action-btn" @click.stop="generateReport(pet)">📊</button>
          </view>
        </view>

        <view class="pet-stats">
          <view class="stat-item">
            <text class="stat-value">{{ pet.current_weight || '-' }}</text>
            <text class="stat-label">当前体重 kg</text>
          </view>
          <view class="stat-item">
            <text class="stat-value">{{ pet.ideal_weight || '-' }}</text>
            <text class="stat-label">理想体重 kg</text>
          </view>
          <view class="stat-item">
            <text class="stat-value gender-text">{{ pet.gender === 'male' ? '公' : '母' }}</text>
            <text class="stat-label">性别</text>
          </view>
        </view>

        <view class="pet-footer">
          <button
            v-if="!pet.is_active"
            class="switch-btn btn btn-primary"
            :disabled="loading"
            @click="handleSwitchActive(pet)"
          >
            设为活跃
          </button>
          <text v-else class="active-text">✅ 当前对话默认使用此宠物</text>
        </view>
      </view>

      <!-- 空状态 -->
      <view class="empty-state" v-if="petStore.pets.length === 0 && !petStore.loading">
        <text class="empty-icon">🐾</text>
        <text class="empty-text">还没有添加宠物</text>
        <text class="empty-hint">添加你的爱宠，开始健康管理</text>
        <button class="btn btn-primary mt-4" @click="addNewPet">立即添加</button>
      </view>
    </view>

    <!-- 家庭组信息 -->
    <view class="section">
      <view class="section-title">
        <text>家庭协作</text>
      </view>
      <view class="card family-card">
        <text class="family-placeholder">绑定家庭组后可多人共同管理宠物</text>
        <button class="btn btn-outline">查看我的家庭</button>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.profile-page {
  min-height: 100vh;
  background-color: $bg-page;
  padding: $spacing-md;
}

.user-header {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  margin-bottom: $spacing-lg;

  .user-avatar {
    width: 60px;
    height: 60px;
    border-radius: $radius-full;
    overflow: hidden;

    image {
      width: 100%;
      height: 100%;
    }

    &.default-avatar {
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, $primary-color-light, $primary-color-lighter);
      font-size: 24px;
    }
  }

  .user-info {
    flex: 1;

    .user-nickname {
      display: block;
      font-size: 18px;
      font-weight: 600;
      color: $text-primary;
      margin-bottom: $spacing-xs;
    }

    .user-desc {
      font-size: $font-size-md;
      color: $text-secondary;
    }
  }

  .logout-btn {
    padding: 6px 14px;
    font-size: $font-size-md;
    border-radius: $radius-sm;
    background-color: $error-color-light;
    color: $error-color;
    line-height: 1.2;
    font-weight: 500;
  }
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: $spacing-md 0 $spacing-sm;
  font-size: $font-size-lg;
  font-weight: 600;
  color: $text-primary;

  .add-btn {
    padding: 4px 14px;
    font-size: $font-size-md;
    color: $primary-color;
    border-radius: $radius-md;
    background-color: $primary-color-light;
    line-height: 1.4;
    font-weight: 500;
  }
}

.pet-list {
  margin-bottom: $spacing-lg;
}

.pet-card {
  margin-bottom: $spacing-md;
  border-left: 4px solid transparent;
  transition: all 0.25s ease;

  &.active {
    border-left-color: $primary-color;
    background: linear-gradient(135deg, white 0%, $primary-color-lighter 100%);
  }

  .pet-header {
    display: flex;
    align-items: center;
    gap: $spacing-md;
    margin-bottom: $spacing-md;

    .pet-avatar {
      width: 48px;
      height: 48px;
      border-radius: $radius-full;
      overflow: hidden;

      image {
        width: 100%;
        height: 100%;
      }

      &.default-pet-avatar {
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: $bg-page;
        font-size: 24px;
      }
    }

    .pet-info {
      flex: 1;

      .pet-name-row {
        display: flex;
        align-items: center;
        gap: $spacing-sm;
        margin-bottom: $spacing-xs;

        .pet-name {
          font-size: $font-size-lg;
          font-weight: 600;
          color: $text-primary;
        }

        .active-badge {
          font-size: $font-size-xs;
          padding: 2px 8px;
          background: linear-gradient(135deg, $success-color, darken(#95D5B2, 10%));
          color: white;
          border-radius: $radius-xs;
          font-weight: 500;
        }
      }

      .pet-meta {
        font-size: $font-size-md;
        color: $text-secondary;
      }
    }

    .pet-actions {
      display: flex;
      gap: $spacing-xs;

      .action-btn {
        width: 34px;
        height: 34px;
        line-height: 34px;
        padding: 0;
        border-radius: $radius-sm;
        background-color: $bg-page;
        font-size: 16px;

        &:active {
          background-color: $bg-hover;
        }
      }
    }
  }

  .pet-stats {
    display: flex;
    gap: $spacing-lg;
    padding: $spacing-md 0;
    border-top: 1px solid $divider-color;
    border-bottom: 1px solid $divider-color;
    margin-bottom: $spacing-md;

    .stat-item {
      flex: 1;
      text-align: center;

      .stat-value {
        display: block;
        font-size: $font-size-lg;
        font-weight: 600;
        color: $text-primary;
        margin-bottom: 2px;

        &.gender-text {
          color: $primary-color;
        }
      }

      .stat-label {
        font-size: $font-size-sm;
        color: $text-secondary;
      }
    }
  }

  .pet-footer {
    text-align: right;

    .switch-btn {
      padding: 6px 18px;
    }

    .active-text {
      font-size: $font-size-md;
      color: $success-color;
      font-weight: 500;
    }
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;

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
    margin-bottom: $spacing-xl;
  }
}

.family-card {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .family-placeholder {
    font-size: $font-size-base;
    color: $text-secondary;
  }
}

.mt-4 {
  margin-top: $spacing-lg;
}
</style>
