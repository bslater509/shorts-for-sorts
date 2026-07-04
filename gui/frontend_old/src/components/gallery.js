import * as api from '../api.js';
import { showToast } from '../toast.js';

export function initGallery() {
  const btn = document.getElementById('btn-refresh-gallery');
  if (btn) {
    btn.addEventListener('click', refreshGallery);
  }
  window.deleteGalleryShort = deleteGalleryShort;
}

export async function refreshGallery() {
  const grid = document.getElementById('gallery-grid');
  if (!grid) return;
  
  grid.innerHTML = Array(4).fill(
    '<div class="gallery-card"><div class="skeleton skeleton-card" style="height:420px"></div><div style="padding:0.85rem"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text short"></div></div></div>'
  ).join('');
  
  try {
    const videos = await api.fetchGallery();
    
    if (videos.length === 0) {
      grid.innerHTML = '<div class="empty-state">No compiled vertical shorts found. Compile one in Studio!</div>';
      return;
    }
    
    grid.innerHTML = '';
    videos.forEach(v => {
      const card = document.createElement('div');
      card.className = 'gallery-card';
      
      let sizeStr = `${(v.size / (1024 * 1024)).toFixed(1)} MB`;
      let durationStr = v.duration ? `${v.duration.toFixed(1)}s` : '';
      let dateStr = new Date(v.modified * 1000).toLocaleString();
      
      card.innerHTML = `
        <div class="gallery-video-container">
          <video class="gallery-video" src="${v.url}" controls playsinline></video>
        </div>
        <div class="gallery-card-body">
          <div class="gallery-card-title" title="${v.filename}">${v.filename}</div>
          <div class="gallery-card-meta">
            <span>${durationStr || 'Short'} (${sizeStr})</span>
            <span>${dateStr}</span>
          </div>
          <div class="gallery-card-actions">
            <a href="${v.url}" download="${v.filename}" class="btn btn-sm btn-primary">Download</a>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteGalleryShort('${v.filename}')">Delete</button>
          </div>
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = '<div class="empty-state text-danger">Failed to load video catalog.</div>';
    showToast('Failed to load gallery', 'error');
  }
}

export async function deleteGalleryShort(filename) {
  if (!confirm(`Are you sure you want to delete this completed video: "${filename}"?`)) return;
  
  try {
    await api.deleteGalleryVideo(filename);
    showToast('Video deleted successfully', 'success');
    await refreshGallery();
  } catch (err) {
    showToast(`Failed to delete video: ${err.message}`, 'error');
  }
}
