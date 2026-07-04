import { state } from '../state.js';
import { updateSelectedAssetsDisplay, syncStudioUI } from './studio.js';
import { updatePresetBadge } from './sidebar.js';
import * as api from '../api.js';
import { showToast } from '../toast.js';
import { renderMusicGrid, renderVideosGrid, uploadFile, searchPexels } from './mediaManager.js';

export function initModal() {
  const closeBtn = document.querySelector('.close-modal-btn');
  if (closeBtn) closeBtn.addEventListener('click', closeAssetSelector);
  
  const modal = document.getElementById('asset-selector-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeAssetSelector();
    });
  }
  
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && modal.style.display === 'flex') {
      closeAssetSelector();
    }
  });
  
  const pexelsBtn = document.getElementById('btn-modal-search-pexels');
  if (pexelsBtn) {
    pexelsBtn.addEventListener('click', () => searchPexels('modal'));
  }
  
  // Set up modal dropzone
  const zone = document.getElementById('modal-upload-zone');
  const input = document.getElementById('modal-file-input');
  if (zone && input) {
    zone.addEventListener('click', () => input.click());
    
    input.addEventListener('change', () => {
      if (input.files.length > 0) uploadFile(input.files[0], 'auto');
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
      if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0], 'auto');
    });
  }
  
  window.openAssetSelector = openAssetSelector;
  window.closeAssetSelector = closeAssetSelector;
  window.selectAssetFromModal = selectAssetFromModal;
}

export function openAssetSelector(target) {
  state.activeSelectorTarget = target;
  const modal = document.getElementById('asset-selector-modal');
  const title = document.getElementById('modal-select-title');
  const pexelsBar = document.getElementById('modal-pexels-search-bar');
  
  if (!modal || !title || !pexelsBar) return;
  
  title.textContent = `Select Background ${target === 'music' ? 'Audio Track' : 'Video'}`;
  
  if (target === 'top' || target === 'bottom') {
    pexelsBar.classList.remove('hidden');
    document.getElementById('modal-pexels-query').value = '';
  } else {
    pexelsBar.classList.add('hidden');
  }
  
  if (target === 'music') {
    renderMusicGrid('modal');
  } else {
    renderVideosGrid('modal');
  }
  
  modal.style.display = 'flex';
}

export function closeAssetSelector() {
  const modal = document.getElementById('asset-selector-modal');
  if (modal) modal.style.display = 'none';
}

export async function selectAssetFromModal(value) {
  if (state.activeSelectorTarget === 'top') {
    state.app.bg_video_path = value;
  } else if (state.activeSelectorTarget === 'bottom') {
    state.app.bg_video_bottom_path = value;
  } else if (state.activeSelectorTarget === 'music') {
    state.app.bg_music_path = value;
  }
  
  state.app.loaded_preset_name = null;
  updatePresetBadge('None (Custom)');
  
  try {
    await api.saveState();
    updateSelectedAssetsDisplay();
    syncStudioUI();
    closeAssetSelector();
    showToast('Asset selected', 'info');
  } catch (err) {
    showToast(`Failed to save state: ${err.message}`, 'error');
  }
}
