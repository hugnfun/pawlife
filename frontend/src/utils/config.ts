/**
 * 应用配置
 * 统一管理 API 基础 URL 等环境相关配置
 *
 * 微信小程序：根据账号环境自动选择 URL（develop/trial/release）
 * H5：使用 import.meta.env.VITE_API_BASE_URL
 */

// 微信小程序各环境 API URL
const MP_WEIXIN_URLS: Record<string, string> = {
  develop: 'http://localhost:8000/api',    // 开发版
  trial: 'https://staging-api.pawlife.com/api',    // 体验版
  release: 'https://api.pawlife.com/api',  // 正式版
}

/**
 * 获取 API 基础 URL
 * 根据运行环境自动选择正确的后端地址
 */
export function getApiBaseUrl(): string {
  // #ifdef H5
  return import.meta.env.VITE_API_BASE_URL || '/api'
  // #endif

  // #ifdef MP-WEIXIN
  // 微信小程序：根据账号信息判断环境
  try {
    const accountInfo = uni.getAccountInfoSync()
    const envVersion = accountInfo.miniProgram.envVersion || 'develop'
    return MP_WEIXIN_URLS[envVersion] || MP_WEIXIN_URLS.develop
  } catch {
    // 降级到开发环境
    return MP_WEIXIN_URLS.develop
  }
  // #endif

  // 其他平台降级
  return '/api'
}
