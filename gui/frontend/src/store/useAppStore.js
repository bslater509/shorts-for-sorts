import { create } from 'zustand'
import * as api from '@/lib/api'

export const useAppStore = create((set, get) => ({
  appState: {},
  settings: {},
  presets: {},
  voices: [],

  // Setters
  updateAppState: (updates) => set((state) => ({ 
    appState: { ...state.appState, ...updates } 
  })),

  // Thunks / Actions
  initializeData: async () => {
    try {
      const [appData, settingsData, presetsData, voicesData] = await Promise.all([
        api.fetchState(),
        api.fetchSettings(),
        api.fetchPresets(),
        api.fetchVoices()
      ])
      
      set({ 
        appState: appData,
        settings: settingsData,
        presets: presetsData,
        voices: voicesData
      })
    } catch (err) {
      console.error('Failed to initialize app data:', err)
    }
  },

  saveCurrentState: async () => {
    const { appState } = get()
    try {
      await api.saveState(appState)
    } catch (err) {
      console.error('Failed to save state:', err)
      throw err
    }
  },

  applyPreset: async (presetName) => {
    const { presets } = get()
    const preset = presets[presetName]
    if (preset) {
      set((state) => ({
        appState: { ...state.appState, ...preset, loaded_preset_name: presetName }
      }))
      await get().saveCurrentState()
    }
  }
}))
