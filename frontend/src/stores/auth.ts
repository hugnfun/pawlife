// 认证状态 store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo } from '@/types/api'
import { wechatLogin as apiWechatLogin } from '@/api/auth'

export const useAuthStore = defineStore(
  'auth',
  () => {
    // 状态
    const userInfo = ref<UserInfo | null>(null)
    const accessToken = ref<string | null>(null)
    const refreshToken = ref<string | null>(null)
    const isLoggedIn = computed(() => !!accessToken.value && !!userInfo.value)

    // 登录
    async function loginByWechat(code: string, nickname?: string, avatarUrl?: string) {
      const response = await apiWechatLogin(code, nickname, avatarUrl)

      accessToken.value = response.token.access_token
      refreshToken.value = response.token.refresh_token
      userInfo.value = response.data

      // 保存到本地存储
      uni.setStorageSync('access_token', response.token.access_token)
      uni.setStorageSync('refresh_token', response.token.refresh_token)
      uni.setStorageSync('user_info', JSON.stringify(response.data))

      return response
    }

    // 登出
    function logout() {
      userInfo.value = null
      accessToken.value = null
      refreshToken.value = null

      // 清除本地存储
      uni.removeStorageSync('access_token')
      uni.removeStorageSync('refresh_token')
      uni.removeStorageSync('user_info')
    }

    // 从本地存储恢复状态
    function restoreFromStorage() {
      const token = uni.getStorageSync('access_token')
      const refresh = uni.getStorageSync('refresh_token')
      const user = uni.getStorageSync('user_info')

      if (token) {
        accessToken.value = token
      }
      if (refresh) {
        refreshToken.value = refresh
      }
      if (user) {
        try {
          userInfo.value = JSON.parse(user)
        } catch (e) {
          userInfo.value = null
        }
      }
    }

    // 更新用户信息
    function updateUserInfo(info: Partial<UserInfo>) {
      if (userInfo.value) {
        userInfo.value = { ...userInfo.value, ...info }
        uni.setStorageSync('user_info', JSON.stringify(userInfo.value))
      }
    }

    return {
      userInfo,
      accessToken,
      refreshToken,
      isLoggedIn,
      loginByWechat,
      logout,
      restoreFromStorage,
      updateUserInfo,
    }
  }
)
