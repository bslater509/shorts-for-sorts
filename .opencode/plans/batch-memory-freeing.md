# Free more memory during batch jobs

## Change 1: Free `concatenated_audio` + `audio_arrays` after saving to disk

**File:** `gui/compiler.py`

After line 332 (`console.print(f"[yellow]  → Transcribing full audio file...")`), add:

```python
del audio_arrays, concatenated_audio
import gc; gc.collect()
```

## Change 2: Unload Whisper model immediately after transcription

**File:** `gui/compiler.py`

After line 416 (`console.print(f"[green]Transcription complete: ...")`), add:

```python
unload_whisper_model()
```

## Change 3: Free `words` list after subtitle generation

**File:** `gui/compiler.py`

After line 433 (`console.print("[green]ASS subtitles generated.[/]")`), add:

```python
del words
```

## Change 4: Add heap cleanup after batch completes

**File:** `gui/server.py`

In the `finally` block (lines 1605-1612), after `batch_state["in_progress"] = False`, add:

```python
import gc
gc.collect()
try:
    import ctypes
    libc = ctypes.CDLL("libc.so.6")
    libc.malloc_trim(0)
except Exception:
    pass
```
