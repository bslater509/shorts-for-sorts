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

export async function fetchSystemStats() {
  return await apiFetch('/api/system_stats');
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

export async function fetchVoices() {
  return await apiFetch('/api/voices');
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

export async function searchYoutube(query, limit = 10) {
  return await apiFetch('/api/youtube/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit })
  });
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

export async function startBatch(numShorts, prompts = [], options = {}, ...legacy) {
  // Backward compatibility: the previous signature accepted positional emoji
  // overrides as arguments 3-8. If `options` isn't an object, treat the call
  // as the legacy positional form.
  let opts = options
  if (typeof options !== 'object' || options === null) {
    opts = {
      enableEmojis: options,
      enableEmojiAnimation: legacy[0],
      emojiScaleFactor: legacy[1],
      emojiHoldDuration: legacy[2],
      emojiThrowMaxCount: legacy[3],
    }
  }
  const {
    enableEmojis = true,
    enableEmojiAnimation = true,
    emojiScaleFactor = 1.5,
    emojiHoldDuration = 0.5,
    emojiThrowMaxCount = 3,
    emojiStyles = null,
    layout = null,
    voiceId = null,
    subAnimationStyle = null,
    wordsPerScreen = null,
    singleWordMode = null,
    bgMusicPath = null,
    scriptTemp = null,
    metaTemp = null,
    maxWorkers = null,
    llmMaxWorkers = null,
    postToTikTok = false,
  } = opts

  // UI sentinels — "Random" / "Default" mean "let the backend decide" and are
  // sent as null so the batch engine keeps its default random behaviour.
  const resolveRandom = (value) => (value === 'Random' || value === 'Default' ? null : value)

  return await apiFetch('/api/batch/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      num_shorts: numShorts,
      prompts,
      enable_emojis: enableEmojis,
      enable_emoji_animation: enableEmojiAnimation,
      emoji_scale_factor: emojiScaleFactor,
      emoji_hold_duration: emojiHoldDuration,
      emoji_throw_max_count: emojiThrowMaxCount,
      emoji_styles: emojiStyles,
      layout: resolveRandom(layout),
      voice_id: resolveRandom(voiceId),
      sub_animation_style: resolveRandom(subAnimationStyle),
      words_per_screen: resolveRandom(wordsPerScreen),
      single_word_mode: singleWordMode,
      bg_music_path: resolveRandom(bgMusicPath),
      script_temp: scriptTemp,
      meta_temp: metaTemp,
      max_workers: maxWorkers,
      llm_max_workers: llmMaxWorkers,
      post_to_tiktok: postToTikTok,
    })
  });
}

export async function getBatchStatus() {
  return await apiFetch('/api/batch/status');
}

export async function cancelBatch() {
  return await apiFetch('/api/batch/cancel', { method: 'POST' });
}

export async function retryFailedBatch() {
  return await apiFetch('/api/batch/retry-failed', {
    method: 'POST'
  });
}

export async function retryBatchJob(jobId) {
  return await apiFetch(`/api/batch/retry-job/${jobId}`, {
    method: 'POST'
  });
}

export async function cancelJob(jobId) {
  return await apiFetch(`/api/batch/cancel-job/${jobId}`, { method: 'POST' });
}

export async function retryCancelledBatch() {
  return await apiFetch('/api/batch/retry-cancelled', { method: 'POST' });
}

export async function dismissJob(jobId) {
  return await apiFetch(`/api/batch/dismiss-job/${jobId}`, { method: 'POST' });
}

export async function getBatchReport() {
  return await apiFetch('/api/batch/report');
}

export async function getJobDetail(jobId) {
  return await apiFetch(`/api/batch/job/${jobId}`);
}

export async function getBatchStats() {
  return await apiFetch('/api/batch/stats');
}

export async function resetBatchStats() {
  return await apiFetch('/api/batch/stats/reset', { method: 'POST' });
}

export async function openOutputFolder() {
  return await apiFetch('/api/gallery/open-folder', { method: 'POST' });
}

export async function validateBatch() {
  return await apiFetch('/api/batch/validate');
}

export async function postToTikTok(filename) {
  return await apiFetch(`/api/tiktok/post/${encodeURIComponent(filename)}`, { method: 'POST' });
}

export async function getTikTokStatus() {
  return await apiFetch('/api/tiktok/status');
}

export async function fetchSchedules() {
  return await apiFetch('/api/schedules');
}

export async function createSchedule(data) {
  return await apiFetch('/api/schedules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

export async function updateSchedule(id, data) {
  return await apiFetch(`/api/schedules/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
}

export async function deleteSchedule(id) {
  return await apiFetch(`/api/schedules/${encodeURIComponent(id)}`, {
    method: 'DELETE'
  });
}

export async function toggleSchedule(id) {
  return await apiFetch(`/api/schedules/${encodeURIComponent(id)}/toggle`, {
    method: 'POST'
  });
}

export async function runScheduleNow(id) {
  return await apiFetch(`/api/schedules/${encodeURIComponent(id)}/run`, {
    method: 'POST'
  });
}

export async function fetchScheduleStatus() {
  return await apiFetch('/api/schedules/status');
}
