// 账户相关 API

import { get, post } from './index'
import type { FamilyMember, PushSettings } from '@/types/api'

// 获取家庭成员列表
export function getFamilyMembers(): Promise<FamilyMember[]> {
  return get('/v1/account/family/members')
}

// 获取推送设置
export function getPushSettings(): Promise<PushSettings> {
  return get('/v1/account/push-settings')
}

// 更新推送设置
export function updatePushSettings(settings: PushSettings): Promise<{ success: boolean }> {
  return post('/v1/account/push-settings', settings)
}

// 生成邀请码
export function generateInviteCode(): Promise<{ invite_code: string }> {
  return get('/v1/account/family/invite')
}
