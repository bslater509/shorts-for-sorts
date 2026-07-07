# Project Rules

## Architectural & Code Conventions
- Strictly separate Python backend logic (`gui/`) from the React frontend (`gui/frontend`).
- Enforce specific coding paradigms (e.g., use Functional Components in React, specific patterns in Python).
- Focus on high UI/UX standards (e.g., enforcing Tailwind usage and specific design aesthetics).

## Tooling & Development Workflow
- During development, `npm run dev` in `gui/frontend` and the Python server should be run in separate terminals.
- To run the Web GUI app conveniently, use the `./run-gui.sh` (or `run-gui.bat` on Windows) script from the root folder to start everything.
- For production, the frontend is built into `gui/static` and served directly by the Python backend.

## Agent-Specific Guidelines
- Agents must ALWAYS build and verify the frontend before committing changes to `gui/frontend`.
- Agents should not modify the generated output directories (`output/`, `videos/`, `gui/static/`).
- Agents must leave explicit comments explaining the rationale behind UI/UX or Architectural changes.

# Project Context: Shorts for Sorts

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, uvicorn, kokoro-onnx (TTS), faster-whisper (transcription), ffmpeg-python, openai (LLM scripts), yt-dlp, sentry-sdk, psutil, nltk, soundfile, playwright (TikTok upload)
- **Frontend**: React 19, Vite 8, shadcn/ui, Tailwind CSS 3, Zustand 5, react-router-dom 7, Recharts, Lucide icons, Radix UI, clsx, tailwind-merge
- **Lint**: oxlint (NOT ESLint) — config at `gui/frontend/.oxlintrc.json`

## Commands
```bash
# Run the full app
./run-gui.sh                      # Linux
run-gui.bat                       # Windows

# Frontend
cd gui/frontend && npm run dev    # Dev server with HMR
cd gui/frontend && npm run build  # Production build → gui/frontend/dist/
cd gui/frontend && npm run lint   # oxlint

# Backend
python gui/server.py              # Runs on port 5000

# Python env setup
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

## Architecture

### Directory Layout
```
shorts-for-sorts/
├── generator.py              # Core: TTS, ASS subtitles, FFmpeg compilation
├── requirements.txt          # Python dependencies
├── run-gui.sh / run-gui.bat  # Startup scripts
├── config/                   # settings.json, presets.json, prompts.json, emojis.json
├── gui/
│   ├── server.py             # FastAPI web server (20+ endpoints, WebSocket)
│   ├── compiler.py           # Compilation orchestration (single video)
│   ├── batch.py              # Parallel batch generation
│   ├── config.py             # Paths, logging, settings/presets/emoji persistence
│   ├── state.py              # Shared state schema, TTS voice list
│   ├── utils.py              # LLM profiles, Pexels downloads, system deps check
│   ├── tiktok_uploader.py    # Playwright-based TikTok upload
│   └── frontend/             # React SPA (Vite + shadcn/ui)
│       └── src/
│           ├── pages/        # Studio, MediaManager, Presets, Gallery, SettingsPage, Batch
│           ├── components/   # layout/, studio/, ui/ (shadcn)
│           ├── lib/          # api.js (all API calls), utils.js (cn helper)
│           └── store/        # useAppStore.js (Zustand)
├── models/                   # Kokoro ONNX model, voices.json
├── videos/                   # Background video assets
├── music/                    # Background music assets
├── output/                   # Rendered videos
├── cache/                    # Generated audio/subtitle cache
├── temp/                     # Temporary render files
└── logs/                     # server.json.log (rotating, 5MB, 3 backups)
```

### Video Compilation Pipeline
1. **Script splitting** — Split by blank-line paragraphs (or ~50-word groups as fallback using NLTK)
2. **Parallel TTS** — Kokoro ONNX voice generation (up to 3 concurrent threads), then unload model
3. **Transcription** — faster-whisper (CPU int8) with OpenAI Whisper API fallback
4. **ASS Subtitle generation** — Per-word timing, 9 animation styles, emoji insertion
5. **FFmpeg render** — Crop to 9:16 or stacked split-screen (9:8+9:8), subtitle burn, voice+music mix, fade in/out

### Subtitle Animation Styles
`tiktok_pop`, `karaoke_sweep`, `bouncy_bounce`, `cinematic_zoom`, `glow_shake`, `neon_flicker`, `pulse_grow`, `fade_in_slide`, `typewriter_swipe`

### Voices
8 voices: Bella/Sarah (US female), Adam/Michael (US male), Emma/Isabella (UK female), George/Lewis (UK male). Prefix: `af_`, `am_`, `bf_`, `bm_`. Default: `af_bella`.

### Built-in Presets
Split-Screen Chill, Lofi Storyteller, Fast-Paced Promo, TikTok Kinetic Pop, Retro Synthwave, Cinematic Documentary, Cyberpunk Red, Classic Serif Storyteller

## Patterns & Conventions

### Thread Safety
- `_TTS_LOCK` — reentrant RLock for TTS model (prevents deadlock)
- `_compile_log_lock` — compilation logs list
- `_compile_thread_lock` — compilation thread spawn
- `_state_file_lock` — GUI state file writes
- `_batch_lock` — batch TOCTOU guard

### Batch Processing
- Uses `multiprocessing.get_context('spawn')` for ProcessPoolExecutor
- Workers suppress stdout/stderr to /dev/null, disable atexit cache cleanup
- Each worker has isolated state/settings copies
- Auto-cancels entire batch on any job failure

### Settings
- Stored in `config/settings.json`, template at `config/settings.json.template`
- Auto-migration from legacy flat keys (`api_key`/`base_url`/`model`) to `llm_profiles` array
- Sentry DSN auto-initialized if set in settings (10% trace sample rate in frontend)

### Security
- Path traversal protection on all file-serving endpoints (`/videos/`, `/music/`, `/output/`)
- SSRF protection: YouTube URL scheme validated to http/https only
- File upload filenames sanitized to alphanumeric + `.`, `_`, `-`
- Port 5000 cleanup kills only known server processes, not unrelated services

### Git History
- 17 commits, single `main` branch
- Conventional commits (`feat:`, `refactor:`, `fix:`)
- Primary contributor: bslater509 (8 commits)
- Evolution: CLI → Textual TUI → unified CLI → FastAPI GUI

### Known Gotchas
- TTS model (Kokoro) must be unloaded before spawning batch workers (GPU memory)
- Whisper model cached module-level, reloaded only on model name change
- Cache cleared on startup by prefix-based matching
- Empty script falls back to silence audio (1 second of zeros)
- NLTK punkt_tab auto-downloaded if missing (for sentence splitting)
