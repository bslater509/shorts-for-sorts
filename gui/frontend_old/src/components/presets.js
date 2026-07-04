import { state } from '../state.js';
import * as api from '../api.js';
import { showToast } from '../toast.js';

export function initPresets() {
  const saveBtn = document.getElementById('btn-save-custom-preset');
  if (saveBtn) {
    saveBtn.addEventListener('click', saveCustomPresetToServer);
  }
  
  const colorPickers = [
    { picker: 'preset-color-primary', text: 'preset-color-primary-text' },
    { picker: 'preset-color-highlight', text: 'preset-color-highlight-text' },
    { picker: 'preset-color-outline', text: 'preset-color-outline-text' }
  ];
  
  colorPickers.forEach(pair => {
    const pickerEl = document.getElementById(pair.picker);
    const textEl = document.getElementById(pair.text);
    if (pickerEl && textEl) {
      pickerEl.addEventListener('input', () => { textEl.value = pickerEl.value.toUpperCase(); });
      textEl.addEventListener('change', () => { pickerEl.value = textEl.value; });
    }
  });
  
  window.loadPresetIntoDesigner = loadPresetIntoDesigner;
  window.deletePreset = deletePreset;
}

export function renderPresetsList() {
  const container = document.getElementById('presets-list-grid');
  if (!container) return;
  
  container.innerHTML = '';
  
  Object.keys(state.presets).forEach(name => {
    const p = state.presets[name];
    const item = document.createElement('div');
    item.className = 'preset-item';
    
    item.innerHTML = `
      <div class="preset-item-info">
        <h4>${name}</h4>
        <p>Voice: ${p.selected_voice || 'Default'} | Anim: ${p.sub_animation_style || 'Default'} | Font: ${p.sub_font || 'Default'} (${p.sub_size}px)</p>
      </div>
      <div class="preset-item-actions">
        <button class="btn btn-sm btn-secondary" onclick="loadPresetIntoDesigner('${name}')">Edit</button>
        <button class="btn btn-sm btn-outline-danger" onclick="deletePreset('${name}')">Delete</button>
      </div>
    `;
    container.appendChild(item);
  });
}

export function loadPresetIntoDesigner(name) {
  const p = state.presets[name];
  if (!p) return;
  
  const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };
  
  setVal('preset-name-input', name);
  setVal('preset-font-select', p.sub_font || 'Arial');
  setVal('preset-font-size', p.sub_size || 72);
  setVal('preset-bold', (p.sub_bold !== false).toString());
  setVal('preset-case', (p.sub_uppercase !== false).toString());
  
  const primary = p.sub_color || '#FFFFFF';
  setVal('preset-color-primary', primary);
  setVal('preset-color-primary-text', primary);
  
  const highlight = p.sub_highlight || '#00FFFF';
  setVal('preset-color-highlight', highlight);
  setVal('preset-color-highlight-text', highlight);
  
  const outline = p.sub_outline || '#000000';
  setVal('preset-color-outline', outline);
  setVal('preset-color-outline-text', outline);
  
  setVal('preset-outline-width', p.sub_outline_width !== undefined ? p.sub_outline_width : 5);
  setVal('preset-word-pop', (p.word_pop !== false).toString());
  setVal('preset-inactive-dim', (p.inactive_dim !== false).toString());
  setVal('preset-anim-style', p.sub_animation_style || 'tiktok_pop');
  
  const emojiPos = p.emoji_position || (p.enable_emojis === false ? 'none' : 'above');
  setVal('preset-emoji-pos', emojiPos);
  
  setVal('preset-voice-select', p.selected_voice || 'af_sarah');
  setVal('preset-voice-speed', p.voice_speed || 1.0);
}

async function saveCustomPresetToServer() {
  const getVal = id => document.getElementById(id)?.value;
  const name = getVal('preset-name-input')?.trim();
  
  if (!name) {
    showToast('Please enter a name for the Preset template.', 'warning');
    return;
  }
  
  const emojiPos = getVal('preset-emoji-pos');
  
  const payload = {
    name: name,
    selected_voice: getVal('preset-voice-select'),
    voice_speed: parseFloat(getVal('preset-voice-speed')) || 1.0,
    voice_volume: 1.2,
    music_volume: 0.15,
    sub_font: getVal('preset-font-select'),
    sub_size: parseInt(getVal('preset-font-size')) || 72,
    sub_color: getVal('preset-color-primary-text'),
    sub_highlight: getVal('preset-color-highlight-text'),
    sub_outline: getVal('preset-color-outline-text'),
    sub_outline_width: parseInt(getVal('preset-outline-width')) || 5,
    sub_bold: getVal('preset-bold') === 'true',
    sub_uppercase: getVal('preset-case') === 'true',
    word_pop: getVal('preset-word-pop') === 'true',
    word_pop_scale: 1.15,
    inactive_dim: getVal('preset-inactive-dim') === 'true',
    inactive_alpha: '88',
    enable_emojis: emojiPos !== 'none',
    emoji_position: emojiPos !== 'none' ? emojiPos : 'none',
    sub_animation_style: getVal('preset-anim-style')
  };
  
  try {
    await api.savePreset(payload);
    showToast('Custom preset template saved!', 'success');
    await api.fetchPresets();
    renderPresetsList();
  } catch (err) {
    showToast(`Preset save failed: ${err.message}`, 'error');
  }
}

export async function deletePreset(name) {
  if (!confirm(`Are you sure you want to delete the preset template "${name}"?`)) return;
  
  try {
    await api.deletePreset(name);
    showToast('Preset deleted', 'success');
    await api.fetchPresets();
    renderPresetsList();
  } catch (err) {
    showToast(`Preset delete failed: ${err.message}`, 'error');
  }
}
