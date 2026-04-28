// 家庭组相关 API

import { get, post } from './index'
import type { Family, FamilyMember } from '@/types/api'

// 获取我的家庭组列表
export function getMyFamilies(): Promise<Family[]> {
  return get('/v1/families/')
}

// 获取家庭组详情
export function getFamilyDetail(familyId: string): Promise<Family> {
  return get(`/v1/families/${familyId}`)
}

// 获取家庭成员列表
export function getFamilyMembers(familyId: string): Promise<FamilyMember[]> {
  return get(`/v1/families/${familyId}/members`)
}

// 创建家庭组
export function createFamily(name: string): Promise<Family> {
  return post('/v1/families/', { name })
}

// 通过邀请码加入家庭组
export function joinFamily(inviteCode: string): Promise<{ success: boolean; family: Family }> {
  return post('/v1/families/join', { invite_code: inviteCode })
}

// 获取邀请信息（邀请码 + 二维码 URL）
export function getFamilyInviteInfo(familyId: string): Promise<{
  invite_code: string
  qr_url: string
  expires_at: string
}> {
  return get(`/v1/families/${familyId}/invite`)
}
