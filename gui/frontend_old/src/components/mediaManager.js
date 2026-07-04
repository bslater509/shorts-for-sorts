import { state } from '../state.js';
import * as api from '../api.js';
import { showToast } from '../toast.js';
import { updateSelectedAssetsDisplay } from './studio.js';
import { selectAssetFromModal, closeAssetSelector } from './modal.js';
import { appendConsoleLog } from './terminal.js';

export function initMediaManager() {
  const tabContainer = document.querySelector('.media-tabs-header');
  if (tabContainer) {
    tabContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.media-tab-btn');
      if (!btn) return;
      
      document.querySelectorAll('.media-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      const targetPaneId = `pane-${btn.dataset.media}`;
      document.querySelectorAll('.media-pane').forEach(pane => {
        if (pane.id === targetPaneId) pane.classList.add('active');
        else pane.classList.remove('active');
      });
      
      refreshAssetsList();
    });
  }
  
  setupDropzones();
  
  const searchBtn = document.getElementById('btn-search-pexels');
  if (searchBtn) {
    searchBtn.addEventListener('click', () => searchPexels('main'));
  }
  
  window.toggleAudioPreview = toggleAudioPreview;
  window.deleteAsset = deleteAsset;
  window.downloadPexelsVideo = downloadPexelsVideo;
}

export async function refreshAssetsList() {
  const activeTab = document.querySelector('.media-tab-btn.active')?.dataset.media;
  if (activeTab === 'videos') {
    await renderVideosGrid('main');
  } else if (activeTab === 'music') {
    await renderMusicGrid('main');
  }
}

function renderSkeletons(grid, count = 4) {
  grid.innerHTML = Array(count).fill(
    '<div class="asset-card"><div class="skeleton skeleton-card" style="height:110px"></div><div style="padding:0.75rem"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text short"></div></div></div>'
  ).join('');
}

export async function renderVideosGrid(context) {
  const gridId = context === 'main' ? 'videos-grid' : 'modal-asset-grid';
  const grid = document.getElementById(gridId);
  if (!grid) return;
  
  renderSkeletons(grid);
  
  try {
    const videos = await api.fetchVideos();
    
    if (videos.length === 0) {
      grid.innerHTML = '<div class="empty-state">No videos found. Upload one or download from Pexels!</div>';
      return;
    }
    
    grid.innerHTML = '';
    
    if (context === 'modal') {
      const randCard = document.createElement('div');
      randCard.className = 'asset-card';
      randCard.style.cursor = 'pointer';
      randCard.innerHTML = `
        <div class="asset-thumbnail-container"><span class="asset-icon-placeholder">🎲</span></div>
        <div class="asset-details">
          <span class="asset-title">Random Selection</span>
          <span class="asset-meta">Auto select randomly on compile</span>
        </div>
      `;
      randCard.addEventListener('click', () => selectAssetFromModal('random'));
      grid.appendChild(randCard);
    }
    
    videos.forEach(v => {
      const card = document.createElement('div');
      card.className = 'asset-card';
      if (context === 'modal') card.style.cursor = 'pointer';
      
      let durationStr = v.duration ? `${v.duration.toFixed(1)}s` : '';
      let sizeStr = `${(v.size / (1024 * 1024)).toFixed(1)} MB`;
      
      card.innerHTML = `
        <div class="asset-thumbnail-container">
          <video class="asset-thumbnail-video" src="${v.url}" muted loop playsinline></video>
          <span class="pexels-duration-badge">${durationStr || 'Loop'}</span>
        </div>
        <div class="asset-details">
          <span class="asset-title" title="${v.filename}">${v.filename}</span>
          <div class="asset-meta"><span>${sizeStr}</span></div>
        </div>
        <div class="asset-actions-overlay">
          <button class="action-icon-btn delete-btn" onclick="event.stopPropagation(); deleteAsset('video', '${v.filename}')">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
          </button>
        </div>
      `;
      
      const video = card.querySelector('video');
      card.addEventListener('mouseenter', () => { try { video.play(); } catch(e){} });
      card.addEventListener('mouseleave', () => { try { video.pause(); video.currentTime = 0; } catch(e){} });
      
      if (context === 'modal') {
        card.addEventListener('click', () => selectAssetFromModal(`videos/${v.filename}`));
      }
      
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = '<div class="empty-state">Failed to load video catalog.</div>';
    showToast('Failed to load videos', 'error');
  }
}

export async function renderMusicGrid(context) {
  const gridId = context === 'main' ? 'music-grid' : 'modal-asset-grid';
  const grid = document.getElementById(gridId);
  if (!grid) return;
  
  renderSkeletons(grid);
  
  try {
    const tracks = await api.fetchMusic();
    
    if (tracks.length === 0) {
      grid.innerHTML = '<div class="empty-state">No music files found. Drag & drop audio tracks to add!</div>';
      return;
    }
    
    grid.innerHTML = '';
    
    if (context === 'modal' && state.activeSelectorTarget === 'music') {
      const noneCard = document.createElement('div');
      noneCard.className = 'asset-card';
      noneCard.style.cursor = 'pointer';
      noneCard.innerHTML = `
        <div class="asset-thumbnail-container"><span class="asset-icon-placeholder">🚫</span></div>
        <div class="asset-details">
          <span class="asset-title">No background music</span>
          <span class="asset-meta">Disable music track</span>
        </div>
      `;
      noneCard.addEventListener('click', () => selectAssetFromModal(null));
      grid.appendChild(noneCard);
    }
    
    tracks.forEach(t => {
      const card = document.createElement('div');
      card.className = 'asset-card';
      if (context === 'modal') card.style.cursor = 'pointer';
      
      let sizeStr = `${(t.size / (1024 * 1024)).toFixed(2)} MB`;
      
      card.innerHTML = `
        <div class="asset-thumbnail-container">
          <span class="asset-icon-placeholder">🎵</span>
          <audio class="asset-audio-preview" src="${t.url}"></audio>
        </div>
        <div class="asset-details">
          <span class="asset-title" title="${t.filename}">${t.filename}</span>
          <div class="asset-meta"><span>${sizeStr}</span></div>
        </div>
        <div class="asset-actions-overlay">
          <button class="action-icon-btn play-btn" onclick="event.stopPropagation(); toggleAudioPreview(this)">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" class="play-svg"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>
          </button>
          <button class="action-icon-btn delete-btn" onclick="event.stopPropagation(); deleteAsset('music', '${t.filename}')">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
          </button>
        </div>
      `;
      
      if (context === 'modal') {
        card.addEventListener('click', () => selectAssetFromModal(`music/${t.filename}`));
      }
      
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = '<div class="empty-state">Failed to load audio files.</div>';
    showToast('Failed to load music', 'error');
  }
}

export function toggleAudioPreview(btn) {
  const audio = btn.closest('.asset-card').querySelector('audio');
  const playSvg = `<path d="M8 5v14l11-7z" fill="currentColor"/>`;
  const pauseSvg = `<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="currentColor"/>`;
  
  document.querySelectorAll('.asset-card audio').forEach(aud => {
    if (aud !== audio && !aud.paused) {
      aud.pause();
      aud.currentTime = 0;
      const otherBtn = aud.closest('.asset-card').querySelector('.play-btn');
      if (otherBtn) otherBtn.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" class="play-svg">${playSvg}</svg>`;
    }
  });
  
  if (audio.paused) {
    audio.play();
    btn.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" class="play-svg">${pauseSvg}</svg>`;
  } else {
    audio.pause();
    btn.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" class="play-svg">${playSvg}</svg>`;
  }
}

async function deleteAsset(type, filename) {
  if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
  
  try {
    if (type === 'video') await api.deleteVideo(filename);
    else await api.deleteMusic(filename);
    
    showToast('Asset deleted', 'success');
    await refreshAssetsList();
    await api.fetchState();
  } catch (err) {
    showToast(`Failed to delete asset: ${err.message}`, 'error');
  }
}

export async function searchPexels(context) {
  const inputEl = context === 'main' ? document.getElementById('pexels-query-input') : document.getElementById('modal-pexels-query');
  const gridEl = context === 'main' ? document.getElementById('pexels-results-grid') : document.getElementById('modal-asset-grid');
  
  const query = inputEl.value.trim();
  if (!query) {
    if (context === 'modal' && state.app.script_text) {
      inputEl.value = 'Extracting keyword...';
      try {
        const data = await api.extractKeyword();
        inputEl.value = data.keyword;
        searchPexels(context);
      } catch (e) {
        inputEl.value = '';
      }
      return;
    }
    showToast('Please enter a query to search Pexels.', 'warning');
    return;
  }
  
  gridEl.innerHTML = '<div class="empty-state">Searching Pexels for vertical videos...</div>';
  
  try {
    const data = await api.searchPexels(query);
    const videos = data.videos || [];
    
    if (videos.length === 0) {
      gridEl.innerHTML = `<div class="empty-state">No matching vertical videos found. Try another concept.</div>`;
      return;
    }
    
    gridEl.innerHTML = '';
    videos.forEach(v => {
      const card = document.createElement('div');
      card.className = 'pexels-card';
      
      card.innerHTML = `
        <div class="pexels-thumbnail">
          <img class="pexels-img" src="${v.thumbnail}" alt="Pexels Loop">
          <span class="pexels-duration-badge">${v.duration}s</span>
          <span class="pexels-author-badge">By ${v.user}</span>
        </div>
        <div class="pexels-card-body">
          <div class="pexels-actions">
            ${context === 'modal' ? `
              <button class="btn btn-sm btn-primary" onclick="downloadPexelsVideo('${v.download_url}', ${v.id}, '${query}')">Choose & Download</button>
            ` : `
              <button class="btn btn-sm btn-primary" onclick="downloadPexelsVideo('${v.download_url}', ${v.id}, '${query}', 'top')">Get as Top</button>
              <button class="btn btn-sm btn-secondary" onclick="downloadPexelsVideo('${v.download_url}', ${v.id}, '${query}', 'bottom')">Get as Bottom</button>
            `}
          </div>
        </div>
      `;
      gridEl.appendChild(card);
    });
  } catch (err) {
    gridEl.innerHTML = `<div class="empty-state text-danger">Failed to search. Check API settings.</div>`;
    showToast(`Pexels search failed: ${err.message}`, 'error');
  }
}

export async function downloadPexelsVideo(url, id, query, positionOverride) {
  const position = positionOverride || state.activeSelectorTarget || 'top';
  
  if (!positionOverride) {
    closeAssetSelector();
  }
  
  appendConsoleLog(`[Pexels Download Started] Triggered download for ${position} video (${id}). Please wait...`, 'system');
  showToast('Download started...', 'info');
  
  try {
    const data = await api.downloadPexelsVideo(url, id, query, position);
    appendConsoleLog(`[Pexels Download Triggered] File: ${data.filename}`, 'system');
    
    let checkCount = 0;
    const stateKey = position === 'top' ? 'bg_video_path' : 'bg_video_bottom_path';
    
    const checkInterval = setInterval(async () => {
      await api.fetchState();
      checkCount++;
      if (state.app[stateKey] && state.app[stateKey].includes(data.filename)) {
        clearInterval(checkInterval);
        appendConsoleLog(`[Pexels Download Complete] Loaded background video: ${data.filename}`, 'system');
        updateSelectedAssetsDisplay();
        showToast('Download complete', 'success');
      }
      if (checkCount > 60) {
        clearInterval(checkInterval);
        showToast('Download check timeout, but it might still be running', 'warning');
      }
    }, 1500);
  } catch (err) {
    showToast(`Download failed: ${err.message}`, 'error');
  }
}

function setupDropzones() {
  const dropzones = [
    { zoneId: 'video-dropzone', inputId: 'video-file-input', type: 'video' },
    { zoneId: 'music-dropzone', inputId: 'music-file-input', type: 'music' }
  ];
  
  dropzones.forEach(pair => {
    const zone = document.getElementById(pair.zoneId);
    const input = document.getElementById(pair.inputId);
    if (!zone || !input) return;
    
    zone.addEventListener('click', () => input.click());
    
    input.addEventListener('change', () => {
      if (input.files.length > 0) uploadFile(input.files[0], pair.type);
    });
    
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('dragover');
    });
    
    zone.addEventListener('dragleave', () => {
      zone.classList.remove('dragover');
    });
    
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0], pair.type);
    });
  });
}

export async function uploadFile(file, typeContext) {
  const type = typeContext === 'auto' ? (state.activeSelectorTarget === 'music' ? 'music' : 'video') : typeContext;
  
  appendConsoleLog(`[Upload Started] Sending "${file.name}" to server...`, 'system');
  showToast(`Uploading ${file.name}...`, 'info');
  
  try {
    const data = await api.uploadAsset(file, type);
    appendConsoleLog(`[Upload Success] File saved: ${data.filename}`, 'system');
    showToast('Upload successful', 'success');
    
    await refreshAssetsList();
    
    const isModalOpen = document.getElementById('asset-selector-modal')?.style.display === 'flex';
    if (isModalOpen) {
      const pathVal = type === 'video' ? `videos/${data.filename}` : `music/${data.filename}`;
      selectAssetFromModal(pathVal);
    }
  } catch (err) {
    showToast(`Upload error: ${err.message}`, 'error');
  }
}
