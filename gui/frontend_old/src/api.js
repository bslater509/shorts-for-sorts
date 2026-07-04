import { state } from './state.js';

async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `Request failed: ${res.status}`);
  }
  return data;
}

export async function fetchState() {
  const data = await apiFetch('/api/state');
  state.app = data;
  return data;
}

export async function saveState() {
  return await apiFetch('/api/state', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state.app)
  });
}

export async function fetchSettings() {
  const data = await apiFetch('/api/settings');
  state.settings = data;
  return data;
}

export async function saveSettings(payload) {
  return await apiFetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export async function fetchPresets() {
  const data = await apiFetch('/api/presets');
  state.presets = data;
  return data;
}

export async function savePreset(payload) {
  return await apiFetch('/api/presets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export async function deletePreset(name) {
  return await apiFetch(`/api/presets/${encodeURIComponent(name)}`, {
    method: 'DELETE'
  });
}

export async function fetchVoices() {
  const data = await apiFetch('/api/voices');
  state.voices = data;
  return data;
}

export async function generateScript(prompt, voiceOverride, modelOverride) {
  return await apiFetch('/api/script/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      selected_voice: voiceOverride || null,
      model_override: modelOverride || null
    })
  });
}

export async function fetchVideos() {
  return await apiFetch('/api/assets/videos');
}

export async function fetchMusic() {
  return await apiFetch('/api/assets/music');
}

export async function uploadAsset(file, type) {
  const formData = new FormData();
  formData.append('file', file);
  const endpoint = type === 'video' ? '/api/assets/videos' : '/api/assets/music';
  return await apiFetch(endpoint, {
    method: 'POST',
    body: formData
  });
}

export async function deleteVideo(filename) {
  return await apiFetch(`/api/assets/videos/${encodeURIComponent(filename)}`, {
    method: 'DELETE'
  });
}

export async function deleteMusic(filename) {
  return await apiFetch(`/api/assets/music/${encodeURIComponent(filename)}`, {
    method: 'DELETE'
  });
}

export async function searchPexels(query) {
  return await apiFetch('/api/pexels/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
}

export async function downloadPexelsVideo(downloadUrl, videoId, keyword, position) {
  return await apiFetch('/api/pexels/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      download_url: downloadUrl,
      video_id: videoId,
      keyword: keyword,
      position: position
    })
  });
}

export async function extractKeyword() {
  return await apiFetch('/api/pexels/extract-keyword', { method: 'POST' });
}

export async function startCompilation(customFilename) {
  const formData = new FormData();
  if (customFilename) {
    formData.append('custom_filename', customFilename);
  }
  return await fetch('/api/compile', {
    method: 'POST',
    body: formData
  });
}

export async function getCompilationStatus() {
  return await apiFetch('/api/compile/status');
}

export async function cancelCompilation() {
  return await apiFetch('/api/compile/cancel', { method: 'POST' });
}

export async function fetchGallery() {
  return await apiFetch('/api/gallery');
}

export async function deleteGalleryVideo(filename) {
  return await apiFetch(`/api/gallery/${encodeURIComponent(filename)}`, {
    method: 'DELETE'
  });
}

// Batch API
export async function startBatch(numShorts) {
  return await apiFetch('/api/batch/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ num_shorts: numShorts })
  });
}

export async function getBatchStatus() {
  return await apiFetch('/api/batch/status');
}

export async function cancelBatch() {
  return await apiFetch('/api/batch/cancel', { method: 'POST' });
}
