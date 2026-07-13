# Plan: Merge Two LLM Calls Into One in Batch Generation

## Problem
`gui/batch.py:llm_job_worker()` makes **two sequential LLM calls** per video:
1. **Script generation** (streaming, ~lines 328-361) — generates the full script
2. **Metadata generation** (~lines 363-413) — takes the script and asks for a title + 5 hashtags

This doubles latency and token cost for a trivial follow-up.

## Solution
Fold the metadata request into the **first** LLM call by appending instructions to the system prompt, then parse `TITLE:`/`HASHTAGS:` from the already-streamed response.

---

## Change 1: `gui/server.py` — Add metadata instruction to batch system prompt

**Location:** `batch_worker_thread()`, around line 1210

**What:** Append a 9th guideline to `default_system_prompt`:

```python
             "8. Source: Never mention Reddit, subreddits, or forums. Tell the story directly as if it happened to someone.\n"
             "9. After the script ends, include exactly one line 'TITLE: <short catchy title under 5 words>' followed by one line 'HASHTAGS: <5 trending hashtags>' based on your script. Do not include these lines within the script body."
```

**Why:** Only the batch system prompt is used by `llm_job_worker`. The single-video endpoint (`generate_viral_script`) uses its own copy of the same default string — we leave that unchanged so single-video output stays clean.

---

## Change 2: `gui/batch.py` — Replace second LLM call with in-stream parsing

**Location:** `llm_job_worker()`, lines 363-414

**Replace the entire block** (lines 363-414, from `try:` through the `except` fallback) with:

```python
        # Parse title and hashtags from the same script response
        try:
            title = "batch_video"
            hashtags = ""
            cleaned_lines = []
            for line in script_text.split('\n'):
                if line.startswith("TITLE:"):
                    title = line.replace("TITLE:", "").strip()
                elif line.startswith("HASHTAGS:"):
                    hashtags = line.replace("HASHTAGS:", "").strip()
                else:
                    cleaned_lines.append(line)
            script_text = "\n".join(cleaned_lines).strip()

            safe_title = re.sub(r'[\s\-]+', '_', title.lower())
            safe_title = re.sub(r'[^\w_]', '', safe_title).strip('_')
            if not safe_title:
                safe_title = "batch_video"

            orig_filename = job_config["output_filename"]
            timestamp_match = re.search(r"rendered_batch_(\d+)_", orig_filename)
            timestamp = timestamp_match.group(1) if timestamp_match else str(int(time.time()))

            new_filename = f"{safe_title}_{timestamp}_{idx}.mp4"
            job_config["output_filename"] = new_filename
            job_config["generated_title"] = title
            job_config["generated_hashtags"] = hashtags
        except Exception as e:
            # Fallback if parsing fails
            job_config["generated_title"] = "Batch Video"
            job_config["generated_hashtags"] = "#shorts #video"
```

**What this does:**
- Iterates over the already-streamed `script_text` lines
- Extracts `TITLE:` and `HASHTAGS:` lines into config keys
- **Removes those metadata lines** from `script_text` so TTS gets clean script text
- Falls back gracefully if parsing fails (same as current fallback)
- Eliminates the second API call, retry loop, `meta_prompt`, and `meta_temp` ref entirely

---

## Verification
- Run a small batch (2-3 videos) and check:
  - `generated_title` and `generated_hashtags` are populated correctly
  - The script text fed to TTS does NOT contain `TITLE:` or `HASHTAGS:` lines
  - Output filename uses the parsed title
- Run the single-video `/api/script/generate` endpoint — it should be unaffected (no metadata lines in output)
