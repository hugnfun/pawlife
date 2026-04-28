import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePetStore } from '@/stores/pet'
import type { Pet } from '@/types/api'

const mockPet: Pet = {
  id: 'pet-1',
  name: '旺财',
  species: 'dog',
  breed: '金毛',
  gender: 'male',
  current_weight: 25.5,
  ideal_weight: 28,
  is_active: true,
  owner_id: 'user-1',
  created_at: '2024-01-01T00:00:00Z',
}

const mockPet2: Pet = {
  ...mockPet,
  id: 'pet-2',
  name: '咪咪',
  species: 'cat',
  breed: '英短',
  gender: 'female',
  current_weight: 4.5,
  ideal_weight: 5,
  is_active: false,
}

describe('Pet Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should initialize with empty pets', () => {
    const store = usePetStore()
    expect(store.pets).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('should add a pet', () => {
    const store = usePetStore()
    store.addPet(mockPet)
    expect(store.pets).toHaveLength(1)
    expect(store.pets[0].name).toBe('旺财')
  })

  it('should update a pet', () => {
    const store = usePetStore()
    store.addPet(mockPet)
    store.updatePet('pet-1', { current_weight: 26 })
    expect(store.pets[0].current_weight).toBe(26)
    expect(store.pets[0].name).toBe('旺财') // 其他字段不变
  })

  it('should not update non-existent pet', () => {
    const store = usePetStore()
    store.addPet(mockPet)
    store.updatePet('pet-999', { name: '不存在' })
    expect(store.pets[0].name).toBe('旺财')
  })

  it('should remove a pet', () => {
    const store = usePetStore()
    store.addPet(mockPet)
    store.addPet(mockPet2)
    expect(store.pets).toHaveLength(2)

    store.removePet('pet-1')
    expect(store.pets).toHaveLength(1)
    expect(store.pets[0].name).toBe('咪咪')
  })

  it('should select a pet', () => {
    const store = usePetStore()
    store.addPet(mockPet)
    store.selectPet(mockPet)
    expect(store.currentSelectedPet?.id).toBe('pet-1')
  })

  it('should clear selected pet', () => {
    const store = usePetStore()
    store.addPet(mockPet)
    store.selectPet(mockPet)
    expect(store.currentSelectedPet).not.toBeNull()

    store.selectPet(null)
    expect(store.currentSelectedPet).toBeNull()
  })
})
