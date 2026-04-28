// 宠物相关 API

import { get, post, put, del } from './index'
import type { Pet } from '@/types/api'

// 获取我的宠物列表
export function getMyPets(): Promise<Pet[]> {
  return get('/v1/pets')
}

// 获取宠物详情
export function getPetDetail(petId: string): Promise<Pet> {
  return get(`/v1/pets/${petId}`)
}

// 创建宠物
export function createPet(data: Omit<Pet, 'id' | 'created_at'>): Promise<Pet> {
  return post('/v1/pets', data)
}

// 更新宠物
export function updatePet(petId: string, data: Partial<Pet>): Promise<Pet> {
  return put(`/v1/pets/${petId}`, data)
}

// 删除宠物
export function deletePet(petId: string): Promise<{ success: boolean }> {
  return del(`/v1/pets/${petId}`)
}

// 切换活跃宠物
export function switchActivePet(petId: string): Promise<{ success: boolean }> {
  return post(`/v1/pets/${petId}/active`)
}
