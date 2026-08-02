import { create } from 'zustand'
import * as api from '@/lib/api'

export const useAppStore = create((set, get) => ({
  appState: {},
  settings: {},
  voices: [],

  // Setters
  updateAppState: (updates) => set((state) => ({ 
    appState: { ...state.appState, ...updates } 
  })),

  updateSettings: (updates) => set((state) => {
    const newSettings = { ...state.settings, ...updates };
    // Optionally auto-save
    api.saveSettings(newSettings).catch(e => console.error("Auto-save failed", e));
    return { settings: newSettings };
  }),

  // Thunks / Actions
  initializeData: async () => {
    try {
      const [appData, settingsData, voicesData] = await Promise.all([
        api.fetchState(),
        api.fetchSettings(),
        api.fetchVoices()
      ])
      
      set({ 
        appState: appData,
        settings: settingsData,
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
  }
}))
