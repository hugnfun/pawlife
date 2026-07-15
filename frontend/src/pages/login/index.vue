<script setup lang="ts">
/**
 * 登录页面
 * 微信小程序：调用 uni.login() 获取 code
 * H5：模拟登录（开发调试用）
 */
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const logging = ref(false)

async function handleLogin() {
  if (logging.value) return
  logging.value = true

  try {
    // #ifdef H5
    // H5 环境：模拟登录（开发调试用）
    await authStore.mockLogin()
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/chat/index' })
    }, 500)
    // #endif

    // #ifndef H5
    // 微信小程序：获取微信登录 code
    const loginRes = await new Promise<UniApp.LoginRes>((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: resolve,
        fail: (err) => reject(new Error(err.errMsg || '微信登录失败')),
      })
    })

    const code = loginRes.code
    if (!code) {
      uni.showToast({ title: '获取登录凭证失败', icon: 'none' })
      return
    }

    // 获取用户信息（昵称+头像）
    let nickname: string | undefined
    let avatarUrl: string | undefined
    try {
      const userInfoRes = await new Promise<UniApp.GetUserInfoRes>((resolve, reject) => {
        uni.getUserInfo({
          provider: 'weixin',
          success: resolve,
          fail: () => reject(null),
        })
      })
      nickname = userInfoRes.userInfo?.nickName
      avatarUrl = userInfoRes.userInfo?.avatarUrl
    } catch {
      // getUserInfo 可能被用户拒绝，不影响登录
    }

    // 发送到后端换取 token
    await authStore.loginByWechat(code, nickname, avatarUrl)

    uni.showToast({ title: '登录成功', icon: 'success' })

    // 跳转到首页
    setTimeout(() => {
      uni.switchTab({ url: '/pages/chat/index' })
    }, 500)
    // #endif
  } catch (error: any) {
    console.error('登录失败:', error)
    const msg = error?.message || '登录失败，请重试'
    uni.showToast({ title: msg, icon: 'none', duration: 3000 })
  } finally {
    logging.value = false
  }
}
</script>

<template>
  <view class="login-page">
    <!-- 装饰性散落爪印 -->
    <view class="paw-decor paw-1">🐾</view>
    <view class="paw-decor paw-2">🐾</view>
    <view class="paw-decor paw-3">🐾</view>
    <view class="paw-decor paw-4">🐾</view>

    <view class="login-container page-enter">
      <!-- Logo -->
      <view class="logo-section">
        <view class="logo-icon-wrap">
          <!-- SVG 爪印 Logo -->
          <view class="paw-logo">
            <view class="paw-pad"></view>
            <view class="paw-toe toe-1"></view>
            <view class="paw-toe toe-2"></view>
            <view class="paw-toe toe-3"></view>
            <view class="paw-toe toe-4"></view>
          </view>
        </view>
        <text class="app-name">PawLife</text>
        <text class="app-desc">AI Native 宠物健康管理</text>
      </view>

      <!-- 登录按钮 -->
      <button
        class="login-btn"
        :class="{ disabled: logging }"
        :disabled="logging"
        @click="handleLogin"
      >
        <text class="btn-text">{{ logging ? '登录中...' : '微信一键登录' }}</text>
      </button>

      <!-- 底部提示 -->
      <view class="login-footer">
        <text class="footer-text">登录即表示同意</text>
        <text class="footer-link">用户协议</text>
        <text class="footer-text">和</text>
        <text class="footer-link">隐私政策</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #FFF0EB 0%, #FFF7F4 30%, #FAF7F5 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

// 装饰性爪印
.paw-decor {
  position: absolute;
  font-size: 24px;
  opacity: 0.12;
  animation: float 6s ease-in-out infinite;
}

.paw-1 { top: 8%; left: 12%; animation-delay: 0s; font-size: 28px; }
.paw-2 { top: 15%; right: 18%; animation-delay: 1.5s; }
.paw-3 { bottom: 25%; left: 8%; animation-delay: 3s; font-size: 20px; }
.paw-4 { bottom: 18%; right: 10%; animation-delay: 4.5s; font-size: 32px; }

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-12px) rotate(8deg); }
}

.login-container {
  width: 100%;
  padding: 48px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  z-index: 1;
}

.logo-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 80px;

  .logo-icon-wrap {
    width: 100px;
    height: 100px;
    background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
    border-radius: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px rgba($primary-color, 0.3);
    animation: logo-bounce 2s ease-out;
  }

  .app-name {
    font-size: 36px;
    font-weight: 700;
    color: $text-primary;
    margin-bottom: 8px;
    letter-spacing: 1px;
  }

  .app-desc {
    font-size: 15px;
    color: $text-secondary;
    letter-spacing: 0.5px;
  }
}

// CSS 爪印 Logo
.paw-logo {
  position: relative;
  width: 48px;
  height: 48px;

  .paw-pad {
    position: absolute;
    bottom: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 28px;
    height: 22px;
    background: white;
    border-radius: 50% 50% 50% 50% / 40% 40% 60% 60%;
  }

  .paw-toe {
    position: absolute;
    width: 12px;
    height: 12px;
    background: white;
    border-radius: 50%;
  }

  .toe-1 { top: 2px; left: 4px; }
  .toe-2 { top: 0; left: 16px; }
  .toe-3 { top: 0; right: 16px; }
  .toe-4 { top: 2px; right: 4px; }
}

@keyframes logo-bounce {
  0% { transform: scale(0.5) translateY(20px); opacity: 0; }
  60% { transform: scale(1.05) translateY(-5px); }
  100% { transform: scale(1) translateY(0); opacity: 1; }
}

.login-btn {
  width: 100%;
  height: 52px;
  line-height: 52px;
  background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
  color: white;
  border-radius: 26px;
  font-size: 17px;
  font-weight: 500;
  border: none;
  box-shadow: 0 4px 16px rgba($primary-color, 0.35);
  transition: all 0.25s ease;

  &:active {
    transform: scale(0.97);
    box-shadow: 0 2px 8px rgba($primary-color, 0.25);
  }

  &.disabled {
    opacity: 0.6;
    transform: none;
  }

  &::after {
    border: none;
  }

  .btn-text {
    color: white;
    letter-spacing: 0.5px;
  }
}

.login-footer {
  margin-top: 32px;
  display: flex;
  align-items: center;
  gap: 4px;

  .footer-text {
    font-size: $font-size-sm;
    color: $text-secondary;
  }

  .footer-link {
    font-size: $font-size-sm;
    color: $primary-color;
    font-weight: 500;
  }
}
</style>
