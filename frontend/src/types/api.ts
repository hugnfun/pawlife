// API 相关类型定义

// 微信登录响应
export interface WechatLoginResponse {
  success: boolean
  message: string
  data: UserInfo
  token: TokenData
}

// Token 数据
export interface TokenData {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  session_id: string
}

// 用户信息
export interface UserInfo {
  id: string
  nickname: string
  avatar_url?: string
  wechat_openid: string
  is_active: boolean
  created_at: string
}

// 对话消息
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  tool_calls?: any[]
  suggestions?: string[]
}

// AI 对话请求
export interface AIConversationRequest {
  message: string
  message_type: 'text' | 'voice' | 'image'
  session_id?: string
  pet_id?: string
}

// AI 对话响应
export interface AIConversationResponse {
  response: string
  session_id: string
  tool_calls?: any[]
  pet_id?: string
  suggestions?: string[]
}

// 宠物信息
export interface Pet {
  id: string
  name: string
  species: 'dog' | 'cat' | 'other'
  breed?: string
  gender: 'male' | 'female'
  birthday?: string
  current_weight?: number
  ideal_weight?: number
  avatar_url?: string
  is_active: boolean
  owner_id: string
  created_at: string
}

// 饮食记录
export interface MealLog {
  id: string
  pet_id: string
  food_name: string
  food_type: 'main' | 'snack' | 'treat'
  amount: number
  unit: string
  notes?: string
  image_url?: string
  operator_nickname?: string
  created_at: string
}

// 疫苗记录
export interface VaccineRecord {
  id: string
  pet_id: string
  vaccine_name: string
  vaccine_type: string
  vaccine_date: string
  next_dose_date?: string
  notes?: string
  created_at: string
}

// 饮食方案
export interface DietRecipe {
  id: string
  pet_id: string
  name: string
  description: string
  daily_calories: number
  protein_ratio: number
  fat_ratio: number
  carb_ratio: number
  meals: Array<{
    time: string
    food: string
    amount: number
    unit: string
  }>
  is_active: boolean
  created_at: string
  updated_at: string
}

// 家庭信息
export interface Family {
  id: string
  name: string
  invite_code: string
  created_at: string
}

// 家庭成员
export interface FamilyMember {
  user_id: string
  family_id: string
  role: 'OWNER' | 'MEMBER'
  joined_at: string
  nickname: string
  avatar_url?: string
}

// 推送设置
export interface PushSettings {
  daily_summary: boolean
  feeding_reminder: boolean
  weight_reminder: boolean
  vaccine_reminder: boolean
  health_alert: boolean
}
