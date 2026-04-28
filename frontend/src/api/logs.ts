// 记录相关 API

import { get } from './index'
import type { MealLog } from '@/types/api'

// 获取时间线记录
export function getTimeline(params: {
  page?: number
  page_size?: number
  pet_id?: string
}): Promise<{ list: MealLog[]; total: number }> {
  // 微信小程序不支持 URLSearchParams，手动拼接查询字符串
  const parts: string[] = []
  if (params.page) parts.push(`page=${params.page}`)
  if (params.page_size) parts.push(`page_size=${params.page_size}`)
  if (params.pet_id) parts.push(`pet_id=${params.pet_id}`)
  const query = parts.length ? `?${parts.join('&')}` : ''

  return get(`/v1/logs/timeline${query}`)
}

// 获取饮食记录
export function getMealLogs(petId: string): Promise<MealLog[]> {
  return get(`/v1/logs/meals?pet_id=${petId}`)
}

// 删除饮食记录
export function deleteMealLog(id: string): Promise<{ success: boolean }> {
  return get(`/v1/logs/meals/${id}/delete`)
}

// 获取今日统计
export function getTodayStats(petId: string): Promise<{
  total_calories: number
  nutrition_completeness: number
}> {
  return get(`/v1/logs/today-stats?pet_id=${petId}`)
}
