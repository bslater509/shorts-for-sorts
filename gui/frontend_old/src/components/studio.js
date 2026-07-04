import { state } from '../state.js';
import * as api from '../api.js';
import { debounce, getBaseName, countWords } from '../utils.js';
import { showToast } from '../toast.js';
import { updatePresetBadge } from './sidebar.js';
import { appendConsoleLog } from './terminal.js';
import { refreshGallery } from './gallery.js';
import { openAssetSelector } from './modal.js';

export function initStudio() {
  const genBtn = document.getElementById('btn-generate-script');
  if (genBtn) genBtn.addEventListener('click', generateScript);
  
  const textArea = document.getElementById('script-text-area');
  if (textArea) {
    textArea.addEventListener('input', () => {
      updateWordCount();
      debouncedSaveScript();
    });
    textArea.addEventListener('blur', () => {
      state.app.script_text = textArea.value;
      api.saveState();
    });
  }
  
  const voiceSelect = document.getElementById('voice-select');
  if (voiceSelect) {
    voiceSelect.addEventListener('change', (e) => {
      state.app.selected_voice = e.target.value;
      state.app.loaded_preset_name = null;
      api.saveState();
      updatePresetBadge('None (Custom)');
      syncStudioUI();
    });
  }
  
  const animSelect = document.getElementById('anim-select');
  if (animSelect) {
    animSelect.addEventListener('change', (e) => {
      state.app.sub_animation_style = e.target.value;
      state.app.loaded_preset_name = null;
      api.saveState();
      updatePresetBadge('None (Custom)');
      syncStudioUI();
    });
  }
  
  const compileBtn = document.getElementById('btn-compile-video');
  if (compileBtn) compileBtn.addEventListener('click', compileVideo);
  
  const cancelBtn = document.getElementById('btn-cancel-compile');
  if (cancelBtn) cancelBtn.addEventListener('click', cancelCompilation);
  
  const topVideoBtn = document.getElementById('btn-choose-top-video');
  if (topVideoBtn) topVideoBtn.addEventListener('click', () => openAssetSelector('top'));
  
  const bottomVideoBtn = document.getElementById('btn-choose-bottom-video');
  if (bottomVideoBtn) bottomVideoBtn.addEventListener('click', () => openAssetSelector('bottom'));
  
  const musicBtn = document.getElementById('btn-choose-music');
  if (musicBtn) musicBtn.addEventListener('click', () => openAssetSelector('music'));
  
  const disableSplitBtn = document.getElementById('btn-disable-split');
  if (disableSplitBtn) {
    disableSplitBtn.addEventListener('click', () => {
      state.app.bg_video_bottom_path = null;
      api.saveState();
      updateSelectedAssetsDisplay();
    });
  }

  // Wizard Flow Logic
  document.querySelectorAll('.btn-next-step').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const nextStep = e.currentTarget.dataset.next;
      goToWizardStep(nextStep);
    });
  });

  document.querySelectorAll('.btn-prev-step').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const prevStep = e.currentTarget.dataset.prev;
      goToWizardStep(prevStep);
    });
  });

  const showCompilerBtn = document.getElementById('btn-show-compiler');
  if (showCompilerBtn) {
    showCompilerBtn.addEventListener('click', () => {
      document.getElementById('compiler-overlay')?.classList.remove('hidden');
    });
  }

  const closeCompilerBtn = document.getElementById('btn-close-compiler');
  if (closeCompilerBtn) {
    closeCompilerBtn.addEventListener('click', () => {
      document.getElementById('compiler-overlay')?.classList.add('hidden');
    });
  }

  setupStudioEventListeners();
}

function goToWizardStep(stepNum) {
  document.querySelectorAll('.wizard-step').forEach(step => {
    step.classList.add('hidden');
    step.classList.remove('active');
  });
  const targetStep = document.getElementById(`wizard-step-${stepNum}`);
  if (targetStep) {
    targetStep.classList.remove('hidden');
    // small timeout to allow display:block to apply before animation classes trigger
    setTimeout(() => {
      targetStep.classList.add('active');
    }, 10);
  }
}

const debouncedSaveScript = debounce(() => {
  const textArea = document.getElementById('script-text-area');
  if (textArea && state.app) {
    state.app.script_text = textArea.value;
    api.saveState().catch(e => console.error(e));
  }
}, 300);

export function syncStudioUI() {
  if (!state.app) return;
  
  const textArea = document.getElementById('script-text-area');
  if (textArea) textArea.value = state.app.script_text || '';
  
  const voiceSelect = document.getElementById('voice-select');
  if (voiceSelect) voiceSelect.value = state.app.selected_voice || 'af_sarah';
  
  const animSelect = document.getElementById('anim-select');
  if (animSelect) animSelect.value = state.app.sub_animation_style || 'tiktok_pop';
  
  updatePresetBadge(state.app.loaded_preset_name);
  updateSelectedAssetsDisplay();
  
  // Also populate voice dropdowns if not populated
  if (state.voices && state.voices.length > 0) {
    const voiceOptions = state.voices.map(v => `<option value="${v.value}">${v.name}</option>`).join('');
    if (voiceSelect && voiceSelect.children.length <= 1) voiceSelect.innerHTML = voiceOptions;
    
    const genSelect = document.getElementById('generate-voice-select');
    if (genSelect && genSelect.children.length <= 1) {
      genSelect.innerHTML = `<option value="">Default/Current</option>` + voiceOptions;
    }
    
    const presetSelect = document.getElementById('preset-voice-select');
    if (presetSelect && presetSelect.children.length <= 1) {
      presetSelect.innerHTML = voiceOptions;
    }
  }
}

export function renderStudioPresetsGrid() {
  const grid = document.getElementById('preset-quick-list');
  if (!grid || !state.presets) return;
  
  grid.innerHTML = '';
  
  Object.keys(state.presets).forEach(name => {
    const card = document.createElement('div');
    card.className = 'preset-card-quick';
    if (state.app.loaded_preset_name === name) {
      card.classList.add('active');
    }
    card.textContent = name;
    card.addEventListener('click', () => selectPreset(name));
    grid.appendChild(card);
  });
}

export async function selectPreset(presetName) {
  const preset = state.presets[presetName];
  if (!preset) return;
  
  state.app.loaded_preset_name = presetName;
  Object.assign(state.app, preset); // copy all properties
  
  syncStudioUI();
  
  document.querySelectorAll('.preset-card-quick').forEach(card => {
    if (card.textContent === presetName) card.classList.add('active');
    else card.classList.remove('active');
  });
  
  try {
    await api.saveState();
    showToast(`Preset "${presetName}" applied`, 'success');
  } catch (e) {
    showToast(`Error applying preset: ${e.message}`, 'error');
  }
}

export function updateSelectedAssetsDisplay() {
  const topName = getBaseName(state.app.bg_video_path) || 'Not configured';
  const elTop = document.getElementById('top-video-name');
  if (elTop) elTop.textContent = topName;
  
  const botName = getBaseName(state.app.bg_video_bottom_path) || 'None (Disable Split Screen)';
  const elBot = document.getElementById('bottom-video-name');
  if (elBot) elBot.textContent = botName;
  
  const musName = getBaseName(state.app.bg_music_path) || 'None';
  const elMus = document.getElementById('music-name');
  if (elMus) elMus.textContent = musName;
}

export function updateWordCount() {
  const textArea = document.getElementById('script-text-area');
  const countSpan = document.getElementById('script-word-count');
  if (textArea && countSpan) {
    countSpan.textContent = `${countWords(textArea.value)} words`;
  }
}

async function generateScript() {
  const promptInput = document.getElementById('ai-prompt-input');
  const prompt = promptInput?.value.trim();
  
  if (!prompt) {
    showToast('Please enter a script topic or instruction.', 'warning');
    return;
  }
  
  const voiceOverride = document.getElementById('generate-voice-select')?.value;
  const btn = document.getElementById('btn-generate-script');
  
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="pulse">Generating Script...</span>`;
  }
  
  try {
    const data = await api.generateScript(prompt, voiceOverride, null);
    
    const textArea = document.getElementById('script-text-area');
    if (textArea) textArea.value = data.script;
    state.app.script_text = data.script;
    
    if (voiceOverride) {
      state.app.selected_voice = voiceOverride;
    }
    state.app.loaded_preset_name = null;
    
    updateWordCount();
    syncStudioUI();
    await api.saveState();
    
    appendConsoleLog(`[AI Script Generated Successfully]\n"${data.script}"\n`, 'system');
    showToast('Script generated successfully', 'success');
  } catch (err) {
    showToast(`Generation Failed: ${err.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" class="btn-svg" width="16" height="16"><path d="M19 9 20.25 11.75 23 13 20.25 14.25 19 17 17.75 14.25 15 13 17.75 11.75 19 9M9 4 11.5 9.5 17 12 11.5 14.5 9 20 6.5 14.5 1 12 6.5 9.5 9 4Z" fill="currentColor"/></svg>
        Generate Script`;
    }
  }
}

async function compileVideo() {
  const textArea = document.getElementById('script-text-area');
  if (textArea) state.app.script_text = textArea.value;
  
  try {
    await api.saveState();
  } catch (err) {
    showToast(`Failed to save state before compile: ${err.message}`, 'error');
    return;
  }
  
  const customFilename = document.getElementById('output-filename-input')?.value;
  const banner = document.getElementById('compile-status-container');
  const progressBar = document.getElementById('compile-progress-bar');
  const btn = document.getElementById('btn-compile-video');
  const errorBox = document.getElementById('error-alert-box');
  const terminalDrawer = document.getElementById('terminal-drawer');
  const badge = document.getElementById('compile-status-badge');
  
  if (banner) banner.classList.remove('hidden');
  if (errorBox) errorBox.classList.add('hidden');
  if (terminalDrawer) terminalDrawer.classList.add('hidden');
  if (progressBar) progressBar.style.width = '10%';
  if (badge) badge.textContent = 'Starting...';
  if (btn) btn.disabled = false;
  
  // Reset stepper
  document.querySelectorAll('.step').forEach(step => {
    step.classList.remove('active', 'completed');
  });
  document.getElementById('step-1')?.classList.add('active');
  
  appendConsoleLog('\n[System Log] Triggering compilation thread on backend...', 'system');
  
  try {
    await api.startCompilation(customFilename);
    appendConsoleLog('[System Log] Background compilation worker spawned successfully.', 'system');
    showToast('Compilation started', 'info');
    startCompilationPolling();
  } catch (err) {
    showToast(`Compilation failed to start: ${err.message}`, 'error');
    if (btn) btn.disabled = false;
    if (banner) banner.classList.add('hidden');
  }
}

export function startCompilationPolling() {
  if (state.compilationPollInterval) clearInterval(state.compilationPollInterval);
  
  const progressBar = document.getElementById('compile-progress-bar');
  let lastLogLength = 0;
  
  state.compilationPollInterval = setInterval(async () => {
    try {
      const data = await api.getCompilationStatus();
      
      if (data.logs && data.logs.length < lastLogLength) {
        lastLogLength = 0;
      }
      if (data.logs && data.logs.length > lastLogLength) {
        const newChunk = data.logs.substring(lastLogLength);
        lastLogLength = data.logs.length;
        appendConsoleLog(newChunk);
      }
      
      const logsText = data.logs || '';
      let progress = 10;
      let currentStep = 1;
      let badgeText = 'Starting...';

      if (logsText.includes('[1/4]') || logsText.includes('Generated sentence')) {
          progress = 25;
          currentStep = 2;
          badgeText = 'Generating Audio...';
      }
      if (logsText.includes('Generating & transcribing sentence')) {
        currentStep = 2;
        badgeText = 'Generating Audio...';
        const matches = logsText.match(/sentence (\d+)\/(\d+)/g);
        if (matches && matches.length > 0) {
          const numMatch = matches[matches.length - 1].match(/sentence (\d+)\/(\d+)/);
          if (numMatch) {
            const current = parseInt(numMatch[1]);
            const total = parseInt(numMatch[2]);
            progress = 25 + Math.floor((current / total) * 20);
          }
        }
      }
      if (logsText.includes('[3/4]') || logsText.includes('ASS subtitles generated')) {
          progress = 55;
          currentStep = 3;
          badgeText = 'Generating Subtitles...';
      }
      if (logsText.includes('[4/4]') || logsText.includes('Rendering vertical video')) {
          progress = 70;
          currentStep = 4;
          badgeText = 'Rendering Video...';
      }
      if (logsText.includes('frame=')) {
          progress = 85;
          currentStep = 4;
          badgeText = 'Rendering Video...';
      }
      if (logsText.includes('RENDER SUCCESSFUL')) {
          progress = 100;
          currentStep = 4;
          badgeText = 'Complete!';
      }
      
      const badge = document.getElementById('compile-status-badge');
      if (badge) {
        let text = badgeText;
        if (data.queue_size && data.queue_size > 0) {
           text += " (Queue: " + data.queue_size + ")";
        }
        badge.textContent = text;
      }

      // Update Stepper UI
      document.querySelectorAll('.step').forEach((step, idx) => {
          const stepNum = idx + 1;
          if (stepNum < currentStep) {
              step.classList.remove('active');
              step.classList.add('completed');
          } else if (stepNum === currentStep) {
              step.classList.add('active');
              step.classList.remove('completed');
          } else {
              step.classList.remove('active', 'completed');
          }
      });
      if (progress === 100) {
          document.querySelectorAll('.step').forEach(step => {
              step.classList.remove('active');
              step.classList.add('completed');
          });
      }
      
      if (progressBar) progressBar.style.width = `${progress}%`;
      
      if (!data.in_progress) {
        clearInterval(state.compilationPollInterval);
        state.compilationPollInterval = null;
        
        const btn = document.getElementById('btn-compile-video');
        if (btn) btn.disabled = false;
        
        if (data.success) {
          if (progressBar) progressBar.style.width = '100%';
          if (badge) badge.textContent = 'Complete!';
          document.querySelectorAll('.step').forEach(step => {
              step.classList.remove('active');
              step.classList.add('completed');
          });
          setTimeout(() => {
              const banner = document.getElementById('compile-status-container');
              if (banner) banner.classList.add('hidden');
              const terminalDrawer = document.getElementById('terminal-drawer');
              if (terminalDrawer) terminalDrawer.classList.add('hidden');
          }, 3000);
          appendConsoleLog('\n[System Log] Video short generated successfully! Reloading video gallery...', 'system');
          showToast('Short compilation successful!', 'success');
          await refreshGallery();
        } else {
          const errorBox = document.getElementById('error-alert-box');
          const banner = document.getElementById('compile-status-container');
          
          if (banner) banner.classList.add('hidden');
          if (errorBox) {
              errorBox.classList.remove('hidden');
              const errText = document.getElementById('error-message-text');
              if (errText) errText.textContent = "Compilation failed. Check the detailed logs for more info.";
          }
          appendConsoleLog('\n[System Log] Video short generation failed. Check errors above.', 'system');
          showToast('Compilation failed. Check logs in the Console panel.', 'error');
        }
      }
    } catch (err) {
      console.error('Polling error:', err);
    }
  }, 1000);
}

async function cancelCompilation() {
  try {
    const data = await api.cancelCompilation();
    appendConsoleLog(`[System Log] Cancel request sent: ${data.message || 'ok'}`, 'system');
    showToast('Cancel request sent', 'info');
  } catch (err) {
    showToast(`Cancel failed: ${err.message}`, 'error');
  }
}

export function setupStudioEventListeners() {
    const btnToggleLogs = document.getElementById('btn-toggle-logs');
    if (btnToggleLogs) {
        btnToggleLogs.addEventListener('click', () => {
            const drawer = document.getElementById('terminal-drawer');
            if (drawer) {
                drawer.classList.toggle('hidden');
                if (!drawer.classList.contains('hidden')) {
                    const consoleBody = document.getElementById('compiler-console');
                    if (consoleBody) consoleBody.scrollTop = consoleBody.scrollHeight;
                }
            }
        });
    }
}

