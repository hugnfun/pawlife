// 宠物状态 store
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Pet } from '@/types/api'
import { getMyPets } from '@/api/pet'

export const usePetStore = defineStore(
  'pet',
  () => {
    // 状态
    const pets = ref<Pet[]>([])
    const loading = ref(false)
    const currentSelectedPet = ref<Pet | null>(null)

    // 获取我的宠物列表
    async function fetchMyPets() {
      loading.value = true
      try {
        const data = await getMyPets()
        pets.value = data
        return data
      } finally {
        loading.value = false
      }
    }

    // 添加宠物
    function addPet(pet: Pet) {
      pets.value.push(pet)
    }

    // 更新宠物
    function updatePet(id: string, updates: Partial<Pet>) {
      const index = pets.value.findIndex(p => p.id === id)
      if (index !== -1) {
        pets.value[index] = { ...pets.value[index], ...updates }
      }
    }

    // 删除宠物
    function removePet(id: string) {
      pets.value = pets.value.filter(p => p.id !== id)
    }

    // 设置当前选中宠物
    function selectPet(pet: Pet | null) {
      currentSelectedPet.value = pet
    }

    return {
      pets,
      loading,
      currentSelectedPet,
      fetchMyPets,
      addPet,
      updatePet,
      removePet,
      selectPet,
    }
  }
)
