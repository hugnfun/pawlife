<script setup lang="ts">
/**
 * 宠物编辑页面
 * 支持新增和编辑两种模式
 * 通过 URL 参数 ?mode=add 或 ?mode=edit&id=xxx 区分
 */
import { ref, onMounted, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { createPet, updatePet, getPetDetail } from '@/api/pet'
import type { Pet } from '@/types/api'

// 页面模式
const mode = ref<'add' | 'edit'>('add')
const petId = ref<string>('')
const loading = ref(false)
const saving = ref(false)

// 表单数据
const form = ref({
  name: '',
  species: 'dog' as 'dog' | 'cat' | 'rabbit' | 'bird' | 'hamster' | 'other',
  breed: '',
  gender: 'male' as 'male' | 'female',
  birthday: '',
  current_weight: '',
  ideal_weight: '',
  is_neutered: false,
  avatar_url: '',
})

// 物种选项
const speciesOptions = [
  { value: 'dog', label: '🐶 狗狗' },
  { value: 'cat', label: '🐱 猫咪' },
  { value: 'rabbit', label: '🐰 兔子' },
  { value: 'bird', label: '🐦 鸟类' },
  { value: 'hamster', label: '🐹 仓鼠' },
  { value: 'other', label: '🐾 其他' },
]

// 性别选项
const genderOptions = [
  { value: 'male', label: '♂ 公' },
  { value: 'female', label: '♀ 母' },
]

// 页面标题
const pageTitle = computed(() => mode.value === 'add' ? '添加宠物' : '编辑宠物')

// 表单验证
function validateForm(): boolean {
  if (!form.value.name.trim()) {
    uni.showToast({ title: '请输入宠物名字', icon: 'none' })
    return false
  }
  if (form.value.current_weight && isNaN(Number(form.value.current_weight))) {
    uni.showToast({ title: '体重请输入数字', icon: 'none' })
    return false
  }
  if (form.value.ideal_weight && isNaN(Number(form.value.ideal_weight))) {
    uni.showToast({ title: '理想体重请输入数字', icon: 'none' })
    return false
  }
  return true
}

// 选择头像
function chooseAvatar() {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['album', 'camera'],
    success: (res) => {
      // 暂时使用本地路径，实际项目应上传到 OSS
      form.value.avatar_url = res.tempFilePaths[0]
    },
  })
}

// 保存宠物
async function handleSave() {
  if (!validateForm()) return

  saving.value = true
  try {
    const payload: any = {
      name: form.value.name.trim(),
      species: form.value.species,
      breed: form.value.breed.trim() || undefined,
      gender: form.value.gender,
      birthday: form.value.birthday || undefined,
      current_weight: form.value.current_weight ? Number(form.value.current_weight) : undefined,
      ideal_weight: form.value.ideal_weight ? Number(form.value.ideal_weight) : undefined,
      avatar_url: form.value.avatar_url || undefined,
      is_active: mode.value === 'add', // 新添加的宠物默认设为活跃
    }

    if (mode.value === 'edit' && petId.value) {
      await updatePet(petId.value, payload)
      uni.showToast({ title: '保存成功', icon: 'success' })
    } else {
      await createPet(payload)
      uni.showToast({ title: '添加成功', icon: 'success' })
    }

    // 返回上一页并刷新
    setTimeout(() => {
      const pages = getCurrentPages()
      const prevPage = pages[pages.length - 2] as any
      if (prevPage && prevPage.$vm) {
        // 触发上一页刷新
        prevPage.$vm.$refs?.petList?.fetchData?.()
      }
      uni.navigateBack()
    }, 500)
  } catch (error: any) {
    console.error('保存宠物失败:', error)
    uni.showToast({ title: error.message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

// 日期选择器
function onBirthdayChange(e: any) {
  form.value.birthday = e.detail.value
}

// 物种选择
function onSpeciesChange(e: any) {
  // speciesOptions 中的 value 是宽字符串，需要断言回 form.species 的联合类型
  form.value.species = speciesOptions[e.detail.value].value as typeof form.value.species
}

// 性别选择
function onGenderChange(e: any) {
  // genderOptions 中的 value 是宽字符串，需要断言回 form.gender 的联合类型
  form.value.gender = genderOptions[e.detail.value].value as typeof form.value.gender
}

onLoad((query) => {
  if (query?.mode === 'edit' && query?.id) {
    mode.value = 'edit'
    petId.value = query.id
  }
})

onMounted(async () => {
  if (mode.value === 'edit' && petId.value) {
    loading.value = true
    try {
      const pet = await getPetDetail(petId.value)
      form.value = {
        name: pet.name,
        species: pet.species,
        breed: pet.breed || '',
        gender: pet.gender,
        birthday: pet.birthday || '',
        current_weight: pet.current_weight ? String(pet.current_weight) : '',
        ideal_weight: pet.ideal_weight ? String(pet.ideal_weight) : '',
        is_neutered: false,
        avatar_url: pet.avatar_url || '',
      }
    } catch (error) {
      console.error('获取宠物详情失败:', error)
      uni.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      loading.value = false
    }
  }
})
</script>

<template>
  <view class="pet-edit-page">
    <!-- 加载状态 -->
    <view v-if="loading" class="loading-state">
      <text>加载中...</text>
    </view>

    <view v-else class="form-container">
      <!-- 头像 -->
      <view class="form-section">
        <view class="avatar-picker" @click="chooseAvatar">
          <image
            v-if="form.avatar_url"
            :src="form.avatar_url"
            mode="aspectFill"
            class="avatar-img"
          />
          <view v-else class="avatar-placeholder">
            <text class="avatar-icon">📷</text>
            <text class="avatar-text">选择头像</text>
          </view>
        </view>
      </view>

      <!-- 基本信息 -->
      <view class="form-section">
        <view class="section-title">基本信息</view>

        <!-- 名字 -->
        <view class="form-item">
          <text class="form-label required">宠物名字</text>
          <input
            v-model="form.name"
            class="form-input"
            placeholder="给你的宠物起个名字"
            maxlength="20"
          />
        </view>

        <!-- 物种 -->
        <view class="form-item">
          <text class="form-label required">物种</text>
          <picker :range="speciesOptions" range-key="label" @change="onSpeciesChange">
            <view class="form-picker">
              <text :class="['picker-text', { placeholder: !form.species }]">
                {{ speciesOptions.find(s => s.value === form.species)?.label || '请选择' }}
              </text>
              <text class="picker-arrow">›</text>
            </view>
          </picker>
        </view>

        <!-- 品种 -->
        <view class="form-item">
          <text class="form-label">品种</text>
          <input
            v-model="form.breed"
            class="form-input"
            placeholder="如：金毛、英短蓝猫"
            maxlength="30"
          />
        </view>

        <!-- 性别 -->
        <view class="form-item">
          <text class="form-label required">性别</text>
          <picker :range="genderOptions" range-key="label" @change="onGenderChange">
            <view class="form-picker">
              <text class="picker-text">
                {{ genderOptions.find(g => g.value === form.gender)?.label || '请选择' }}
              </text>
              <text class="picker-arrow">›</text>
            </view>
          </picker>
        </view>

        <!-- 生日 -->
        <view class="form-item">
          <text class="form-label">生日</text>
          <picker mode="date" :value="form.birthday" @change="onBirthdayChange" :end="new Date().toISOString().split('T')[0]">
            <view class="form-picker">
              <text :class="['picker-text', { placeholder: !form.birthday }]">
                {{ form.birthday || '请选择日期' }}
              </text>
              <text class="picker-arrow">›</text>
            </view>
          </picker>
        </view>
      </view>

      <!-- 健康数据 -->
      <view class="form-section">
        <view class="section-title">健康数据</view>

        <!-- 当前体重 -->
        <view class="form-item">
          <text class="form-label">当前体重 (kg)</text>
          <input
            v-model="form.current_weight"
            class="form-input"
            type="digit"
            placeholder="如：5.5"
          />
        </view>

        <!-- 理想体重 -->
        <view class="form-item">
          <text class="form-label">理想体重 (kg)</text>
          <input
            v-model="form.ideal_weight"
            class="form-input"
            type="digit"
            placeholder="如：5.0"
          />
        </view>

        <!-- 是否绝育 -->
        <view class="form-item form-switch">
          <text class="form-label">是否绝育</text>
          <switch :checked="form.is_neutered" @change="(e: any) => form.is_neutered = e.detail.value" color="#FF8C69" />
        </view>
      </view>

      <!-- 保存按钮 -->
      <view class="form-actions">
        <button
          class="btn btn-primary save-btn"
          :disabled="saving"
          @click="handleSave"
        >
          {{ saving ? '保存中...' : (mode === 'add' ? '添加宠物' : '保存修改') }}
        </button>
        <button
          v-if="mode === 'edit'"
          class="btn btn-danger delete-btn"
          @click="handleDelete"
        >
          删除宠物
        </button>
      </view>
    </view>
  </view>
</template>

<script lang="ts">
// 删除宠物（单独的 script 块避免 setup 作用域问题）
export default {
  methods: {
    handleDelete() {
      uni.showModal({
        title: '确认删除',
        content: '删除后无法恢复，确定要删除这个宠物吗？',
        confirmColor: '#EF6461',
        success: async (res) => {
          if (res.confirm) {
            try {
              const { deletePet } = await import('@/api/pet')
              const petId = (this as any).petId
              await deletePet(petId)
              uni.showToast({ title: '已删除', icon: 'success' })
              setTimeout(() => uni.navigateBack(), 500)
            } catch (error: any) {
              uni.showToast({ title: error.message || '删除失败', icon: 'none' })
            }
          }
        },
      })
    },
  },
}
</script>

<style lang="scss" scoped>
.pet-edit-page {
  min-height: 100vh;
  background-color: $bg-page;
  padding-bottom: 130px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 60vh;
  color: $text-secondary;
  font-size: $font-size-base;
  gap: $spacing-md;

  .loading-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid $divider-color;
    border-top-color: $primary-color;
    border-radius: $radius-full;
    animation: spin 0.8s linear infinite;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.form-container {
  padding: $spacing-md;
}

.avatar-picker {
  display: flex;
  justify-content: center;
  padding: $spacing-xl 0;
  margin-bottom: $spacing-sm;

  .avatar-img {
    width: 120px;
    height: 120px;
    border-radius: $radius-full;
    border: 3px solid $primary-color;
    box-shadow: 0 4px 16px rgba($primary-color, 0.2);
  }

  .avatar-placeholder {
    width: 120px;
    height: 120px;
    border-radius: $radius-full;
    background: linear-gradient(135deg, $primary-color-lighter, $bg-page);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: $spacing-xs;
    border: 2px dashed $border-color;
    transition: all 0.25s ease;

    &:active {
      border-color: $primary-color;
      background-color: $primary-color-light;
    }

    .avatar-icon {
      font-size: 32px;
    }

    .avatar-text {
      font-size: $font-size-xs;
      color: $text-secondary;
    }
  }
}

.form-section {
  background-color: white;
  border-radius: $radius-md;
  padding: $spacing-lg;
  margin-bottom: $spacing-md;
  box-shadow: $shadow-sm;

  .section-title {
    font-size: $font-size-card-title;
    font-weight: 600;
    color: $text-primary;
    margin-bottom: $spacing-md;
    padding-bottom: $spacing-sm;
    border-bottom: 1px solid $divider-color;
    display: flex;
    align-items: center;
    gap: $spacing-sm;

    &::before {
      content: '';
      width: 4px;
      height: 16px;
      border-radius: 2px;
      background: $primary-color;
    }
  }
}

.form-item {
  margin-bottom: $spacing-lg;

  &:last-child {
    margin-bottom: 0;
  }

  .form-label {
    display: block;
    font-size: $font-size-base;
    color: $text-secondary;
    margin-bottom: $spacing-sm;

    &.required::before {
      content: '*';
      color: $error-color;
      margin-right: 4px;
    }
  }

  .form-input {
    width: 100%;
    height: 44px;
    padding: 0 $spacing-md;
    font-size: $font-size-card-title;
    background-color: $bg-page;
    border-radius: $radius-sm;
    border: 1px solid $border-color;
    box-sizing: border-box;
    transition: all 0.2s ease;

    &:focus {
      border-color: $primary-color;
      background-color: white;
      box-shadow: 0 0 0 3px rgba($primary-color, 0.1);
    }
  }

  .form-picker {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 44px;
    padding: 0 $spacing-md;
    background-color: $bg-page;
    border-radius: $radius-sm;
    border: 1px solid $border-color;
    transition: all 0.2s ease;

    &:active {
      border-color: $primary-color;
      background-color: $primary-color-lighter;
    }

    .picker-text {
      font-size: $font-size-card-title;
      color: $text-primary;

      &.placeholder {
        color: $text-disabled;
      }
    }

    .picker-arrow {
      font-size: 18px;
      color: $text-disabled;
      font-weight: 300;
    }
  }

  &.form-switch {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: $spacing-sm 0;

    .form-label {
      margin-bottom: 0;
    }
  }
}

.form-actions {
  padding: $spacing-lg $spacing-md;
  padding-bottom: calc(#{$spacing-lg} + env(safe-area-inset-bottom));
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: white;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.06);

  .save-btn {
    width: 100%;
    height: 48px;
    line-height: 48px;
    font-size: 17px;
    font-weight: 500;
    border-radius: $radius-md;
    background: linear-gradient(135deg, $primary-color 0%, $primary-color-dark 100%);
    color: white;
    box-shadow: 0 4px 16px rgba($primary-color, 0.3);
    transition: all 0.25s ease;

    &:active {
      transform: scale(0.98);
      box-shadow: 0 2px 8px rgba($primary-color, 0.2);
    }

    &::after { border: none; }

    &[disabled] {
      opacity: 0.6;
      transform: none;
      box-shadow: none;
    }
  }

  .delete-btn {
    width: 100%;
    height: 44px;
    line-height: 44px;
    font-size: $font-size-card-title;
    font-weight: 500;
    border-radius: $radius-sm;
    margin-top: $spacing-sm;
    background-color: $error-color-light;
    color: $error-color;

    &:active {
      background-color: darken($error-color-light, 5%);
    }

    &::after { border: none; }
  }
}

.btn {
  &.btn-primary {
    background: linear-gradient(135deg, $primary-color, $primary-color-dark);
    color: #fff;

    &[disabled] {
      opacity: 0.6;
    }
  }

  &.btn-danger {
    background-color: $error-color-light;
    color: $error-color;
  }
}

// 页面入场动画
.form-container {
  animation: stagger-fade-in 0.3s ease-out;
}

@keyframes stagger-fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
