import { state } from '../state.js';
import * as api from '../api.js';
import { showToast } from '../toast.js';

export function initSettings() {
  const saveBtn = document.getElementById('btn-save-settings');
  if (saveBtn) {
    saveBtn.addEventListener('click', saveSettingsToServer);
  }
  
  const whisperModeSelect = document.getElementById('settings-whisper-mode');
  if (whisperModeSelect) {
    whisperModeSelect.addEventListener('change', () => {
      const localRow = document.getElementById('settings-whisper-model-row');
      const apiFields = document.getElementById('settings-whisper-api-fields');
      if (localRow && apiFields) {
        if (whisperModeSelect.value === 'local') {
          localRow.classList.remove('hidden');
          apiFields.classList.add('hidden');
        } else {
          localRow.classList.add('hidden');
          apiFields.classList.remove('hidden');
        }
      }
    });
  }
}

export function syncSettingsUI() {
  if (!state.settings) return;
  
  const s = state.settings;
  const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };
  
  setVal('settings-api-key', s.api_key || '');
  setVal('settings-base-url', s.base_url || '');
  setVal('settings-model', s.model || 'gpt-4o-mini');
  setVal('settings-max-words', s.max_words || 400);
  setVal('settings-pexels-key', s.pexels_api_key || '');
  
  const whisperModeSelect = document.getElementById('settings-whisper-mode');
  if (whisperModeSelect) {
    whisperModeSelect.value = s.local_whisper ? 'local' : 'api';
    whisperModeSelect.dispatchEvent(new Event('change'));
  }
  
  setVal('settings-whisper-model', s.local_whisper_model || 'tiny');
  setVal('settings-whisper-key', s.whisper_api_key || '');
  setVal('settings-whisper-url', s.whisper_base_url || '');
  
  setVal('settings-render-res', s.render_resolution || '1080p');
  setVal('settings-render-preset', s.render_preset || 'veryfast');
  setVal('settings-video-encoder', s.video_encoder || 'libx264');
}

async function saveSettingsToServer() {
  const getVal = id => document.getElementById(id)?.value;
  
  const payload = {
    api_key: getVal('settings-api-key'),
    base_url: getVal('settings-base-url'),
    model: getVal('settings-model'),
    max_words: parseInt(getVal('settings-max-words')) || 400,
    pexels_api_key: getVal('settings-pexels-key'),
    local_whisper: getVal('settings-whisper-mode') === 'local',
    local_whisper_model: getVal('settings-whisper-model'),
    whisper_api_key: getVal('settings-whisper-key'),
    whisper_base_url: getVal('settings-whisper-url'),
    render_resolution: getVal('settings-render-res'),
    render_preset: getVal('settings-render-preset'),
    video_encoder: getVal('settings-video-encoder'),
  };
  
  try {
    await api.saveSettings(payload);
    showToast('Settings saved successfully!', 'success');
    await api.fetchSettings();
  } catch (err) {
    showToast(`Error saving settings: ${err.message}`, 'error');
  }
}
