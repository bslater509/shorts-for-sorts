import './styles/index.css';
import { state } from './state.js';
import * as api from './api.js';
import { showToast } from './toast.js';
import { initSidebar } from './components/sidebar.js';
import { initStudio, syncStudioUI, renderStudioPresetsGrid, updateWordCount, startCompilationPolling } from './components/studio.js';
import { initMediaManager } from './components/mediaManager.js';
import { initPresets, renderPresetsList } from './components/presets.js';
import { initGallery, refreshGallery } from './components/gallery.js';
import { initSettings, syncSettingsUI } from './components/settings.js';
import { initModal } from './components/modal.js';
import { initBatch, checkActiveBatch } from './components/batch.js';

async function initApp() {
  // Init components
  initSidebar();
  initStudio();
  initMediaManager();
  initPresets();
  initGallery();
  initSettings();
  initModal();
  initBatch();

  // Parallel data fetch
  try {
    await Promise.all([
      api.fetchVoices(),
      api.fetchState(),
      api.fetchSettings(),
      api.fetchPresets(),
    ]);
    // Sync UI
    syncStudioUI();
    syncSettingsUI();
    renderStudioPresetsGrid();
    renderPresetsList();
    updateWordCount();
    refreshGallery();
    checkActiveCompilation();
    checkActiveBatch();
  } catch (err) {
    console.error('Init failed:', err);
    showToast('Failed to load application data', 'error');
  }
}

async function checkActiveCompilation() {
  try {
    const data = await api.getCompilationStatus();
    if (data.in_progress) {
      document.getElementById('compile-status-container')?.classList.remove('hidden');
      const btn = document.getElementById('btn-compile-video');
      if (btn) btn.disabled = false;
      startCompilationPolling();
    }
  } catch (e) {
    // Silently ignore - compilation status check is non-critical
  }
}

document.addEventListener('DOMContentLoaded', initApp);
