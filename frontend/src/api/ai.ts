// AI 对话相关 API

import { post } from './index'

// AI 对话（非流式）- 使用真实 LangGraph Agent 路由
export function chatConversation(data: {
  message: string
  input_type?: 'text' | 'voice' | 'image'
  input_url?: string
  session_id?: string
  pet_id?: string
  onboarding_step?: string
  onboarding_data?: any
}): Promise<{ response: string; session_id: string; suggestions?: string[] }> {
  return post('/v1/chat/', data)
}

// 兼容旧接口名
export function aiConversation(data: any): Promise<any> {
  return chatConversation(data)
}

// 获取 SSE 流式对话连接 URL - 使用真实 LangGraph Agent 路由
export function getAIConversationStreamUrl(): string {
  // #ifdef H5
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
  // #endif
  // #ifdef MP-WEIXIN
  const baseUrl = 'http://localhost:8000/api'
  // #endif
  return `${baseUrl}/v1/chat/stream`
}

// 生成健康报告
export function generateHealthReport(petId: string, periodDays: number = 30, reportType: string = 'full') {
  return post('/v1/ai/health-report', {
    pet_id: petId,
    period_days: periodDays,
    report_type: reportType,
  })
}

// 营养分析
export function analyzeNutrition(mealLogId: string) {
  return post('/v1/ai/nutrition-analysis', {
    meal_log_id: mealLogId,
  })
}
