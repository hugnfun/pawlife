// 宠物档案相关 API

import { get } from './index'
import type { Pet, VaccineRecord, DietRecipe } from '@/types/api'

// 获取宠物档案详情
export function getPetProfile(petId: string): Promise<Pet> {
  return get(`/v1/pet/${petId}/profile`)
}

// 获取疫苗记录列表
export function getVaccineRecords(petId: string): Promise<VaccineRecord[]> {
  return get(`/v1/pet/${petId}/vaccines`)
}

// 获取当前饮食方案
export function getDietRecipe(petId: string): Promise<DietRecipe | null> {
  return get(`/v1/pet/${petId}/diet-recipe`)
}
