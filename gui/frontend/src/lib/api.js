async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  // Parse JSON safely — non-JSON responses (e.g. HTML 502 from proxy) would otherwise
  // throw a confusing SyntaxError that masks the real HTTP error.
  let data;
  try {
    data = await res.json();
  } catch {
    if (!res.ok) throw new Error(`Request failed: ${res.status} ${res.statusText}`);
    throw new Error('Invalid JSON response from server');
  }
  if (!res.ok) {
    throw new Error(data?.detail || `Request failed: ${res.status}`);
  }
  return data;
}

export async function fetchState() {
  return await apiFetch('/api/state');
}

export async function saveState(appState) {
  return await apiFetch('/api/state', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(appState)
  });
}

export async function fetchSettings() {
  return await apiFetch('/api/settings');
}

export async function saveSettings(payload) {
  return await apiFetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export async function fetchLLMModels(api_key, base_url) {
  return await apiFetch('/api/llm/models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key, base_url })
  });
}

export async function fetchPresets() {
  return await apiFetch('/api/presets');
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
  return await apiFetch('/api/voices');
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

export async function downloadYoutubeVideo(url, downscale) {
  return await apiFetch('/api/youtube/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: url,
      downscale: downscale
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

export async function deleteAllGalleryVideos() {
  return await apiFetch('/api/gallery', {
    method: 'DELETE'
  });
}

export async function fetchPrompts() {
  return await apiFetch('/api/prompts');
}

export async function startBatch(numShorts, prompts = []) {
  return await apiFetch('/api/batch/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ num_shorts: numShorts, prompts })
  });
}

export async function getBatchStatus() {
  return await apiFetch('/api/batch/status');
}

export async function cancelBatch() {
  return await apiFetch('/api/batch/cancel', { method: 'POST' });
}

export async function uploadTikTokVideo(filename, description, visibility) {
  return await apiFetch('/api/tiktok/upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, description, visibility })
  });
}

export async function loginTikTok() {
  return await apiFetch('/api/tiktok/login', { method: 'POST' });
}
