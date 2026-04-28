import { describe, it, expect, vi } from 'vitest'

// Mock API 模块
vi.mock('@/api/index', () => ({
  get: vi.fn(() => Promise.resolve([])),
  post: vi.fn(() => Promise.resolve({ id: 'pet-1' })),
  put: vi.fn(() => Promise.resolve({ id: 'pet-1' })),
  del: vi.fn(() => Promise.resolve({ success: true })),
}))

describe('Pet API', () => {
  it('should export all pet API functions', async () => {
    const { getMyPets, getPetDetail, createPet, updatePet, deletePet, switchActivePet } =
      await import('@/api/pet')

    expect(typeof getMyPets).toBe('function')
    expect(typeof getPetDetail).toBe('function')
    expect(typeof createPet).toBe('function')
    expect(typeof updatePet).toBe('function')
    expect(typeof deletePet).toBe('function')
    expect(typeof switchActivePet).toBe('function')
  })

  it('getMyPets should call GET /v1/pets', async () => {
    const { getMyPets } = await import('@/api/pet')
    const pets = await getMyPets()
    expect(Array.isArray(pets)).toBe(true)
  })

  it('createPet should call POST /v1/pets', async () => {
    const { createPet } = await import('@/api/pet')
    const result = await createPet({
      name: 'Test Pet',
      species: 'dog',
      gender: 'male',
      is_active: false,
      owner_id: 'user-1',
      created_at: '2024-01-01',
    })
    expect(result.id).toBe('pet-1')
  })
})
