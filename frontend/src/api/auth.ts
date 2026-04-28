// 认证相关 API

import { post, get } from './index'
import type { WechatLoginResponse, UserInfo } from '@/types/api'

// 微信登录
export function wechatLogin(code: string, nickname?: string, avatarUrl?: string): Promise<WechatLoginResponse> {
  return post('/v1/auth/wechat-login', {
    code,
    nickname,
    avatar_url: avatarUrl,
  })
}

// 刷新 token
export function refreshToken(refreshToken: string): Promise<WechatLoginResponse> {
  return post('/v1/auth/refresh', {
    refresh_token: refreshToken,
  })
}

// 获取用户资料
export function getProfile(): Promise<UserInfo> {
  return get('/v1/auth/profile')
}

// 登出
export function logout(sessionId: string): Promise<{ success: boolean; message: string }> {
  return post('/v1/auth/logout', {
    session_id: sessionId,
  })
}
