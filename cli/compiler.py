import os
import re
import uuid
import json
import shutil
import random
import hashlib
import asyncio
import numpy as np
import soundfile as sf
from openai import OpenAI
import questionary

from generator import generate_voice, generate_ass_subtitles, compile_video
from cli.state import state, settings
from cli.config import (
    CACHE_DIR, OUTPUT_DIR, VIDEOS_DIR, logger, console, load_emoji_map
)
from cli.utils import discover_opencode_keys

_WHISPER_MODEL = None
_WHISPER_MODEL_NAME = None

def compile_video_flow(skip_confirm=False, custom_output_filename=None, progress_callback=None):
    global _WHISPER_MODEL, _WHISPER_MODEL_NAME
    
    console.print("[bold yellow]5. COMPILE TIKTOK SHORT[/]")
    script = state["script_text"].strip()
    voice = state["selected_voice"]
    
    if not script:
        console.print("[red]Error: Script is empty. Please generate or edit a script first.[/]")
        return False
        
    if not state["bg_video_path"]:
        console.print("[red]Error: No top/primary background video configured. Please configure it first.[/]")
        return False
        
    # Resolve random selections
    video_files = []
    if os.path.exists(VIDEOS_DIR):
        video_files = [
            os.path.join(VIDEOS_DIR, f) 
            for f in os.listdir(VIDEOS_DIR) 
            if f.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.avi'))
        ]
        
    resolved_top_path = state["bg_video_path"]
    resolved_bottom_path = state["bg_video_bottom_path"]
    
    if resolved_top_path == "random":
        if not video_files:
            console.print("[red]Error: No background videos found in videos/ folder to select from.[/]")
            return False
        resolved_top_path = random.choice(video_files)
        console.print(f"[yellow]Resolved Top Video: {os.path.basename(resolved_top_path)}[/]")
        
    if resolved_bottom_path == "random":
        if not video_files:
            console.print("[red]Error: No background videos found in videos/ folder to select from.[/]")
            return False
        # Try to select a different video than the top video if possible
        remaining = [v for v in video_files if v != resolved_top_path]
        if remaining:
            resolved_bottom_path = random.choice(remaining)
        else:
            resolved_bottom_path = random.choice(video_files)
        console.print(f"[yellow]Resolved Bottom Video: {os.path.basename(resolved_bottom_path)}[/]")
        
    # Validate final paths
    if not resolved_top_path or not os.path.exists(resolved_top_path):
        console.print(f"[red]Error: Top background video file '{resolved_top_path}' not found.[/]")
        return False
        
    if state["bg_video_bottom_path"] and (not resolved_bottom_path or not os.path.exists(resolved_bottom_path)):
        console.print(f"[red]Error: Bottom background video file '{resolved_bottom_path}' not found.[/]")
        return False
        
    # Get settings values
    api_key = settings.get("api_key") or os.environ.get("OPENAI_API_KEY")
    base_url = settings.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    whisper_api_key = settings.get("whisper_api_key") or os.environ.get("WHISPER_API_KEY")
    whisper_base_url = settings.get("whisper_base_url") or os.environ.get("WHISPER_BASE_URL")
    use_local_whisper = settings.get("local_whisper", True)
    local_model_name = settings.get("local_whisper_model", "tiny")
    
    opencode_key, opencode_openai_token = discover_opencode_keys()
    if not api_key:
        api_key = opencode_key
        if api_key and not base_url:
            base_url = "https://opencode.ai/zen/go/v1"
            
    if not use_local_whisper and not api_key:
        console.print("[red]Error: API Key is required to transcribe audio when local Whisper is disabled. Configure it in Settings.[/]")
        return False
        
    if not skip_confirm:
        confirm = questionary.confirm("Are you sure you want to compile the TikTok Short now?").ask()
        if not confirm:
            return False
        
    job_id = str(uuid.uuid4())
    audio_path = os.path.join(CACHE_DIR, f"audio_{job_id}.wav")
    subs_path = os.path.join(CACHE_DIR, f"subs_{job_id}.ass")
    if custom_output_filename:
        output_filename = custom_output_filename
    else:
        output_filename = f"rendered_{job_id}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    try:
        # Load subtitle style settings
        sub_opts = {
            "font_name": state.get("sub_font") or settings.get("sub_font", "Arial"),
            "font_size": int(state.get("sub_size") or settings.get("sub_size", 72)),
            "primary_color": state.get("sub_color") or settings.get("sub_color", "#FFFFFF"),
            "highlight_color": state.get("sub_highlight") or settings.get("sub_highlight", "#00FFFF"),
            "outline_color": state.get("sub_outline") or settings.get("sub_outline", "#000000"),
            "outline_width": int(state.get("sub_outline_width") if state.get("sub_outline_width") is not None else settings.get("sub_outline_width", 5)),
            "bold": state.get("sub_bold") if state.get("sub_bold") is not None else settings.get("sub_bold", True),
            "word_pop": state.get("word_pop") if state.get("word_pop") is not None else settings.get("word_pop", True),
            "word_pop_scale": float(state.get("word_pop_scale") if state.get("word_pop_scale") is not None else settings.get("word_pop_scale", 1.15)),
            "inactive_dim": state.get("inactive_dim") if state.get("inactive_dim") is not None else settings.get("inactive_dim", True),
            "inactive_alpha": state.get("inactive_alpha") if state.get("inactive_alpha") is not None else settings.get("inactive_alpha", "88"),
            "enable_emojis": state.get("enable_emojis") if state.get("enable_emojis") is not None else settings.get("enable_emojis", True)
        }
        
        if state["bg_video_bottom_path"]:
            # Stacked split screen: position subtitle centered in the bottom video
            sub_opts["alignment"] = 2
            sub_opts["margin_v"] = 440
        else:
            # Full screen: standard Alignment 5 (Middle center)
            sub_opts["alignment"] = 5
            sub_opts["margin_v"] = 10
        
        # Load volume settings
        voice_vol = state["voice_volume"]
        if voice_vol is None:
            voice_vol = settings.get("voice_volume", 1.0)
        music_vol = state["music_volume"]
        if music_vol is None:
            music_vol = settings.get("music_volume", 0.15)

        # Compute cache key for audio & whisper transcription
        import hashlib
        cache_str = f"{voice}:{use_local_whisper}:{local_model_name}:{script}"
        cache_key = hashlib.md5(cache_str.encode("utf-8")).hexdigest()
        cached_audio_path = os.path.join(CACHE_DIR, f"cached_audio_{cache_key}.wav")
        cached_words_path = os.path.join(CACHE_DIR, f"cached_words_{cache_key}.json")
        
        words = []
        use_cached = os.path.exists(cached_audio_path) and os.path.exists(cached_words_path)
        
        if use_cached:
            console.print("[bold green]ℹ️ Found cached audio and transcription for this script. Reusing...[/]")
            try:
                # Copy cached audio to the temporary run path
                shutil.copy(cached_audio_path, audio_path)
                # Load words from cached json
                with open(cached_words_path, "r", encoding="utf-8") as f:
                    words = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read cached words json or copy audio, invalidating cache: {e}", exc_info=True)
                use_cached = False
                words = []
                
        if not use_cached:
            # Split script into sentences for granular caching
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]
            if not sentences:
                sentences = [script]
                
            audio_arrays = []
            sample_rate = 24000  # Default for Kokoro
            current_offset = 0.0
            
            # Setup Whisper client if using API
            w_client = None
            if not use_local_whisper:
                try:
                    if whisper_api_key:
                        w_client = OpenAI(api_key=whisper_api_key, base_url=whisper_base_url)
                    elif whisper_base_url:
                        w_client = OpenAI(api_key=api_key, base_url=whisper_base_url)
                    elif base_url and "opencode.ai" in base_url:
                        w_key = opencode_openai_token or os.environ.get("OPENAI_API_KEY")
                        if w_key:
                            w_client = OpenAI(api_key=w_key, base_url="https://api.openai.com/v1")
                        else:
                            w_client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
                    else:
                        w_client = OpenAI(api_key=api_key, base_url=base_url)
                except Exception as e:
                    logger.warning(f"Failed to initialize Whisper API client: {e}")

            for s_idx, sentence in enumerate(sentences):
                s_cache_str = f"{voice}:{use_local_whisper}:{local_model_name}:{sentence}"
                s_cache_key = hashlib.md5(s_cache_str.encode("utf-8")).hexdigest()
                s_audio_path = os.path.join(CACHE_DIR, f"sentence_audio_{s_cache_key}.wav")
                s_words_path = os.path.join(CACHE_DIR, f"sentence_words_{s_cache_key}.json")
                
                s_words = []
                s_audio_data = None
                s_sr = None
                
                use_s_cached = os.path.exists(s_audio_path) and os.path.exists(s_words_path)
                
                if use_s_cached:
                    try:
                        with open(s_words_path, "r", encoding="utf-8") as f:
                            s_words = json.load(f)
                        s_audio_data, s_sr = sf.read(s_audio_path)
                        sample_rate = s_sr
                    except Exception as e:
                        logger.warning(f"Failed to read cached sentence {s_idx}: {e}", exc_info=True)
                        use_s_cached = False
                
                if not use_s_cached:
                    console.print(f"[yellow]  → Generating & transcribing sentence {s_idx+1}/{len(sentences)}: \"{sentence[:40]}...\"[/]")
                    s_temp_audio_path = os.path.join(CACHE_DIR, f"s_temp_{job_id}_{s_idx}.wav")
                    
                    # 1. Kokoro ONNX Voice Generation
                    asyncio.run(generate_voice(sentence, voice, s_temp_audio_path))
                    
                    # 2. Whisper Transcription
                    s_words = []
                    transcribed = False
                    
                    if use_local_whisper or w_client is None:
                        try:
                            from faster_whisper import WhisperModel
                            if _WHISPER_MODEL is None or _WHISPER_MODEL_NAME != local_model_name:
                                _WHISPER_MODEL = WhisperModel(local_model_name, device="cpu", compute_type="int8")
                                _WHISPER_MODEL_NAME = local_model_name
                            segments, info = _WHISPER_MODEL.transcribe(s_temp_audio_path, word_timestamps=True)
                            for segment in segments:
                                if segment.words:
                                    for w in segment.words:
                                        s_words.append({
                                            "word": w.word,
                                            "start": w.start,
                                            "end": w.end
                                        })
                            if s_words:
                                transcribed = True
                        except Exception as e:
                            logger.error(f"Local Whisper transcription failed for sentence: {e}", exc_info=True)
                    
                    if not transcribed and w_client is not None:
                        try:
                            with open(s_temp_audio_path, "rb") as f:
                                transcription = w_client.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=f,
                                    response_format="verbose_json",
                                    timestamp_granularities=["word"]
                                )
                            if hasattr(transcription, "words") and transcription.words:
                                for w in transcription.words:
                                    s_words.append({
                                        "word": w.get("word") if isinstance(w, dict) else getattr(w, "word"),
                                        "start": w.get("start") if isinstance(w, dict) else getattr(w, "start"),
                                        "end": w.get("end") if isinstance(w, dict) else getattr(w, "end")
                                    })
                                transcribed = True
                        except Exception as e:
                            logger.error(f"Whisper API transcription failed for sentence: {e}", exc_info=True)
                    
                    # Fallback to local
                    if not transcribed and not use_local_whisper:
                        try:
                            from faster_whisper import WhisperModel
                            if _WHISPER_MODEL is None or _WHISPER_MODEL_NAME != local_model_name:
                                _WHISPER_MODEL = WhisperModel(local_model_name, device="cpu", compute_type="int8")
                                _WHISPER_MODEL_NAME = local_model_name
                            segments, info = _WHISPER_MODEL.transcribe(s_temp_audio_path, word_timestamps=True)
                            for segment in segments:
                                if segment.words:
                                    for w in segment.words:
                                        s_words.append({
                                            "word": w.word,
                                            "start": w.start,
                                            "end": w.end
                                        })
                            if s_words:
                                transcribed = True
                        except Exception as local_e:
                            logger.error(f"Local Whisper fallback failed for sentence: {local_e}", exc_info=True)
                            
                    # Fallback to dummy timing if everything failed
                    if not s_words:
                        try:
                            s_audio_data, s_sr = sf.read(s_temp_audio_path)
                            duration = len(s_audio_data) / s_sr
                        except Exception:
                            duration = 1.0
                        s_words = [{
                            "word": sentence,
                            "start": 0.0,
                            "end": duration
                        }]
                        
                    # Save to cache
                    try:
                        shutil.copy(s_temp_audio_path, s_audio_path)
                        with open(s_words_path, "w", encoding="utf-8") as f:
                            json.dump(s_words, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Failed to cache sentence details: {e}", exc_info=True)
                        
                    try:
                        s_audio_data, s_sr = sf.read(s_temp_audio_path)
                        sample_rate = s_sr
                    except Exception as e:
                        logger.error(f"Failed to load generated audio array: {e}", exc_info=True)
                        raise e
                    finally:
                        if os.path.exists(s_temp_audio_path):
                            try: os.remove(s_temp_audio_path)
                            except Exception: pass
                            
                # Adjust timing offset and append
                for w in s_words:
                    words.append({
                        "word": w["word"],
                        "start": w["start"] + current_offset,
                        "end": w["end"] + current_offset
                    })
                audio_arrays.append(s_audio_data)
                current_offset += len(s_audio_data) / sample_rate
                
            # Concatenate all sentence audios and save
            if audio_arrays:
                try:
                    concatenated_audio = np.concatenate(audio_arrays)
                    sf.write(audio_path, concatenated_audio, sample_rate)
                except Exception as e:
                    logger.error(f"Failed to concatenate and save audios: {e}", exc_info=True)
                    raise e
                    
            # Save final stitched output to full cache
            try:
                shutil.copy(audio_path, cached_audio_path)
                with open(cached_words_path, "w", encoding="utf-8") as f:
                    json.dump(words, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to save full cache: {e}", exc_info=True)
            
        audio_duration = words[-1]["end"] + 0.5
        console.print(f"[green]Transcription complete: {len(words)} words. Duration: {audio_duration:.2f}s[/]")
        
        # 3. Create Styled Subtitles File
        console.print("[yellow][3/4] Generating ASS subtitle file with custom styling...[/]")
        generate_ass_subtitles(words, subs_path, style_opts=sub_opts, emoji_map=load_emoji_map())
        console.print("[green]ASS subtitles generated.[/]")
        
        # 4. Render video using FFmpeg
        console.print("[yellow][4/4] Rendering vertical video using FFmpeg (cropping 9:16, mixing audio, burning subtitles)...[/]")
        render_preset = settings.get("render_preset", "veryfast")
        render_res = settings.get("render_resolution", "1080p")
        compile_video(
            bg_video_path=resolved_top_path,
            audio_path=audio_path,
            subs_path=subs_path,
            output_path=output_path,
            audio_duration=audio_duration,
            music_path=state["bg_music_path"],
            voice_volume=voice_vol,
            music_volume=music_vol,
            bg_video_bottom_path=resolved_bottom_path,
            render_preset=render_preset,
            render_resolution=render_res,
            progress_callback=progress_callback
        )
        
        console.print(f"\n[green]🎉 RENDER SUCCESSFUL! Saved to output/{output_filename}[/]\n")
        return True
    except Exception as e:
        logger.error(f"Video compilation failed for job '{job_id}': {e}", exc_info=True)
        console.print(f"[red]Video compilation failed: {str(e)}[/]")
        console.print("[yellow]Detailed error logs are available in logs/app.log[/]")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        return False
    finally:
        for p in [audio_path, subs_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
