import { state, emit } from '../state.js';
import { refreshAssetsList } from './mediaManager.js';
import { refreshGallery } from './gallery.js';
import { renderPresetsList } from './presets.js';

export function initSidebar() {
  const sidebarNav = document.querySelector('.sidebar-nav');
  const tabPanes = document.querySelectorAll('.tab-pane');
  
  if (sidebarNav) {
    sidebarNav.addEventListener('click', (e) => {
      const btn = e.target.closest('.nav-btn');
      if (!btn) return;
      
      const tabId = btn.dataset.tab;
      
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      tabPanes.forEach(pane => {
        if (pane.id === `tab-${tabId}`) {
          pane.classList.add('active');
          if (tabId === 'assets') refreshAssetsList();
          else if (tabId === 'gallery') refreshGallery();
          else if (tabId === 'presets') renderPresetsList();
        } else {
          pane.classList.remove('active');
        }
      });
      
      emit('tab-changed', tabId);
      
      // Close mobile menu if open
      if (window.innerWidth <= 768) {
        document.querySelector('.sidebar')?.classList.remove('open');
      }
    });
  }
  
  const sidebarToggle = document.getElementById('sidebar-toggle');
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
      state.sidebarCollapsed = !state.sidebarCollapsed;
      document.querySelector('.app-container')?.classList.toggle('sidebar-collapsed', state.sidebarCollapsed);
      document.querySelector('.sidebar')?.classList.toggle('collapsed', state.sidebarCollapsed);
    });
  }
  
  const mobileMenuBtn = document.getElementById('mobile-menu-btn');
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', () => {
      document.querySelector('.sidebar')?.classList.toggle('open');
    });
  }
}

export function updatePresetBadge(name) {
  const badge = document.getElementById('active-preset-badge');
  if (badge) {
    badge.textContent = name || 'None (Custom)';
  }
}
