<script setup lang="ts">
/**
 * 我的账户页面
 * 家庭成员管理、推送设置、退出登录等功能
 */
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getFamilyMembers, getPushSettings, updatePushSettings } from '@/api/account'
import { getMyFamilies, createFamily, joinFamily, getFamilyInviteInfo } from '@/api/family'
import type { FamilyMember, PushSettings, Family } from '@/types/api'

const authStore = useAuthStore()

// 状态
const loading = ref(false)
const familyMembers = ref<FamilyMember[]>([])
const myFamilies = ref<Family[]>([])
const currentFamilyId = ref<string>('')
const pushSettings = ref<PushSettings>({
  daily_summary: true,
  feeding_reminder: false,
  weight_reminder: false,
  vaccine_reminder: true,
  health_alert: true,
})

// 邀请码弹窗状态
const showInviteModal = ref(false)
const inviteCode = ref('')
const inviteQrUrl = ref('')
const inviteLoading = ref(false)

// 加入家庭弹窗状态
const showJoinModal = ref(false)
const joinCode = ref('')
const joinLoading = ref(false)

// 创建家庭弹窗状态
const showCreateModal = ref(false)
const newFamilyName = ref('')
const createLoading = ref(false)

// 加载数据
async function loadData() {
  loading.value = true
  try {
    // 加载家庭列表
    const families = await getMyFamilies()
    myFamilies.value = families
    if (families.length > 0) {
      currentFamilyId.value = families[0].id
    }

    // 加载家庭成员
    const members = await getFamilyMembers()
    familyMembers.value = members

    // 加载推送设置
    const settings = await getPushSettings()
    pushSettings.value = { ...pushSettings.value, ...settings }
  } catch (error) {
    console.error('加载数据失败:', error)
    // 静默失败，不阻塞页面
  } finally {
    loading.value = false
  }
}

// 保存推送设置
async function savePushSettings() {
  try {
    await updatePushSettings(pushSettings.value)
    uni.showToast({ title: '保存成功', icon: 'success' })
  } catch (error) {
    console.error('保存失败:', error)
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

// 邀请成员 — 获取邀请码 + 二维码
async function inviteMember() {
  if (!currentFamilyId.value) {
    uni.showToast({ title: '请先创建或加入家庭', icon: 'none' })
    return
  }

  inviteLoading.value = true
  showInviteModal.value = true
  try {
    const result = await getFamilyInviteInfo(currentFamilyId.value)
    inviteCode.value = result.invite_code
    inviteQrUrl.value = result.qr_url
  } catch (error: any) {
    console.error('获取邀请码失败:', error)
    uni.showToast({ title: error.message || '获取邀请码失败', icon: 'none' })
    showInviteModal.value = false
  } finally {
    inviteLoading.value = false
  }
}

// 复制邀请码
function copyInviteCode() {
  uni.setClipboardData({
    data: inviteCode.value,
    success: () => {
      uni.showToast({ title: '已复制邀请码', icon: 'success' })
    },
  })
}

// 关闭邀请弹窗
function closeInviteModal() {
  showInviteModal.value = false
  inviteCode.value = ''
  inviteQrUrl.value = ''
}

// 打开加入家庭弹窗
function openJoinModal() {
  joinCode.value = ''
  showJoinModal.value = true
}

// 加入家庭
async function handleJoinFamily() {
  const code = joinCode.value.trim()
  if (!code) {
    uni.showToast({ title: '请输入邀请码', icon: 'none' })
    return
  }
  if (code.length !== 6) {
    uni.showToast({ title: '邀请码为 6 位', icon: 'none' })
    return
  }

  joinLoading.value = true
  try {
    const result = await joinFamily(code)
    uni.showToast({ title: '加入成功', icon: 'success' })
    showJoinModal.value = false
    // 刷新数据
    await loadData()
  } catch (error: any) {
    console.error('加入家庭失败:', error)
    uni.showToast({ title: error.message || '加入失败，请检查邀请码', icon: 'none' })
  } finally {
    joinLoading.value = false
  }
}

// 打开创建家庭弹窗
function openCreateModal() {
  newFamilyName.value = ''
  showCreateModal.value = true
}

// 创建家庭
async function handleCreateFamily() {
  const name = newFamilyName.value.trim()
  if (!name) {
    uni.showToast({ title: '请输入家庭名称', icon: 'none' })
    return
  }

  createLoading.value = true
  try {
    const family = await createFamily(name)
    uni.showToast({ title: '创建成功', icon: 'success' })
    showCreateModal.value = false
    currentFamilyId.value = family.id
    await loadData()
  } catch (error: any) {
    console.error('创建家庭失败:', error)
    uni.showToast({ title: error.message || '创建失败', icon: 'none' })
  } finally {
    createLoading.value = false
  }
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
  authStore.restoreFromStorage()
  loadData()
})
</script>

<template>
  <view class="account-page">
    <!-- 用户信息头部 -->
    <view class="user-section card">
      <view class="user-section-bg"></view>
      <view class="user-info">
        <view class="user-avatar" v-if="authStore.userInfo?.avatar_url">
          <image :src="authStore.userInfo?.avatar_url" mode="aspectFill" />
        </view>
        <view class="user-avatar default-avatar" v-else>
          <text>🐾</text>
        </view>
        <view class="user-text">
          <text class="user-nickname">{{ authStore.userInfo?.nickname || '未登录' }}</text>
          <text class="user-desc">PawLife 用户</text>
        </view>
      </view>
    </view>

    <!-- 家庭成员管理 -->
    <view class="section card">
      <view class="section-header">
        <view class="title-with-accent">
          <view class="accent-bar"></view>
          <text class="section-title">家庭成员</text>
        </view>
        <view class="header-actions">
          <button class="action-link" @click="openJoinModal">加入</button>
          <button class="action-link" @click="openCreateModal">创建</button>
          <button class="invite-btn" @click="inviteMember" :disabled="!currentFamilyId">+ 邀请</button>
        </view>
      </view>

      <!-- 当前家庭名称 -->
      <view v-if="myFamilies.length > 0" class="current-family">
        <text class="family-name">🏠 {{ myFamilies[0]?.name || '我的家庭' }}</text>
      </view>

      <view class="member-list" v-if="familyMembers.length > 0">
        <view v-for="member in familyMembers" :key="member.user_id" class="member-item">
          <view class="member-avatar" v-if="member.avatar_url">
            <image :src="member.avatar_url" mode="aspectFill" />
          </view>
          <view class="member-avatar default-avatar" v-else>
            <text>👤</text>
          </view>
          <view class="member-info">
            <text class="member-name">{{ member.nickname }}</text>
            <text class="member-role" :class="{ owner: member.role === 'OWNER' }">
              {{ member.role === 'OWNER' ? '创建者' : '成员' }}
            </text>
          </view>
        </view>
      </view>
      <view class="empty-hint" v-else>
        暂无其他家庭成员
      </view>
    </view>

    <!-- 推送设置 -->
    <view class="section card">
      <view class="section-header">
        <view class="title-with-accent">
          <view class="accent-bar accent-secondary"></view>
          <text class="section-title">推送通知设置</text>
        </view>
      </view>
      <view class="setting-list">
        <view class="setting-item">
          <view class="setting-info">
            <text class="setting-name">每日健康晨报</text>
            <text class="setting-desc">每天早上推送昨日健康总结</text>
          </view>
          <switch :checked="pushSettings.daily_summary" @change="pushSettings.daily_summary = $event.detail.value" color="#FF8C69" />
        </view>
        <view class="setting-item">
          <view class="setting-info">
            <text class="setting-name">喂食提醒</text>
            <text class="setting-desc">到饭点提醒喂食</text>
          </view>
          <switch :checked="pushSettings.feeding_reminder" @change="pushSettings.feeding_reminder = $event.detail.value" color="#FF8C69" />
        </view>
        <view class="setting-item">
          <view class="setting-info">
            <text class="setting-name">体重记录提醒</text>
            <text class="setting-desc">每周提醒称重</text>
          </view>
          <switch :checked="pushSettings.weight_reminder" @change="pushSettings.weight_reminder = $event.detail.value" color="#FF8C69" />
        </view>
        <view class="setting-item">
          <view class="setting-info">
            <text class="setting-name">疫苗接种提醒</text>
            <text class="setting-desc">临近下次疫苗接种时提醒</text>
          </view>
          <switch :checked="pushSettings.vaccine_reminder" @change="pushSettings.vaccine_reminder = $event.detail.value" color="#FF8C69" />
        </view>
        <view class="setting-item">
          <view class="setting-info">
            <text class="setting-name">健康异常预警</text>
            <text class="setting-desc">发现健康风险时及时通知</text>
          </view>
          <switch :checked="pushSettings.health_alert" @change="pushSettings.health_alert = $event.detail.value" color="#FF8C69" />
        </view>
      </view>
      <button class="save-btn" @click="savePushSettings">保存设置</button>
    </view>

    <!-- 退出登录 -->
    <view class="section card">
      <button class="logout-btn" @click="logout">退出登录</button>
    </view>

    <!-- 邀请码弹窗 -->
    <view v-if="showInviteModal" class="modal-mask" @click="closeInviteModal">
      <view class="modal-content" @click.stop>
        <view class="modal-title">邀请家庭成员</view>
        <view v-if="inviteLoading" class="modal-loading">
          <view class="loading-spinner"></view>
          <text>加载中...</text>
        </view>
        <view v-else class="invite-detail">
          <view class="invite-code-row">
            <text class="invite-code-label">邀请码</text>
            <view class="invite-code-value">
              <text class="code-text">{{ inviteCode }}</text>
              <button class="copy-btn" @click="copyInviteCode">复制</button>
            </view>
          </view>
          <view class="qr-container" v-if="inviteQrUrl">
            <image :src="inviteQrUrl" mode="aspectFit" class="qr-image" />
            <text class="qr-hint">扫描二维码加入家庭</text>
          </view>
        </view>
        <button class="modal-close-btn" @click="closeInviteModal">关闭</button>
      </view>
    </view>

    <!-- 加入家庭弹窗 -->
    <view v-if="showJoinModal" class="modal-mask" @click="showJoinModal = false">
      <view class="modal-content" @click.stop>
        <view class="modal-title">加入家庭</view>
        <input
          v-model="joinCode"
          class="modal-input"
          type="text"
          placeholder="请输入 6 位邀请码"
          maxlength="6"
        />
        <view class="modal-actions">
          <button class="modal-btn" @click="showJoinModal = false">取消</button>
          <button class="modal-btn primary" :disabled="joinLoading" @click="handleJoinFamily">
            {{ joinLoading ? '加入中...' : '加入' }}
          </button>
        </view>
      </view>
    </view>

    <!-- 创建家庭弹窗 -->
    <view v-if="showCreateModal" class="modal-mask" @click="showCreateModal = false">
      <view class="modal-content" @click.stop>
        <view class="modal-title">创建家庭</view>
        <input
          v-model="newFamilyName"
          class="modal-input"
          type="text"
          placeholder="输入家庭名称"
          maxlength="20"
        />
        <view class="modal-actions">
          <button class="modal-btn" @click="showCreateModal = false">取消</button>
          <button class="modal-btn primary" :disabled="createLoading" @click="handleCreateFamily">
            {{ createLoading ? '创建中...' : '创建' }}
          </button>
        </view>
      </view>
    </view>

    <!-- 加载状态 -->
    <view class="loading-mask" v-if="loading">
      <view class="loading-spinner"></view>
      <text>加载中...</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.account-page {
  min-height: 100vh;
  background-color: $bg-page;
  padding: $spacing-md;
  padding-bottom: 40px;
}

.title-with-accent {
  display: flex;
  align-items: center;
  gap: $spacing-sm;

  .accent-bar {
    width: 4px;
    height: 18px;
    border-radius: 2px;
    background: $primary-color;

    &.accent-secondary { background: $secondary-color; }
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

    .invite-btn {
      font-size: $font-size-base;
      color: white;
      background: linear-gradient(135deg, $primary-color, $primary-color-dark);
      border: none;
      padding: 4px 14px;
      line-height: 24px;
      border-radius: $radius-xs;
      font-weight: 500;

      &::after { border: none; }
      &[disabled] { opacity: 0.5; }
    }
  }
}

.user-section {
  position: relative;
  overflow: hidden;
  margin-bottom: $spacing-lg;

  .user-section-bg {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 60px;
    background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
    border-radius: $radius-md $radius-md 0 0;
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: $spacing-md;
    position: relative;
    z-index: 1;
    padding-top: 12px;

    .user-avatar {
      width: 60px;
      height: 60px;
      border-radius: $radius-full;
      overflow: hidden;
      border: 3px solid white;
      box-shadow: $shadow-sm;

      image {
        width: 100%;
        height: 100%;
      }

      &.default-avatar {
        display: flex;
        align-items: center;
        justify-content: center;
        background: $bg-page;
        font-size: 24px;
      }
    }

    .user-text {
      .user-nickname {
        display: block;
        font-size: 18px;
        font-weight: 600;
        color: $text-primary;
        margin-bottom: $spacing-xs;
      }

      .user-desc {
        font-size: $font-size-base;
        color: $text-secondary;
      }
    }
  }
}

.header-actions {
  display: flex;
  gap: $spacing-sm;
  align-items: center;

  .action-link {
    font-size: $font-size-md;
    color: $text-regular;
    background: none;
    border: none;
    padding: 4px 8px;
    line-height: 24px;
    font-weight: 500;

    &::after { border: none; }
  }
}

.current-family {
  margin-bottom: $spacing-md;
  .family-name {
    font-size: $font-size-base;
    color: $text-regular;
  }
}

.member-list {
  .member-item {
    display: flex;
    align-items: center;
    padding: $spacing-md 0;
    border-bottom: 1px solid $divider-color;

    &:last-child { border-bottom: none; }

    .member-avatar {
      width: 44px;
      height: 44px;
      border-radius: $radius-full;
      overflow: hidden;
      margin-right: $spacing-md;
      flex-shrink: 0;

      image {
        width: 100%;
        height: 100%;
      }

      &.default-avatar {
        display: flex;
        align-items: center;
        justify-content: center;
        background: $bg-page;
        font-size: 18px;
      }
    }

    .member-info {
      flex: 1;

      .member-name {
        display: block;
        font-size: $font-size-md;
        font-weight: 500;
        color: $text-primary;
        margin-bottom: $spacing-xs;
      }

      .member-role {
        font-size: $font-size-sm;
        padding: 2px 10px;
        background-color: $bg-page;
        color: $text-secondary;
        border-radius: $radius-xs;

        &.owner {
          background-color: $primary-color-light;
          color: $primary-color;
          font-weight: 500;
        }
      }
    }
  }
}

.empty-hint {
  text-align: center;
  color: $text-secondary;
  font-size: $font-size-base;
  padding: $spacing-xl 0;
}

.setting-list {
  .setting-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: $spacing-lg 0;
    border-bottom: 1px solid $divider-color;

    &:last-child { border-bottom: none; }

    .setting-info {
      flex: 1;

      .setting-name {
        display: block;
        font-size: $font-size-md;
        color: $text-primary;
        margin-bottom: $spacing-xs;
        font-weight: 500;
      }

      .setting-desc {
        font-size: $font-size-sm;
        color: $text-secondary;
      }
    }
  }
}

.save-btn {
  width: 100%;
  margin-top: $spacing-lg;
  background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
  color: white;
  border-radius: $radius-sm;
  line-height: 44px;
  font-size: $font-size-lg;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba($primary-color, 0.25);
  transition: all 0.2s;

  &:active { transform: scale(0.98); }
  &::after { border: none; }
}

.logout-btn {
  width: 100%;
  background-color: $error-color-light;
  color: $error-color;
  border-radius: $radius-sm;
  line-height: 44px;
  font-size: $font-size-lg;
  font-weight: 500;
  &::after { border: none; }
}

.loading-mask {
  text-align: center;
  padding: $spacing-xxxl * 2;
  color: $text-secondary;
  font-size: $font-size-base;
}

/* 弹窗样式 */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.45);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  animation: fade-in 0.2s ease;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-content {
  background-color: white;
  border-radius: $radius-md;
  padding: $spacing-xxl;
  width: 80%;
  max-width: 360px;
  animation: modal-slide-up 0.25s ease;
}

@keyframes modal-slide-up {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.modal-content {
  .modal-title {
    font-size: 18px;
    font-weight: 600;
    color: $text-primary;
    text-align: center;
    margin-bottom: $spacing-xl;
  }

  .modal-input {
    width: 100%;
    height: 48px;
    padding: 0 $spacing-md;
    font-size: $font-size-lg;
    background-color: $bg-page;
    border-radius: $radius-sm;
    border: 1px solid $border-color;
    box-sizing: border-box;
    letter-spacing: 4px;
    text-align: center;
    transition: border-color 0.2s;

    &:focus { border-color: $primary-color; }
  }

  .modal-loading {
    text-align: center;
    padding: $spacing-xl;
    color: $text-secondary;
  }

  .modal-actions {
    display: flex;
    gap: $spacing-md;
    margin-top: $spacing-xl;

    .modal-btn {
      flex: 1;
      height: 44px;
      line-height: 44px;
      border-radius: $radius-sm;
      font-size: $font-size-md;
      background-color: $bg-page;
      color: $text-regular;
      font-weight: 500;

      &.primary {
        background: linear-gradient(135deg, $primary-color, $primary-color-dark);
        color: white;
        box-shadow: 0 2px 8px rgba($primary-color, 0.25);

        &[disabled] { opacity: 0.6; }
      }

      &::after { border: none; }
    }
  }
}

.invite-detail {
  text-align: center;

  .invite-code-row {
    margin-bottom: $spacing-xl;

    .invite-code-label {
      display: block;
      font-size: $font-size-base;
      color: $text-regular;
      margin-bottom: $spacing-sm;
    }

    .invite-code-value {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: $spacing-md;

      .code-text {
        font-size: 36px;
        font-weight: 700;
        color: $primary-color;
        letter-spacing: 8px;
        font-variant-numeric: tabular-nums;
      }

      .copy-btn {
        font-size: $font-size-md;
        color: $primary-color;
        background-color: $primary-color-light;
        border-radius: $radius-xs;
        padding: 4px 14px;
        line-height: 1.4;
        font-weight: 500;

        &::after { border: none; }
      }
    }
  }

  .qr-container {
    .qr-image {
      width: 180px;
      height: 180px;
      margin: 0 auto $spacing-sm;
      border-radius: $radius-sm;
    }

    .qr-hint {
      font-size: $font-size-sm;
      color: $text-secondary;
    }
  }
}

.modal-close-btn {
  width: 100%;
  margin-top: $spacing-lg;
  background-color: $bg-page;
  color: $text-regular;
  border-radius: $radius-sm;
  line-height: 44px;
  font-size: $font-size-md;
  font-weight: 500;
  &::after { border: none; }
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid $divider-color;
  border-top-color: $primary-color;
  border-radius: $radius-full;
  margin: 0 auto $spacing-md;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
