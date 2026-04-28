/**
 * 录音工具类
 * 封装微信小程序 RecorderManager + H5 MediaRecorder 降级方案
 */

type RecordState = 'idle' | 'recording' | 'paused'

interface RecorderCallbacks {
  onStart?: () => void
  onStop?: (filePath: string, duration: number) => void
  onError?: (error: string) => void
  onDurationUpdate?: (duration: number) => void
}

class AudioRecorder {
  private state: RecordState = 'idle'
  private recorderManager: any = null
  private mediaRecorder: any = null
  private mediaChunks: any[] = []
  private mediaStream: any = null
  private startTime = 0
  private durationTimer: any = null
  private callbacks: RecorderCallbacks = {}

  init(callbacks: RecorderCallbacks) {
    this.callbacks = callbacks
    // #ifdef MP-WEIXIN
    this.initWechatRecorder()
    // #endif
    // #ifdef H5
    // H5 端在 start 时动态初始化
    // #endif
  }

  // #ifdef MP-WEIXIN
  private initWechatRecorder() {
    this.recorderManager = uni.getRecorderManager()

    this.recorderManager.onStart(() => {
      this.state = 'recording'
      this.startTime = Date.now()
      this.startDurationTimer()
      this.callbacks.onStart?.()
    })

    this.recorderManager.onStop((res: any) => {
      this.state = 'idle'
      this.stopDurationTimer()
      const duration = Math.round((Date.now() - this.startTime) / 1000)
      this.callbacks.onStop?.(res.tempFilePath, duration)
    })

    this.recorderManager.onPause(() => {
      this.state = 'paused'
      this.stopDurationTimer()
    })

    this.recorderManager.onResume(() => {
      this.state = 'recording'
      this.startDurationTimer()
    })

    this.recorderManager.onError((err: any) => {
      this.state = 'idle'
      this.stopDurationTimer()
      this.callbacks.onError?.(err.errMsg || '录音失败')
    })
  }
  // #endif

  private startDurationTimer() {
    this.stopDurationTimer()
    this.durationTimer = setInterval(() => {
      const duration = Math.round((Date.now() - this.startTime) / 1000)
      this.callbacks.onDurationUpdate?.(duration)
    }, 1000)
  }

  private stopDurationTimer() {
    if (this.durationTimer) {
      clearInterval(this.durationTimer)
      this.durationTimer = null
    }
  }

  start() {
    if (this.state === 'recording') return

    // #ifdef MP-WEIXIN
    if (this.recorderManager) {
      this.recorderManager.start({
        duration: 60000, // 最长 60 秒
        format: 'mp3',
        sampleRate: 16000,
        numberOfChannels: 1,
        encodeBitRate: 48000,
      })
      return
    }
    // #endif

    // #ifdef H5
    this.startH5Recorder()
    // #endif
  }

  // #ifdef H5
  private async startH5Recorder() {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      // @ts-ignore
      this.mediaRecorder = new MediaRecorder(this.mediaStream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4',
      })
      this.mediaChunks = []

      this.mediaRecorder.onstart = () => {
        this.state = 'recording'
        this.startTime = Date.now()
        this.startDurationTimer()
        this.callbacks.onStart?.()
      }

      this.mediaRecorder.ondataavailable = (e: any) => {
        this.mediaChunks.push(e.data)
      }

      this.mediaRecorder.onstop = () => {
        this.state = 'idle'
        this.stopDurationTimer()
        const blob = new Blob(this.mediaChunks, { type: this.mediaRecorder.mimeType })
        const url = URL.createObjectURL(blob)
        const duration = Math.round((Date.now() - this.startTime) / 1000)
        this.callbacks.onStop?.(url, duration)
        // 清理流
        this.mediaStream?.getTracks().forEach((t: any) => t.stop())
      }

      this.mediaRecorder.onerror = (err: any) => {
        this.state = 'idle'
        this.stopDurationTimer()
        this.mediaStream?.getTracks().forEach((t: any) => t.stop())
        this.callbacks.onError?.(err.message || '录音失败')
      }

      this.mediaRecorder.start()
    } catch (err: any) {
      this.callbacks.onError?.(err.message || '无法访问麦克风')
    }
  }
  // #endif

  stop() {
    if (this.state !== 'recording' && this.state !== 'paused') return

    // #ifdef MP-WEIXIN
    if (this.recorderManager) {
      this.recorderManager.stop()
      return
    }
    // #endif

    // #ifdef H5
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop()
    }
    // #endif
  }

  pause() {
    if (this.state !== 'recording') return

    // #ifdef MP-WEIXIN
    if (this.recorderManager) {
      this.recorderManager.pause()
    }
    // #endif

    // #ifdef H5
    if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
      this.mediaRecorder.pause()
    }
    // #endif
  }

  resume() {
    if (this.state !== 'paused') return

    // #ifdef MP-WEIXIN
    if (this.recorderManager) {
      this.recorderManager.resume()
    }
    // #endif

    // #ifdef H5
    if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
      this.mediaRecorder.resume()
    }
    // #endif
  }

  isRecording() {
    return this.state === 'recording'
  }

  destroy() {
    this.stop()
    this.stopDurationTimer()
    // #ifdef H5
    this.mediaStream?.getTracks().forEach((t: any) => t.stop())
    // #endif
  }
}

// 单例导出
export const audioRecorder = new AudioRecorder()
