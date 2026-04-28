<script setup lang="ts">
// App 根组件
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app'

onLaunch(async () => {
  console.log('PawLife App Launch')

  // 尝试静默登录（微信小程序）
  // #ifdef MP-WEIXIN
  try {
    const token = uni.getStorageSync('access_token')
    if (!token) {
      // 没有缓存的 token，执行静默登录
      await silentLogin()
    }
  } catch (e) {
    console.error('静默登录失败:', e)
  }
  // #endif
})

/**
 * 微信小程序静默登录
 * 不需要用户手动点击，自动获取 code 换取 token
 */
async function silentLogin() {
  try {
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()

    const loginRes = await new Promise<UniApp.LoginRes>((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: resolve,
        fail: reject,
      })
    })

    if (loginRes.code) {
      await authStore.loginByWechat(loginRes.code)
      console.log('静默登录成功')
    }
  } catch (e) {
    // 静默登录失败不阻塞应用，后续需要登录时再跳转到登录页
    console.warn('静默登录失败，将在需要时跳转登录页:', e)
  }
}

onShow(() => {
  console.log('PawLife App Show')
})

onHide(() => {
  console.log('PawLife App Hide')
})
</script>

<template>
</template>

<style lang="scss">
/* 全局样式通过 vite.config.ts 自动注入 */
</style>
