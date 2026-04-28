// API 基础封装
// 使用 uni.request 兼容微信小程序

function resolveBaseUrl(): string {
  // #ifdef H5
  return import.meta.env.VITE_API_BASE_URL || '/api'
  // #endif
  // #ifdef MP-WEIXIN
  return 'http://localhost:8000/api'
  // #endif
  return '/api'
}

const BASE_URL = resolveBaseUrl()

// 请求拦截器
function request<T>(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET',
  data?: any
): Promise<T> {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('access_token')

    const header: Record<string, string> = {
      'Content-Type': 'application/json',
    }

    if (token) {
      header['Authorization'] = `Bearer ${token}`
    }

    uni.request({
      url: `${BASE_URL}${url}`,
      method,
      data,
      header,
      success: (res) => {
        if (res.statusCode === 401) {
          // 未授权，清除 token 跳转到登录
          uni.removeStorageSync('access_token')
          uni.removeStorageSync('refresh_token')
          uni.reLaunch({ url: '/pages/login/index' })
          reject(new Error('请重新登录'))
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`HTTP error! status: ${res.statusCode}`))
          return
        }
        resolve(res.data as T)
      },
      fail: (err) => {
        console.error('API 请求错误:', err)
        reject(err)
      },
    })
  })
}

// GET 请求
export function get<T = any>(url: string): Promise<T> {
  return request<T>(url, 'GET')
}

// POST 请求
export function post<T = any>(url: string, data?: any): Promise<T> {
  return request<T>(url, 'POST', data)
}

// PUT 请求
export function put<T = any>(url: string, data?: any): Promise<T> {
  return request<T>(url, 'PUT', data)
}

// DELETE 请求
export function del<T = any>(url: string): Promise<T> {
  return request<T>(url, 'DELETE')
}

export { request }
