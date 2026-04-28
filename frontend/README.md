# PawLife Frontend

PawLife AI Native 宠物健康管理 - 前端

基于 uni-app + Vue 3 + Pinia 开发，支持微信小程序和 H5。

## 技术栈

- **框架**: uni-app 3.x + Vue 3.4 (Composition API)
- **状态管理**: Pinia 2.x
- **语言**: TypeScript
- **样式**: SCSS
- **流式输出**: SSE 原生支持

## 目录结构

```
src/
├── api/              # API 接口封装
├── components/       # 公共组件
├── pages/            # 页面
│   ├── chat/        # AI 对话主界面
│   ├── timeline/    # 记录流
│   └── profile/     # 宠物档案
├── stores/          # Pinia 状态管理
│   ├── auth.ts      # 认证状态
│   ├── chat.ts      # AI 对话状态
│   └── pet.ts       # 宠物状态
├── styles/          # 全局样式
├── types/           # TypeScript 类型定义
└── utils/           # 工具函数
    └── sse.ts       # SSE 流式响应客户端
```

## 主要功能

1. **AI 对话主界面 (ChatPage)**
   - 文字/语音/图片输入
   - SSE 流式实时输出
   - 快捷建议按钮
   - 会话上下文管理

2. **记录流 (TimelinePage)**
   - 按时间倒序展示所有记录
   - 按宠物筛选
   - 下拉刷新/上拉加载

3. **宠物档案 (ProfilePage)**
   - 我的宠物列表
   - 切换活跃宠物
   - 宠物基本信息展示

## 开发

### 安装依赖

```bash
npm install
```

### 运行微信小程序开发

```bash
npm run dev:mp-weixin
```

开发工具打开 `dist/dev/mp-weixin` 目录即可预览

### 运行 H5 开发

```bash
npm run dev:h5
```

### 类型检查

```bash
npm run type-check
```

### 构建

```bash
# 微信小程序
npm run build:mp-weixin

# H5
npm run build:h5
```

## SSE 流式输出

实现了环境兼容的 SSE 客户端:
- H5 环境使用原生 `EventSource`
- 微信小程序使用 `uni.request` + `enableChunked` 分块读取

支持实时逐字显示 AI 回复，提供更好的用户体验。

## 环境变量

- `VITE_API_BASE_URL`: API 基础地址，默认 `/api`，开发环境可以代理到后端

## 权限流程

1. 微信小程序登录 → 获取 code
2. 调用后端 `/v1/auth/wechat-login` → 获取 JWT token
3. 保存在本地存储，后续请求自动携带
4. token 过期使用 refresh_token 刷新
