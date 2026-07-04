// State variables for Web GUI client
let appState = {};
let appSettings = {};
let appPresets = {};
let appVoices = [];

let activeSelectorTarget = ''; // 'top', 'bottom', or 'music'
let compilationPollInterval = null;

// DOM Elements
const sidebarNav = document.querySelector('.sidebar-nav');
const tabPanes = document.querySelectorAll('.tab-pane');
const activePresetBadge = document.getElementById('active-preset-badge');

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// Setup tab routing, listeners, and load data
async function initApp() {
    setupTabNavigation();
    setupMediaTabs();
    setupDropzones();
    setupEventHandlers();
    
    // Initial fetch of data
    await fetchVoices();
    await fetchState();
    await fetchSettings();
    await fetchPresets();
    await refreshGallery();
    
    // Check if compilation is already running in background
    checkActiveCompilation();
}

// Sidebar tab switching logic
function setupTabNavigation() {
    sidebarNav.addEventListener('click', (e) => {
        const btn = e.target.closest('.nav-btn');
        if (!btn) return;
        
        const tabId = btn.dataset.tab;
        
        // Update active class on buttons
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Show/hide panes
        tabPanes.forEach(pane => {
            if (pane.id === `tab-${tabId}`) {
                pane.classList.add('active');
                // Auto refresh lists if needed
                if (tabId === 'assets') {
                    refreshAssetsList();
                } else if (tabId === 'gallery') {
                    refreshGallery();
                } else if (tabId === 'presets') {
                    renderPresetsList();
                }
            } else {
                pane.classList.remove('active');
            }
        });
    });
}

// Media Manager internal tabs
function setupMediaTabs() {
    const tabContainer = document.querySelector('.media-tabs-header');
    if (!tabContainer) return;
    
    tabContainer.addEventListener('click', (e) => {
        const btn = e.target.closest('.media-tab-btn');
        if (!btn) return;
        
        document.querySelectorAll('.media-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        const targetPaneId = `pane-${btn.dataset.media}`;
        document.querySelectorAll('.media-pane').forEach(pane => {
            if (pane.id === targetPaneId) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });
        
        // Trigger specific loads
        refreshAssetsList();
    });
}

// Events
function setupEventHandlers() {
    // Generate script
    document.getElementById('btn-generate-script').addEventListener('click', generateScript);
    
    // Save settings
    document.getElementById('btn-save-settings').addEventListener('click', saveSettingsToServer);
    
    // Save state when editing script area on blur
    document.getElementById('script-text-area').addEventListener('blur', () => {
        appState.script_text = document.getElementById('script-text-area').value;
        saveState();
        updateWordCount();
    });
    
    document.getElementById('script-text-area').addEventListener('input', updateWordCount);
    
    // Compile trigger
    document.getElementById('btn-compile-video').addEventListener('click', compileVideo);
    
    // Cancel compilation
    document.getElementById('btn-cancel-compile').addEventListener('click', cancelCompilation);
    
    // Refresh gallery
    document.getElementById('btn-refresh-gallery').addEventListener('click', refreshGallery);
    
    // Clear terminal logs
    document.getElementById('btn-clear-logs').addEventListener('click', () => {
        document.getElementById('compiler-console').innerHTML = '';
    });
    
    // Preset styling bindings
    document.getElementById('btn-save-custom-preset').addEventListener('click', saveCustomPresetToServer);
    
    // Sync text inputs with hex color pickers in Preset Designer
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
    
    // Hide/show whisper fields dynamically in Settings form
    const whisperModeSelect = document.getElementById('settings-whisper-mode');
    whisperModeSelect.addEventListener('change', () => {
        const localRow = document.getElementById('settings-whisper-model-row');
        const apiFields = document.getElementById('settings-whisper-api-fields');
        if (whisperModeSelect.value === 'local') {
            localRow.classList.remove('hidden');
            apiFields.classList.add('hidden');
        } else {
            localRow.classList.add('hidden');
            apiFields.classList.remove('hidden');
        }
    });
    
    // Search Pexels Tab
    document.getElementById('btn-search-pexels').addEventListener('click', () => {
        searchPexels('main');
    });
    
    // Search Pexels Modal
    document.getElementById('btn-modal-search-pexels').addEventListener('click', () => {
        searchPexels('modal');
    });
    
    // Disable split screen
    document.getElementById('btn-disable-split').addEventListener('click', () => {
        appState.bg_video_bottom_path = null;
        saveState();
        updateSelectedAssetsDisplay();
    });
    
    // Voice select change in studio
    document.getElementById('voice-select').addEventListener('change', (e) => {
        appState.selected_voice = e.target.value;
        appState.loaded_preset_name = null;
        saveState();
        activePresetBadge.textContent = 'None (Custom)';
    });
    
    // Animation select change in studio
    document.getElementById('anim-select').addEventListener('change', (e) => {
        appState.sub_animation_style = e.target.value;
        appState.loaded_preset_name = null;
        saveState();
        activePresetBadge.textContent = 'None (Custom)';
    });
}

// Word Count Counter
function updateWordCount() {
    const text = document.getElementById('script-text-area').value.trim();
    const count = text ? text.split(/\s+/).length : 0;
    document.getElementById('script-word-count').textContent = `${count} words`;
}

// Fetch APIs

async function fetchState() {
    try {
        const res = await fetch('/api/state');
        appState = await res.json();
        
        // Sync to UI
        document.getElementById('script-text-area').value = appState.script_text || '';
        document.getElementById('voice-select').value = appState.selected_voice || 'af_sarah';
        document.getElementById('anim-select').value = appState.sub_animation_style || 'tiktok_pop';
        
        activePresetBadge.textContent = appState.loaded_preset_name || 'None (Custom)';
        
        updateSelectedAssetsDisplay();
        updateWordCount();
    } catch (err) {
        console.error('Failed to fetch state:', err);
    }
}

async function fetchSettings() {
    try {
        const res = await fetch('/api/settings');
        appSettings = await res.json();
        
        // Populate Settings Form
        document.getElementById('settings-api-key').value = appSettings.api_key || '';
        document.getElementById('settings-base-url').value = appSettings.base_url || '';
        document.getElementById('settings-model').value = appSettings.model || 'gpt-4o-mini';
        document.getElementById('settings-max-words').value = appSettings.max_words || 130;
        document.getElementById('settings-pexels-key').value = appSettings.pexels_api_key || '';
        
        const whisperModeSelect = document.getElementById('settings-whisper-mode');
        whisperModeSelect.value = appSettings.local_whisper ? 'local' : 'api';
        whisperModeSelect.dispatchEvent(new Event('change'));
        
        document.getElementById('settings-whisper-model').value = appSettings.local_whisper_model || 'tiny';
        document.getElementById('settings-whisper-key').value = appSettings.whisper_api_key || '';
        document.getElementById('settings-whisper-url').value = appSettings.whisper_base_url || '';
        
        document.getElementById('settings-render-res').value = appSettings.render_resolution || '1080p';
        document.getElementById('settings-render-preset').value = appSettings.render_preset || 'veryfast';
        document.getElementById('settings-video-encoder').value = appSettings.video_encoder || 'libx264';
    } catch (err) {
        console.error('Failed to fetch settings:', err);
    }
}

async function saveSettingsToServer() {
    const payload = {
        api_key: document.getElementById('settings-api-key').value,
        base_url: document.getElementById('settings-base-url').value,
        model: document.getElementById('settings-model').value,
        max_words: parseInt(document.getElementById('settings-max-words').value) || 130,
        pexels_api_key: document.getElementById('settings-pexels-key').value,
        local_whisper: document.getElementById('settings-whisper-mode').value === 'local',
        local_whisper_model: document.getElementById('settings-whisper-model').value,
        whisper_api_key: document.getElementById('settings-whisper-key').value,
        whisper_base_url: document.getElementById('settings-whisper-url').value,
        render_resolution: document.getElementById('settings-render-res').value,
        render_preset: document.getElementById('settings-render-preset').value,
        video_encoder: document.getElementById('settings-video-encoder').value,
    };
    
    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const ans = await res.json();
        if (ans.status === 'success') {
            alert('Settings saved successfully!');
            await fetchSettings();
        } else {
            alert('Error: ' + ans.detail);
        }
    } catch (err) {
        alert('Server connection failed: ' + err);
    }
}

async function fetchPresets() {
    try {
        const res = await fetch('/api/presets');
        appPresets = await res.json();
        
        // Render presets quick selector in Studio
        renderStudioPresetsGrid();
        // Render list in Presets Tab
        renderPresetsList();
    } catch (err) {
        console.error('Failed to fetch presets:', err);
    }
}

async function fetchVoices() {
    try {
        const res = await fetch('/api/voices');
        appVoices = await res.json();
        
        // Populate dropdowns
        const studioVoiceSelect = document.getElementById('voice-select');
        const generateVoiceSelect = document.getElementById('generate-voice-select');
        const presetVoiceSelect = document.getElementById('preset-voice-select');
        
        const voiceOptions = appVoices.map(v => `<option value="${v.value}">${v.name}</option>`).join('');
        
        studioVoiceSelect.innerHTML = voiceOptions;
        generateVoiceSelect.innerHTML = `<option value="">Default/Current</option>` + voiceOptions;
        presetVoiceSelect.innerHTML = voiceOptions;
    } catch (err) {
        console.error('Failed to fetch voices:', err);
    }
}

// Display configurations
function updateSelectedAssetsDisplay() {
    // Helper to format basename path
    const getBaseName = (path) => {
        if (!path) return '';
        if (path === 'random') return 'Random Selection';
        return path.split(/[\\/]/).pop();
    };
    
    // Top Background
    const topName = getBaseName(appState.bg_video_path) || 'Not configured';
    document.getElementById('top-video-name').textContent = topName;
    
    // Bottom Background
    const botName = getBaseName(appState.bg_video_bottom_path) || 'None (Disable Split Screen)';
    document.getElementById('bottom-video-name').textContent = botName;
    
    // Music
    const musName = getBaseName(appState.bg_music_path) || 'None';
    document.getElementById('music-name').textContent = musName;
}

// Save active state to backend
async function saveState() {
    try {
        await fetch('/api/state', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(appState)
        });
    } catch (err) {
        console.error('Failed to save session state:', err);
    }
}

// Studio Presets selection grid renderer
function renderStudioPresetsGrid() {
    const grid = document.getElementById('preset-quick-list');
    grid.innerHTML = '';
    
    Object.keys(appPresets).forEach(name => {
        const card = document.createElement('div');
        card.className = 'preset-card-quick';
        if (appState.loaded_preset_name === name) {
            card.classList.add('active');
        }
        card.textContent = name;
        card.addEventListener('click', () => selectPreset(name));
        grid.appendChild(card);
    });
}

// Preset selection execution
async function selectPreset(presetName) {
    const preset = appPresets[presetName];
    if (!preset) return;
    
    // Update local state properties from preset
    appState.loaded_preset_name = presetName;
    appState.selected_voice = preset.selected_voice;
    appState.bg_video_path = preset.bg_video_path;
    appState.bg_video_bottom_path = preset.bg_video_bottom_path;
    appState.bg_music_path = preset.bg_music_path;
    appState.music_volume = preset.music_volume;
    appState.voice_volume = preset.voice_volume;
    appState.sub_font = preset.sub_font;
    appState.sub_size = preset.sub_size;
    appState.sub_color = preset.sub_color;
    appState.sub_highlight = preset.sub_highlight;
    appState.sub_outline = preset.sub_outline;
    appState.sub_outline_width = preset.sub_outline_width;
    appState.sub_bold = preset.sub_bold;
    appState.word_pop = preset.word_pop;
    appState.word_pop_scale = preset.word_pop_scale;
    appState.inactive_dim = preset.inactive_dim;
    appState.inactive_alpha = preset.inactive_alpha;
    appState.enable_emojis = preset.enable_emojis;
    appState.sub_animation_style = preset.sub_animation_style;
    appState.single_word_mode = preset.single_word_mode || false;
    appState.emoji_position = preset.emoji_position || 'above';
    appState.sub_uppercase = preset.sub_uppercase !== undefined ? preset.sub_uppercase : true;
    appState.sub_border_style = preset.sub_border_style || 1;
    
    // Synchronize selector indicators
    document.getElementById('voice-select').value = preset.selected_voice;
    document.getElementById('anim-select').value = preset.sub_animation_style;
    activePresetBadge.textContent = presetName;
    
    // Highlight active preset card
    document.querySelectorAll('.preset-card-quick').forEach(card => {
        if (card.textContent === presetName) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });
    
    updateSelectedAssetsDisplay();
    await saveState();
}

// Generate script via LLM
async function generateScript() {
    const promptInput = document.getElementById('ai-prompt-input');
    const prompt = promptInput.value.trim();
    if (!prompt) {
        alert('Please enter a script topic or instruction.');
        return;
    }
    
    const voiceOverride = document.getElementById('generate-voice-select').value;
    const btn = document.getElementById('btn-generate-script');
    
    // Spinner loading indicator
    btn.disabled = true;
    btn.innerHTML = `<span class="pulse">Generating Script...</span>`;
    
    try {
        const res = await fetch('/api/script/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                selected_voice: voiceOverride || null
            })
        });
        const ans = await res.json();
        
        if (res.ok) {
            document.getElementById('script-text-area').value = ans.script;
            appState.script_text = ans.script;
            if (voiceOverride) {
                appState.selected_voice = voiceOverride;
                document.getElementById('voice-select').value = voiceOverride;
            }
            activePresetBadge.textContent = 'None (Custom)';
            appState.loaded_preset_name = null;
            
            updateWordCount();
            await saveState();
            
            // Log to console
            appendConsoleLog(`[AI Script Generated Successfully]\n"${ans.script}"\n`, 'system');
        } else {
            alert('Generation Failed: ' + ans.detail);
        }
    } catch (err) {
        alert('Failed to connect to API: ' + err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" class="btn-svg"><path d="M19 9 20.25 11.75 23 13 20.25 14.25 19 17 17.75 14.25 15 13 17.75 11.75 19 9M9 4 11.5 9.5 17 12 11.5 14.5 9 20 6.5 14.5 1 12 6.5 9.5 9 4Z" fill="currentColor"/></svg>
            Generate Script`;
    }
}

// Media Manager Assets fetching & rendering
async function refreshAssetsList() {
    const activeTab = document.querySelector('.media-tab-btn.active').dataset.media;
    if (activeTab === 'videos') {
        await renderVideosGrid('main');
    } else if (activeTab === 'music') {
        await renderMusicGrid('main');
    }
}

async function renderVideosGrid(context) {
    const gridId = context === 'main' ? 'videos-grid' : 'modal-asset-grid';
    const grid = document.getElementById(gridId);
    if (!grid) return;
    
    grid.innerHTML = '<div class="empty-state">Loading video library...</div>';
    
    try {
        const res = await fetch('/api/assets/videos');
        const videos = await res.json();
        
        if (videos.length === 0) {
            grid.innerHTML = '<div class="empty-state">No videos found. Upload one or download from Pexels!</div>';
            return;
        }
        
        grid.innerHTML = '';
        
        // Add a virtual "Random Selection" card for selector context
        if (context === 'modal') {
            const randCard = document.createElement('div');
            randCard.className = 'asset-card';
            randCard.innerHTML = `
                <div class="asset-thumbnail-container">
                    <span class="asset-icon-placeholder">🎲</span>
                </div>
                <div class="asset-details">
                    <span class="asset-title">Random Selection</span>
                    <span class="asset-meta">Auto select randomly on compile</span>
                </div>
            `;
            randCard.addEventListener('click', () => {
                selectAssetFromModal('random');
            });
            grid.appendChild(randCard);
        }
        
        videos.forEach(v => {
            const card = document.createElement('div');
            card.className = 'asset-card';
            
            // Build card html content
            let durationStr = v.duration ? `${v.duration.toFixed(1)}s` : '';
            let sizeStr = `${(v.size / (1024 * 1024)).toFixed(1)} MB`;
            
            card.innerHTML = `
                <div class="asset-thumbnail-container">
                    <video class="asset-thumbnail-video" src="${v.url}" muted loop playsinline></video>
                    <span class="pexels-duration-badge">${durationStr || 'Loop'}</span>
                </div>
                <div class="asset-details">
                    <span class="asset-title" title="${v.filename}">${v.filename}</span>
                    <div class="asset-meta">
                        <span>${sizeStr}</span>
                    </div>
                </div>
                <div class="asset-actions-overlay">
                    <button class="action-icon-btn delete-btn" onclick="event.stopPropagation(); deleteAsset('video', '${v.filename}')">
                        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
                    </button>
                </div>
            `;
            
            // Video preview hover logic
            const video = card.querySelector('video');
            card.addEventListener('mouseenter', () => { try { video.play(); } catch(e){} });
            card.addEventListener('mouseleave', () => { try { video.pause(); video.currentTime = 0; } catch(e){} });
            
            if (context === 'modal') {
                card.addEventListener('click', () => {
                    // select video path
                    selectAssetFromModal(`videos/${v.filename}`);
                });
            }
            
            grid.appendChild(card);
        });
    } catch (err) {
        grid.innerHTML = '<div class="empty-state">Failed to load video catalog.</div>';
    }
}

async function renderMusicGrid(context) {
    const gridId = context === 'main' ? 'music-grid' : 'modal-asset-grid';
    const grid = document.getElementById(gridId);
    if (!grid) return;
    
    grid.innerHTML = '<div class="empty-state">Loading music library...</div>';
    
    try {
        const res = await fetch('/api/assets/music');
        const tracks = await res.json();
        
        if (tracks.length === 0) {
            grid.innerHTML = '<div class="empty-state">No music files found. Drag & drop audio tracks to add!</div>';
            return;
        }
        
        grid.innerHTML = '';
        
        // Virtual "None" card for selector context
        if (context === 'modal' && activeSelectorTarget === 'music') {
            const randCard = document.createElement('div');
            randCard.className = 'asset-card';
            randCard.innerHTML = `
                <div class="asset-thumbnail-container">
                    <span class="asset-icon-placeholder">🚫</span>
                </div>
                <div class="asset-details">
                    <span class="asset-title">No background music</span>
                    <span class="asset-meta">Disable music track</span>
                </div>
            `;
            randCard.addEventListener('click', () => {
                selectAssetFromModal(null);
            });
            grid.appendChild(randCard);
        }
        
        tracks.forEach(t => {
            const card = document.createElement('div');
            card.className = 'asset-card';
            
            let sizeStr = `${(t.size / (1024 * 1024)).toFixed(2)} MB`;
            
            card.innerHTML = `
                <div class="asset-thumbnail-container">
                    <span class="asset-icon-placeholder">🎵</span>
                    <audio class="asset-audio-preview" src="${t.url}"></audio>
                </div>
                <div class="asset-details">
                    <span class="asset-title" title="${t.filename}">${t.filename}</span>
                    <div class="asset-meta">
                        <span>${sizeStr}</span>
                    </div>
                </div>
                <div class="asset-actions-overlay">
                    <button class="action-icon-btn play-btn" onclick="event.stopPropagation(); toggleAudioPreview(this)">
                        <svg viewBox="0 0 24 24" fill="none" class="play-svg" xmlns="http://www.w3.org/2000/svg"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>
                    </button>
                    <button class="action-icon-btn delete-btn" onclick="event.stopPropagation(); deleteAsset('music', '${t.filename}')">
                        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
                    </button>
                </div>
            `;
            
            if (context === 'modal') {
                card.addEventListener('click', () => {
                    selectAssetFromModal(`music/${t.filename}`);
                });
            }
            
            grid.appendChild(card);
        });
    } catch (err) {
        grid.innerHTML = '<div class="empty-state">Failed to load audio files.</div>';
    }
}

// Audio preview playing controller
function toggleAudioPreview(btn) {
    const audio = btn.closest('.asset-card').querySelector('audio');
    const playSvg = `<path d="M8 5v14l11-7z" fill="currentColor"/>`;
    const pauseSvg = `<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="currentColor"/>`;
    
    // Stop all other audio previews first
    document.querySelectorAll('.asset-card audio').forEach(aud => {
        if (aud !== audio && !aud.paused) {
            aud.pause();
            aud.currentTime = 0;
            const otherBtn = aud.closest('.asset-card').querySelector('.play-btn');
            if (otherBtn) otherBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" class="play-svg">${playSvg}</svg>`;
        }
    });
    
    if (audio.paused) {
        audio.play();
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" class="play-svg">${pauseSvg}</svg>`;
    } else {
        audio.pause();
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" class="play-svg">${playSvg}</svg>`;
    }
}

// Delete media asset from server
async function deleteAsset(type, filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
    
    try {
        const endpoint = type === 'video' ? `/api/assets/videos/${filename}` : `/api/assets/music/${filename}`;
        const res = await fetch(endpoint, { method: 'DELETE' });
        const ans = await res.json();
        
        if (ans.status === 'success') {
            await refreshAssetsList();
            await fetchState();
        } else {
            alert('Failed to delete asset: ' + ans.detail);
        }
    } catch (err) {
        alert('Network error: ' + err);
    }
}

// Pexels API Searches
async function searchPexels(context) {
    const inputEl = context === 'main' ? document.getElementById('pexels-query-input') : document.getElementById('modal-pexels-query');
    const gridEl = context === 'main' ? document.getElementById('pexels-results-grid') : document.getElementById('modal-asset-grid');
    
    const query = inputEl.value.trim();
    if (!query) {
        // Try auto extracting keyword from script if query empty and modal context
        if (context === 'modal' && appState.script_text) {
            inputEl.value = 'Extracting keyword...';
            try {
                const extRes = await fetch('/api/pexels/extract-keyword', { method: 'POST' });
                const extData = await extRes.json();
                inputEl.value = extData.keyword;
                searchPexels(context);
            } catch (e) {
                inputEl.value = '';
            }
            return;
        }
        alert('Please enter a query to search Pexels.');
        return;
    }
    
    gridEl.innerHTML = '<div class="empty-state">Searching Pexels for vertical videos...</div>';
    
    try {
        const res = await fetch('/api/pexels/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        const data = await res.json();
        
        if (!res.ok) {
            gridEl.innerHTML = `<div class="empty-state text-danger">Error: ${data.detail}</div>`;
            return;
        }
        
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
    }
}

// Download Pexels video
async function downloadPexelsVideo(url, id, query, positionOverride) {
    const position = positionOverride || activeSelectorTarget || 'top';
    const payload = {
        download_url: url,
        video_id: id,
        keyword: query,
        position: position
    };
    
    // Close modal if context
    if (!positionOverride) {
        closeAssetSelector();
    }
    
    // Print to logs
    appendConsoleLog(`[Pexels Download Started] Triggered download for ${position} video (${id}). Please wait...`, 'system');
    
    try {
        const res = await fetch('/api/pexels/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const ans = await res.json();
        if (res.ok) {
            appendConsoleLog(`[Pexels Download Triggered] File: ${ans.filename}`, 'system');
            // Poll state until downloaded
            let checkCount = 0;
            const stateKey = position === 'top' ? 'bg_video_path' : 'bg_video_bottom_path';
            
            const checkInterval = setInterval(async () => {
                await fetchState();
                checkCount++;
                if (appState[stateKey] && appState[stateKey].includes(ans.filename)) {
                    clearInterval(checkInterval);
                    appendConsoleLog(`[Pexels Download Complete] Loaded background video: ${ans.filename}`, 'system');
                    updateSelectedAssetsDisplay();
                }
                if (checkCount > 60) { // 1 min timeout
                    clearInterval(checkInterval);
                }
            }, 1500);
        } else {
            alert('Failed: ' + ans.detail);
        }
    } catch (err) {
        alert('Download connection failed: ' + err);
    }
}

// Visual Modal Operations for Asset Selectors
function openAssetSelector(target) {
    activeSelectorTarget = target;
    const modal = document.getElementById('asset-selector-modal');
    const title = document.getElementById('modal-select-title');
    const pexelsBar = document.getElementById('modal-pexels-search-bar');
    
    title.textContent = `Select Background ${target === 'music' ? 'Audio Track' : 'Video'}`;
    
    // Show Pexels search query bar inside modal if picking background video
    if (target === 'top' || target === 'bottom') {
        pexelsBar.classList.remove('hidden');
        document.getElementById('modal-pexels-query').value = '';
    } else {
        pexelsBar.classList.add('hidden');
    }
    
    // Refresh modal grid items
    if (target === 'music') {
        renderMusicGrid('modal');
    } else {
        renderVideosGrid('modal');
    }
    
    modal.style.display = 'flex';
}

function closeAssetSelector() {
    document.getElementById('asset-selector-modal').style.display = 'none';
}

async function selectAssetFromModal(value) {
    if (activeSelectorTarget === 'top') {
        appState.bg_video_path = value;
    } else if (activeSelectorTarget === 'bottom') {
        appState.bg_video_bottom_path = value;
    } else if (activeSelectorTarget === 'music') {
        appState.bg_music_path = value;
    }
    
    appState.loaded_preset_name = null;
    activePresetBadge.textContent = 'None (Custom)';
    
    await saveState();
    updateSelectedAssetsDisplay();
    closeAssetSelector();
}

// Drag & drop file uploads
function setupDropzones() {
    const dropzones = [
        { zoneId: 'video-dropzone', inputId: 'video-file-input', type: 'video' },
        { zoneId: 'music-dropzone', inputId: 'music-file-input', type: 'music' },
        { zoneId: 'modal-upload-zone', inputId: 'modal-file-input', type: 'auto' }
    ];
    
    dropzones.forEach(pair => {
        const zone = document.getElementById(pair.zoneId);
        const input = document.getElementById(pair.inputId);
        if (!zone || !input) return;
        
        zone.addEventListener('click', () => input.click());
        
        input.addEventListener('change', () => {
            if (input.files.length > 0) {
                uploadFile(input.files[0], pair.type);
            }
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
            if (e.dataTransfer.files.length > 0) {
                uploadFile(e.dataTransfer.files[0], pair.type);
            }
        });
    });
}

async function uploadFile(file, typeContext) {
    const type = typeContext === 'auto' ? (activeSelectorTarget === 'music' ? 'music' : 'video') : typeContext;
    const endpoint = type === 'video' ? '/api/assets/videos' : '/api/assets/music';
    
    const formData = new FormData();
    formData.append('file', file);
    
    appendConsoleLog(`[Upload Started] Sending "${file.name}" to server...`, 'system');
    
    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });
        const ans = await res.json();
        
        if (res.ok) {
            appendConsoleLog(`[Upload Success] File saved: ${ans.filename}`, 'system');
            // Refresh lists
            await refreshAssetsList();
            
            // If inside selector modal, auto-select it
            const isModalOpen = document.getElementById('asset-selector-modal').style.display === 'flex';
            if (isModalOpen) {
                const pathVal = type === 'video' ? `videos/${ans.filename}` : `music/${ans.filename}`;
                selectAssetFromModal(pathVal);
            }
        } else {
            alert('Upload failed: ' + ans.detail);
        }
    } catch (err) {
        alert('Network upload error: ' + err);
    }
}

// Preset manager page rendering & creation
function renderPresetsList() {
    const container = document.getElementById('presets-list-grid');
    if (!container) return;
    
    container.innerHTML = '';
    
    Object.keys(appPresets).forEach(name => {
        const p = appPresets[name];
        const item = document.createElement('div');
        item.className = 'preset-item';
        
        item.innerHTML = `
            <div class="preset-item-info">
                <h4>${name}</h4>
                <p>Voice: ${p.selected_voice} | Animation: ${p.sub_animation_style} | Font: ${p.sub_font} (${p.sub_size}px, ${p.sub_color})</p>
            </div>
            <div class="preset-item-actions">
                <button class="btn btn-sm btn-secondary" onclick="loadPresetIntoDesigner('${name}')">Edit</button>
                <button class="btn btn-sm btn-outline-danger" onclick="deletePreset('${name}')">Delete</button>
            </div>
        `;
        container.appendChild(item);
    });
}

function loadPresetIntoDesigner(name) {
    const p = appPresets[name];
    if (!p) return;
    
    document.getElementById('preset-name-input').value = name;
    document.getElementById('preset-font-select').value = p.sub_font || 'Arial';
    document.getElementById('preset-font-size').value = p.sub_size || 72;
    document.getElementById('preset-bold').value = (p.sub_bold !== false).toString();
    document.getElementById('preset-case').value = (p.sub_uppercase !== false).toString();
    
    const primary = p.sub_color || '#FFFFFF';
    document.getElementById('preset-color-primary').value = primary;
    document.getElementById('preset-color-primary-text').value = primary;
    
    const highlight = p.sub_highlight || '#00FFFF';
    document.getElementById('preset-color-highlight').value = highlight;
    document.getElementById('preset-color-highlight-text').value = highlight;
    
    const outline = p.sub_outline || '#000000';
    document.getElementById('preset-color-outline').value = outline;
    document.getElementById('preset-color-outline-text').value = outline;
    
    document.getElementById('preset-outline-width').value = p.sub_outline_width !== undefined ? p.sub_outline_width : 5;
    
    document.getElementById('preset-word-pop').value = (p.word_pop !== false).toString();
    document.getElementById('preset-inactive-dim').value = (p.inactive_dim !== false).toString();
    document.getElementById('preset-anim-style').value = p.sub_animation_style || 'tiktok_pop';
    
    const emojiPos = p.emoji_position || (p.enable_emojis === false ? 'none' : 'above');
    document.getElementById('preset-emoji-pos').value = emojiPos;
    
    document.getElementById('preset-voice-select').value = p.selected_voice || 'af_sarah';
    document.getElementById('preset-voice-speed').value = p.voice_speed || 1.0;
}

async function saveCustomPresetToServer() {
    const name = document.getElementById('preset-name-input').value.trim();
    if (!name) {
        alert('Please enter a name for the Preset template.');
        return;
    }
    
    const emojiPos = document.getElementById('preset-emoji-pos').value;
    
    const payload = {
        name: name,
        selected_voice: document.getElementById('preset-voice-select').value,
        voice_speed: parseFloat(document.getElementById('preset-voice-speed').value) || 1.0,
        voice_volume: 1.2,
        music_volume: 0.15,
        sub_font: document.getElementById('preset-font-select').value,
        sub_size: parseInt(document.getElementById('preset-font-size').value) || 72,
        sub_color: document.getElementById('preset-color-primary-text').value,
        sub_highlight: document.getElementById('preset-color-highlight-text').value,
        sub_outline: document.getElementById('preset-color-outline-text').value,
        sub_outline_width: parseInt(document.getElementById('preset-outline-width').value) || 5,
        sub_bold: document.getElementById('preset-bold').value === 'true',
        sub_uppercase: document.getElementById('preset-case').value === 'true',
        word_pop: document.getElementById('preset-word-pop').value === 'true',
        word_pop_scale: 1.15,
        inactive_dim: document.getElementById('preset-inactive-dim').value === 'true',
        inactive_alpha: '88',
        enable_emojis: emojiPos !== 'none',
        emoji_position: emojiPos !== 'none' ? emojiPos : 'none',
        sub_animation_style: document.getElementById('preset-anim-style').value
    };
    
    try {
        const res = await fetch('/api/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const ans = await res.json();
        
        if (res.ok) {
            alert('Custom preset template saved!');
            await fetchPresets();
        } else {
            alert('Save failed: ' + ans.detail);
        }
    } catch (err) {
        alert('Preset save failed: ' + err);
    }
}

async function deletePreset(name) {
    if (!confirm(`Are you sure you want to delete the preset template "${name}"?`)) return;
    
    try {
        const res = await fetch(`/api/presets/${encodeURIComponent(name)}`, { method: 'DELETE' });
        const ans = await res.json();
        
        if (res.ok) {
            await fetchPresets();
        } else {
            alert('Failed: ' + ans.detail);
        }
    } catch (err) {
        alert('Preset delete failed: ' + err);
    }
}

// Rendered library videos viewer
async function refreshGallery() {
    const grid = document.getElementById('gallery-grid');
    if (!grid) return;
    
    grid.innerHTML = '<div class="empty-state">Loading compiled video library...</div>';
    
    try {
        const res = await fetch('/api/gallery');
        const videos = await res.json();
        
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
    }
}

async function deleteGalleryShort(filename) {
    if (!confirm(`Are you sure you want to delete this completed video: "${filename}"?`)) return;
    
    try {
        const res = await fetch(`/api/gallery/${filename}`, { method: 'DELETE' });
        const ans = await res.json();
        if (res.ok) {
            await refreshGallery();
        } else {
            alert('Failed to delete video: ' + ans.detail);
        }
    } catch (err) {
        alert('Delete failed: ' + err);
    }
}

// Real-time Compilation Flow
async function compileVideo() {
    // Save current editor state first
    appState.script_text = document.getElementById('script-text-area').value;
    await saveState();
    
    const customFilename = document.getElementById('output-filename-input').value;
    
    const formData = new FormData();
    if (customFilename) {
        formData.append('custom_filename', customFilename);
    }
    
    // Toggle layout to loading compilation banner
    const banner = document.getElementById('compile-status-container');
    const progressBar = document.getElementById('compile-progress-bar');
    const btn = document.getElementById('btn-compile-video');
    
    banner.classList.remove('hidden');
    progressBar.style.width = '10%';
    btn.disabled = true;
    
    appendConsoleLog('\n[System Log] Triggering compilation thread on backend...', 'system');
    
    try {
        const res = await fetch('/api/compile', {
            method: 'POST',
            body: formData
        });
        const ans = await res.json();
        
        if (res.ok) {
            appendConsoleLog('[System Log] Background compilation worker spawned successfully.', 'system');
            
            // Poll for completion
            startCompilationPolling();
        } else {
            alert('Compilation failed to start: ' + ans.detail);
            btn.disabled = false;
            banner.classList.add('hidden');
        }
    } catch (err) {
        alert('Compile trigger connection failure: ' + err);
        btn.disabled = false;
        banner.classList.add('hidden');
    }
}

async function cancelCompilation() {
    try {
        const res = await fetch('/api/compile/cancel', { method: 'POST' });
        const ans = await res.json();
        appendConsoleLog(`[System Log] Cancel request sent: ${ans.message}`, 'system');
    } catch(e){}
}

function startCompilationPolling() {
    if (compilationPollInterval) clearInterval(compilationPollInterval);
    
    const progressBar = document.getElementById('compile-progress-bar');
    const consoleBody = document.getElementById('compiler-console');
    let lastLogLength = 0;
    
    compilationPollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/compile/status');
            const data = await res.json();
            
            // Append new log increments
            if (data.logs && data.logs.length > lastLogLength) {
                const newChunk = data.logs.substring(lastLogLength);
                lastLogLength = data.logs.length;
                
                appendConsoleLog(newChunk);
            }
            
            // Guess progress from log contents for user delight
            const logsText = data.logs || '';
            let progress = 10;
            if (logsText.includes('[1/4]') || logsText.includes('Generated sentence')) progress = 25;
            if (logsText.includes('Generating & transcribing sentence')) {
                // approximate sentence index
                const matches = logsText.match(/sentence (\d+)\/(\d+)/g);
                if (matches && matches.length > 0) {
                    const lastMatch = matches[matches.length - 1];
                    const numMatch = lastMatch.match(/sentence (\d+)\/(\d+)/);
                    if (numMatch) {
                        const current = parseInt(numMatch[1]);
                        const total = parseInt(numMatch[2]);
                        progress = 25 + Math.floor((current / total) * 20);
                    }
                }
            }
            if (logsText.includes('[3/4]') || logsText.includes('ASS subtitles generated')) progress = 55;
            if (logsText.includes('[4/4]') || logsText.includes('Rendering vertical video')) progress = 70;
            if (logsText.includes('frame=')) {
                // parsing frame rendering from ffmpeg
                progress = 85;
            }
            if (logsText.includes('RENDER SUCCESSFUL')) progress = 100;
            
            progressBar.style.width = `${progress}%`;
            
            if (!data.in_progress) {
                clearInterval(compilationPollInterval);
                compilationPollInterval = null;
                
                document.getElementById('btn-compile-video').disabled = false;
                document.getElementById('compile-status-container').classList.add('hidden');
                
                if (data.success) {
                    progressBar.style.width = '100%';
                    appendConsoleLog('\n[System Log] Video short generated successfully! Reloading video gallery...', 'system');
                    await refreshGallery();
                    // Play success notification if needed
                    alert('Short compilation successful!');
                } else {
                    appendConsoleLog('\n[System Log] Video short generation failed. Check errors above.', 'system');
                    alert('Compilation failed. Check logs in the Console panel.');
                }
            }
        } catch (err) {
            console.error('Error polling compiler status:', err);
        }
    }, 1000);
}

// Background checker for active compilers on load
async function checkActiveCompilation() {
    try {
        const res = await fetch('/api/compile/status');
        const data = await res.json();
        
        if (data.in_progress) {
            document.getElementById('compile-status-container').classList.remove('hidden');
            document.getElementById('btn-compile-video').disabled = true;
            startCompilationPolling();
        }
    } catch(e){}
}

// Terminal logs appending with basic ANSI color formatting support
function appendConsoleLog(text, className = '') {
    const consoleBody = document.getElementById('compiler-console');
    if (!consoleBody) return;
    
    // Parse ANSI escape codes to styled HTML
    const formatted = parseAnsiColors(text);
    
    if (className === 'system') {
        const line = document.createElement('div');
        line.className = 'terminal-line system-line';
        line.innerHTML = formatted;
        consoleBody.appendChild(line);
    } else {
        // Append raw logs which might contain linebreaks
        const span = document.createElement('span');
        span.innerHTML = formatted;
        consoleBody.appendChild(span);
    }
    
    // Scroll console terminal to bottom
    consoleBody.scrollTop = consoleBody.scrollHeight;
}

// Simple ANSI color sequences converter
function parseAnsiColors(text) {
    if (!text) return '';
    
    // Escape standard HTML tags
    let clean = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
        
    // Convert ANSI color escape codes
    const ansiMap = {
        '\\x1b\\[31m': 'color: #ff5f56; font-weight: bold;', // Red
        '\\x1b\\[32m': 'color: #27c93f; font-weight: bold;', // Green
        '\\x1b\\[33m': 'color: #ffbd2e; font-weight: bold;', // Yellow
        '\\x1b\\[34m': 'color: #54a3ff; font-weight: bold;', // Blue
        '\\x1b\\[35m': 'color: #ff007f; font-weight: bold;', // Magenta (Pink)
        '\\x1b\\[36m': 'color: #00f2fe; font-weight: bold;', // Cyan
        '\\x1b\\[1m': 'font-weight: bold;',
        '\\x1b\\[0m': 'reset'
    };
    
    // Also cover raw control codes if they come as raw characters (\u001b or \x1b)
    const rawAnsiMap = [
        { regex: /\u001b\[31m/g, style: 'color: #ff5f56; font-weight: bold;' },
        { regex: /\u001b\[32m/g, style: 'color: #27c93f; font-weight: bold;' },
        { regex: /\u001b\[33m/g, style: 'color: #ffbd2e; font-weight: bold;' },
        { regex: /\u001b\[34m/g, style: 'color: #54a3ff; font-weight: bold;' },
        { regex: /\u001b\[35m/g, style: 'color: #ff007f; font-weight: bold;' },
        { regex: /\u001b\[36m/g, style: 'color: #00f2fe; font-weight: bold;' },
        { regex: /\u001b\[1m/g, style: 'font-weight: bold;' },
        { regex: /\u001b\[0m/g, style: 'reset' },
        
        { regex: /\[31m/g, style: 'color: #ff5f56; font-weight: bold;' },
        { regex: /\[32m/g, style: 'color: #27c93f; font-weight: bold;' },
        { regex: /\[33m/g, style: 'color: #ffbd2e; font-weight: bold;' },
        { regex: /\[34m/g, style: 'color: #54a3ff; font-weight: bold;' },
        { regex: /\[35m/g, style: 'color: #ff007f; font-weight: bold;' },
        { regex: /\[36m/g, style: 'color: #00f2fe; font-weight: bold;' },
        { regex: /\[1m/g, style: 'font-weight: bold;' },
        { regex: /\[0m/g, style: 'reset' }
    ];
    
    let html = clean;
    
    // Basic parser for ANSI colors using a stack of span openings
    let openSpansCount = 0;
    
    // We parse character by character or chunk by chunk
    // Let's replace raw escape sequences
    rawAnsiMap.forEach(item => {
        html = html.replace(item.regex, (match) => {
            if (item.style === 'reset') {
                let res = '';
                while (openSpansCount > 0) {
                    res += '</span>';
                    openSpansCount--;
                }
                return res;
            } else {
                openSpansCount++;
                return `<span style="${item.style}">`;
            }
        });
    });
    
    // Close any left-open spans
    while (openSpansCount > 0) {
        html += '</span>';
        openSpansCount--;
    }
    
    return html;
}
