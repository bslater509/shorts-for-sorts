# Project Rules

## Architectural & Code Conventions
- Strictly separate Python backend logic (`gui/`) from the React frontend (`gui/frontend`).
- The `generator/` package is a pure-media-library dependency of `gui/` — it has no FastAPI dependency and can be tested independently.
- Use Functional Components in React; Python backend code is module-level functions with docstrings.
- Focus on high UI/UX standards (enforcing Tailwind usage and specific design aesthetics).

## Tooling & Development Workflow
- During development, `npm run dev` in `gui/frontend` and the Python server should be run in separate terminals.
- To run the Web GUI app conveniently, use the `./run-gui.sh` script from the root folder to start everything.
- For production, the frontend is built into `gui/frontend/dist/` and served by the Python backend.

## Agent-Specific Guidelines
- Agents must ALWAYS build and verify the frontend before committing changes to `gui/frontend`. If ANY changes are made to the frontend (`gui/frontend`), you MUST rebuild the production bundle by running `cd gui/frontend && npm run build`. The Python backend serves these compiled static files, so changes will not take effect without a rebuild.
- Agents should not modify the generated output directories (`output/`, `videos/`, `music/`, `cache/`, `temp/`).
- Agents must leave explicit comments explaining the rationale behind UI/UX or Architectural changes.

# Project Context: Shorts for Sorts

## Tech Stack
- **Backend**: Python 3.10+, FastAPI, uvicorn, kokoro-onnx (on-device TTS, 20+ voices), faster-whisper (local transcription), openai (LLM script generation), ffmpeg-python (video composition), yt-dlp (YouTube downloads), sentry-sdk (error tracking), psutil (system stats), nltk (sentence splitting), soundfile (audio I/O), Pillow (thumbnail), rich (CLI logging), questionary (CLI prompts)
- **Frontend**: React 19, Vite 8, shadcn/ui, Tailwind CSS 3, Zustand 5, react-router-dom 7, Recharts, Lucide icons, Radix UI, clsx, tailwind-merge, next-themes (dark/light mode)
- **Lint**: oxlint (NOT ESLint) — config at `gui/frontend/.oxlintrc.json`; Python lint uses Ruff

## Commands
```bash
# Run the full app
./run-gui.sh                      # Linux only (auto-setup venv + build frontend + HTTPS)

# Frontend (separate terminal for dev)
cd gui/frontend && npm run dev    # Vite dev server on :5173 (proxies API to :5000)
cd gui/frontend && npm run build  # Production build → gui/frontend/dist/
cd gui/frontend && npm run lint   # oxlint

# Backend (run in another terminal, or use run-gui.sh)
python gui/server.py              # Runs on port 5000 (HTTP)
python gui/server.py --https      # Runs on port 5000 (HTTPS with cert.pem)

# Python env setup
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Tests
python -m pytest tests/ -x -q
```

## Architecture

### High-Level Structure

```
shorts-for-sorts/
├── generator/                  # Core media-generation library (no FastAPI dep)
│   ├── __init__.py             # Public API: generate_voice, compile_video, etc.
│   ├── tts.py                  # Kokoro ONNX text-to-speech (download-on-first-use, thread-local)
│   ├── subtitles.py            # ASS subtitle generator (9 animation styles, emojis, word-timing)
│   ├── video.py                # FFmpeg composition (crop 9:16 / split-screen, burn subs, mix audio)
│   └── utils.py                # Memory release, file download, time formatting
├── gui/                        # FastAPI web application
│   ├── server.py               # App creation, WebSocket endpoints, static serving, SPA catch-all
│   ├── routers/                # REST API route modules
│   │   ├── batch.py            # Batch generation CRUD (start, status, cancel, retry, report)
│   │   ├── settings.py         # Settings, presets, session state
│   │   ├── assets.py           # Video/music upload, list, delete
│   │   ├── integrations.py     # Pexels search/download, YouTube search/download, TikTok upload
│   │   └── admin.py            # Health check, server restart
│   ├── batch_engine.py         # Batch orchestrator: job config builder, pipeline loop, ETA prediction
│   ├── video_compiler.py       # Single-video compilation pipeline (TTS→Transcribe→Subs→Render)
│   ├── llm_utils.py            # LLM retry helpers
│   ├── assets_utils.py         # Video/music file listing helpers
│   ├── config.py               # Paths, logging (JSON rotating + rich console), module re-exports
│   ├── state.py                # Shared session state dict + settings dict + voice definitions
│   ├── ws_manager.py           # WebSocket connection manager + cross-thread notify_clients()
│   ├── models.py               # Pydantic request/response models
│   ├── utils.py                # LLM profile resolution, system deps check
│   ├── tiktok_uploader.py      # Playwright-based TikTok upload
│   ├── media.py                # Range-request media streaming
│   ├── prompts.py              # Default prompt templates
│   ├── emoji_map.py            # Emoji keyword→unicode map
│   ├── builtin_presets.py      # 8 built-in video presets
│   └── frontend/               # React SPA (Vite + shadcn/ui)
│       └── src/
│           ├── pages/          # Batch, MediaManager, Presets, Gallery, SettingsPage, Analytics
│           ├── components/     # layout/, batch/, presets/, settings/, media/, gallery/, analytics/, ui/ (shadcn)
│           ├── lib/            # api.js (all API calls + WebSocket hooks), utils.js (cn helper)
│           ├── hooks/          # useNotifications (WebSocket), useInView
│           └── store/          # useAppStore.js (Zustand: settings, presets, batch state, theme)
├── config/                     # Runtime JSON config files
│   ├── settings.json           # User settings (auto-generated, gitignored)
│   ├── prompts.json            # Prompt templates for batch LLM generation
│   ├── presets.json            # Saved video presets
│   ├── emojis.json             # Emoji map (keyword → unicode)
│   ├── batch_stats.json        # Learned phase weights + per-job stats for ETA prediction
│   ├── batch_profiles.json     # Saved batch config profiles
│   ├── failed_batch_configs.json # Persisted failed jobs (survives restarts)
│   └── gui_state.json          # UI state persistence
├── models/                     # Downloaded Kokoro ONNX model + voices.json
├── fonts/                      # Custom fonts for subtitle ASS rendering
├── videos/                     # Background video assets (user-uploaded / Pexels / YouTube)
├── music/                      # Background music assets
├── output/                     # Rendered videos + thumbnails/ + metadata .txt files
├── cache/                      # Temp TTS chunks, concatenated audio, ASS subtitles
├── temp/                       # FFmpeg temp output before move to output/
├── logs/                       # server.json.log (rotating, 5MB, 3 backups) + app.log
├── tests/                      # pytest test suite
│   ├── test_batch.py, test_emoji.py, test_llm_utils.py, test_models.py,
│   │   test_progress_utils.py, test_routers.py, test_subtitles.py, test_ws_manager.py
├── docs/screenshots/           # README screenshots
├── voices.json                 # External voice definition file
└── videos_to_download.json     # Track pending YouTube/Pexels downloads
```

### Request Flow

**Single-video compile** (`gui/video_compiler.py:compile_video_flow`):
1. **Phase 0** — Split script into TTS chunks (blank-line paragraphs → NLTK sentence grouping fallback)
2. **Phase 1** — Parallel Kokoro TTS via ThreadPoolExecutor (worker count = `settings.max_workers`)
3. **Phase 1b** — Concatenate audio arrays via numpy
4. **Phase 2** — Transcribe via faster-whisper (local) or OpenAI Whisper API, with cascade fallback
5. **Phase 3** — Generate ASS subtitle file with word-level karaoke timing + emoji insertion
6. **Phase 4** — FFmpeg render: crop background(s) to 9:16 (or split-screen 9:8×2 vstack), loop, burn subs, mix voice+music, fade in/out

**Batch mode** (`gui/batch_engine.py`):
1. `POST /api/batch/start` → `_build_job_configs()` creates N randomized configs with shuffled prompts, random voices, random subtitle styles
2. `batch_worker_thread` runs a two-phase pipeline:
   - **LLM phase**: ThreadPoolExecutor (all N scripts generated concurrently via OpenAI-compatible API)
   - **Video phase**: as each LLM future completes, its config is submitted to a ProcessPoolExecutor (`spawn` context, `max_tasks_per_child=1`)
3. Progress pushed over WebSocket in 4 segments: LLM(0–20%) → Voice(20–45%) → Transcribe(45–55%) → Render(55–100%)
4. ETA uses similarity-weighted prediction against historical per-job stats (word count, chunk count, voice)
5. Results persisted to `batch_stats.json` (phase weights + per-job feature/duration records)

### WebSocket Endpoints
| Path | Description |
|---|---|
| `/api/notifications` | Real-time batch progress & failure events (broadcast via `ws_manager.notify_clients()`) |
| `/api/system_stats` | CPU + memory usage streamed every 1s |

### Subtitle Animation Styles
`tiktok_pop`, `karaoke_sweep`, `bouncy_bounce`, `cinematic_zoom`, `glow_shake`, `neon_flicker`, `pulse_grow`, `fade_in_slide`, `typewriter_swipe`

### Voices
8 primary voices (GUI dropdown): Bella/Sarah (US female), Adam/Michael (US male), Emma/Isabella (UK female), George/Lewis (UK male). Prefixes: `af_`, `am_`, `bf_`, `bm_`. Default: `af_bella`. 20+ additional Kokoro voices recognized in presets.

### Built-in Presets
Split-Screen Chill, Lofi Storyteller, Fast-Paced Promo, TikTok Kinetic Pop, Retro Synthwave, Cinematic Documentary, Cyberpunk Red, Classic Serif Storyteller

## Patterns & Conventions

### State Management
- **No database**. All state is module-level Python dicts (`gui/state.py:state` and `gui/state.py:settings`) or JSON files in `config/`.
- `state` = active (single-video) session; `settings` = persistent config loaded from `config/settings.json`.
- Every module that needs state imports `gui.state` directly and mutates the dicts.

### Thread/Process Safety
- `_TTS_LOCK` — reentrant RLock for Kokoro TTS model access
- `_batch_lock` — TOCTOU guard for `batch_state["in_progress"]`
- `_batch_state_lock` — RLock guarding all other batch_state read/write
- Batch video workers run in **ProcessPoolExecutor** (`spawn` context, `max_tasks_per_child=1`), not threads — because Kokoro/Whisper load heavy native model state
- LLM workers run in **ThreadPoolExecutor** (I/O-bound HTTP calls)
- `notify_clients()` uses `asyncio.run_coroutine_threadsafe()` for cross-thread WebSocket broadcasts

### Batch Processing Details
- Failure mode configurable: `"stop_all"` (default) or `"continue"` (Settings → AI Script Generation)
- Workers suppress stdout/stderr, disable atexit cache cleanup
- Each worker has isolated state/settings copies (passed explicitly, not imported)
- Failed jobs persist to disk (`failed_batch_configs.json`) for cross-restart retry
- ETA prediction: similarity-weighted average over historical jobs (normalised Euclidean distance on word_count + chunk_count, same-voice bonus ×1.5, blend to global average when <3 candidates)

### Settings
- Stored in `config/settings.json`, template at `config/settings.json.template`
- Auto-migration from legacy flat keys (`api_key`/`base_url`/`model`) to `llm_profiles` array
- Free Zen LLM models auto-populated on startup (DeepSeek V4 Flash, MiMo-V2.5, etc.)
- Sentry DSN auto-initialized if set in settings (10% trace sample rate in frontend)

### Security
- Path traversal protection on all file-serving endpoints (`/videos/`, `/music/`, `/output/`)
- SSRF protection: YouTube URL scheme validated to http/https only
- File upload filenames sanitized to alphanumeric + `.`, `_`, `-`
- Port 5000 startup cleanup kills only Python/uvicorn/gunicorn/hypercorn processes, not unrelated services

### Git History
- ~40+ commits, single `main` branch
- Conventional commits (`feat:`, `refactor:`, `fix:`)
- Primary contributor: bslater509
- Evolution: CLI → Textual TUI → FastAPI GUI (with multiple refactors of the batch engine, video compiler, and subtitle system)

### Verification
- After editing backend Python code, run: `python -m pytest tests/ -x -q`
- After editing frontend React code, run: `cd gui/frontend && npm run lint` AND ALWAYS run `cd gui/frontend && npm run build` to update the compiled static files served by the backend.

### Known Gotchas
- TTS model (Kokoro) must be unloaded before spawning batch workers to free GPU/native memory
- Whisper model cached module-level in `video_compiler._WHISPER_MODEL`; reloaded only on model name change
- Cache cleared on startup by prefix-based matching (`cached_audio_`, `audio_`, `subs_`, etc.)
- Empty script throws `RuntimeError("Script is empty")` — not silently handled
- NLTK `punkt_tab` auto-downloaded if missing (for sentence splitting)
- `"random"` as a video/music path is resolved at render time to a random file from the corresponding directory
- `generator/` is a standalone package — it imports nothing from `gui/`. `gui/` imports from `generator/` via `from generator import ...`
- Circular imports mitigated by lazy re-exports at the bottom of `gui/config.py` and by isolating `ws_manager.py` as its own module
