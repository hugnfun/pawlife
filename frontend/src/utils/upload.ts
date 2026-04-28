/**
 * 文件上传工具类
 * 支持图片和音频上传到后端 COS 服务
 */

interface UploadOptions {
  filePath: string
  type?: 'image' | 'audio'  // 默认 image
  onProgress?: (progress: number) => void
}

interface UploadResult {
  url: string
  key: string
  file_type: string
  file_size: number
}

/**
 * 上传图片到后端
 */
export async function uploadImage(options: Omit<UploadOptions, 'type'>): Promise<UploadResult> {
  return uploadFile({ ...options, type: 'image' })
}

/**
 * 上传音频到后端
 */
export async function uploadAudio(options: Omit<UploadOptions, 'type'>): Promise<UploadResult> {
  return uploadFile({ ...options, type: 'audio' })
}

/**
 * 上传文件到后端
 * 微信小程序使用 uni.uploadFile
 * H5 使用 fetch + FormData
 */
export async function uploadFile(options: UploadOptions): Promise<UploadResult> {
  const { filePath, type = 'image', onProgress } = options

  const token = uni.getStorageSync('access_token')
  if (!token) {
    throw new Error('请先登录')
  }

  const uploadUrl = `${getBaseUrl()}/v1/upload/${type}`

  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    const uploadTask = uni.uploadFile({
      url: uploadUrl,
      filePath,
      name: 'file',
      header: {
        Authorization: `Bearer ${token}`,
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const data = typeof res.data === 'string' ? JSON.parse(res.data) : res.data
            resolve({
              url: data.url,
              key: data.key,
              file_type: data.file_type || type,
              file_size: data.file_size || 0,
            })
          } catch {
            reject(new Error('解析上传响应失败'))
          }
        } else {
          reject(new Error(`上传失败 (${res.statusCode})`))
        }
      },
      fail: (err) => {
        reject(new Error(err.errMsg || '上传失败'))
      },
    })

    if (onProgress) {
      uploadTask.onProgressUpdate((res: any) => {
        onProgress(res.progress)
      })
    }
  })
  // #endif

  // #ifdef H5
  return new Promise(async (resolve, reject) => {
    try {
      const formData = new FormData()

      // H5 端处理 blob URL / data URL / 普通文件路径
      if (filePath.startsWith('blob:') || filePath.startsWith('data:')) {
        const response = await fetch(filePath)
        const blob = await response.blob()
        const ext = type === 'audio' ? 'm4a' : 'jpg'
        formData.append('file', blob, `upload.${ext}`)
      } else {
        // 对于普通路径，创建空 blob（H5 环境中通常不会到这里）
        formData.append('file', new Blob(), `upload.${type === 'audio' ? 'm4a' : 'jpg'}`)
      }

      const response = await fetch(uploadUrl, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      })

      if (!response.ok) {
        reject(new Error(`上传失败 (${response.status})`))
        return
      }

      const data = await response.json()
      resolve({
        url: data.url,
        key: data.key,
        file_type: data.file_type || type,
        file_size: data.file_size || 0,
      })
    } catch (err: any) {
      reject(new Error(err.message || '上传失败'))
    }
  })
  // #endif
}

/**
 * 获取 API 基础 URL
 */
function getBaseUrl(): string {
  // #ifdef H5
  return import.meta.env.VITE_API_BASE_URL || '/api'
  // #endif
  // #ifdef MP-WEIXIN
  return 'http://localhost:8000/api'
  // #endif
  return '/api'
}
