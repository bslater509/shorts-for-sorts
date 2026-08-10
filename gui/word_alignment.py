"""Word-timing alignment logic for the video compiler.

Extracted from ``gui/video_compiler.py``.  Corrects mis-transcribed words,
drops hallucinated/duplicated words, and inserts script words the transcription
missed (with interpolated timing) using ``difflib.SequenceMatcher``.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

SCRIPT_INSERT_GAP_S: float = 0.3
"""Nominal per-word slot (seconds) for script-only words with no timing anchor."""


def interpolate_inserted_words(
    tokens: list[str],
    prev_end: float,
    next_start: float | None,
) -> list[dict[str, Any]]:
    """Assign interpolated timing to script-only words inserted during alignment.

    Inserted words are spread evenly across the ``(prev_end, next_start)``
    window so they land between the surrounding anchored words.  When no forward
    anchor exists (inserts at the very end of the script) each word is given a
    nominal :data:`SCRIPT_INSERT_GAP_S` slot instead.

    Args:
        tokens: Script word texts to insert.
        prev_end: End time of the previous anchored word.
        next_start: Start time of the next anchored word, or ``None``.

    Returns:
        List of word dicts with interpolated ``"start"``/``"end"`` times.
    """
    if not tokens:
        return []
    if next_start is None or next_start <= prev_end:
        out: list[dict[str, Any]] = []
        cursor: float = prev_end
        for tok in tokens:
            out.append(
                {"word": tok, "start": cursor, "end": cursor + SCRIPT_INSERT_GAP_S}
            )
            cursor += SCRIPT_INSERT_GAP_S
        return out
    gap: float = (next_start - prev_end) / (len(tokens) + 1)
    out = []
    cursor: float = prev_end + gap
    for tok in tokens:
        out.append({"word": tok, "start": cursor, "end": cursor + gap})
        cursor += gap
    return out


def align_words_to_script(
    words: list[dict[str, Any]], script: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Align transcript word timings to the original script text.

    Uses ``difflib.SequenceMatcher`` to correct mis-transcribed words (e.g.
    homophones), drop hallucinated/duplicated words, and insert script words the
    transcription missed with interpolated timing.  ``[tag]`` directives in the
    script (e.g. ``[pause=1]``) are stripped before matching.

    Args:
        words: Transcript word dicts with ``"word"``, ``"start"``, ``"end"``.
        script: The original script text.

    Returns:
        Tuple of ``(aligned_words, stats)``.  ``stats`` holds ``total``,
        ``corrected``, ``inserted``, ``removed``, and ``match_pct`` counters.
    """
    no_align_stats: dict[str, Any] = {
        "total": len(words),
        "corrected": 0,
        "inserted": 0,
        "removed": 0,
        "match_pct": 0.0,
    }

    clean_script: str = re.sub(r"\[[^\]]+\]", "", script)
    script_tokens: list[str] = [
        m.group(0) for m in re.finditer(r"[\w']+", clean_script)
    ]
    if len(words) < 2 or not script_tokens:
        return words, no_align_stats

    transcript_tokens: list[dict[str, Any]] = []
    for word in words:
        text: Any = word.get("word", "")
        if not isinstance(text, str):
            continue
        for m in re.finditer(r"[\w']+", text):
            transcript_tokens.append({"text": m.group(0), "word": word})

    matcher = difflib.SequenceMatcher(
        None,
        [t["text"].lower() for t in transcript_tokens],
        [s.lower() for s in script_tokens],
        autojunk=False,
    )

    # planned: (script_token_text, transcript_word | None)
    # A None transcript word means the script token has no timing anchor yet.
    planned: list[tuple[str, dict[str, Any] | None]] = []
    matched: int = 0
    corrected: int = 0
    removed: int = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            matched += i2 - i1
            for k in range(i2 - i1):
                planned.append(
                    (script_tokens[j1 + k], transcript_tokens[i1 + k]["word"])
                )
        elif tag == "replace":
            n_trans: int = i2 - i1
            n_script: int = j2 - j1
            paired: int = min(n_trans, n_script)
            for k in range(paired):
                stok: str = script_tokens[j1 + k]
                ttok: dict[str, Any] = transcript_tokens[i1 + k]
                if stok.lower() == ttok["text"].lower():
                    matched += 1
                else:
                    corrected += 1
                planned.append((stok, ttok["word"]))
            if n_script > n_trans:
                # Leftover script words have no transcript timing -> insert.
                for k in range(paired, n_script):
                    planned.append((script_tokens[j1 + k], None))
            else:
                # Leftover transcript words are hallucinations -> drop.
                removed += n_trans - n_script
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "insert":
            for k in range(j1, j2):
                planned.append((script_tokens[k], None))

    inserted: int = sum(1 for _, tw in planned if tw is None)
    aligned: list[dict[str, Any]] = []
    prev_end: float = 0.0
    i: int = 0
    total_planned: int = len(planned)
    while i < total_planned:
        stok, tw = planned[i]
        if tw is not None:
            aligned.append(
                {
                    "word": stok,
                    "start": float(tw.get("start", 0.0)),
                    "end": float(tw.get("end", 0.0)),
                }
            )
            prev_end = aligned[-1]["end"]
            i += 1
            continue
        # Run of script-only tokens: interpolate between surrounding anchors.
        j: int = i
        gap_tokens: list[str] = []
        while j < total_planned and planned[j][1] is None:
            gap_tokens.append(planned[j][0])
            j += 1
        next_anchor: dict[str, Any] | None = (
            planned[j][1] if j < total_planned else None
        )
        next_start: float | None = (
            float(next_anchor.get("start", 0.0)) if next_anchor is not None else None
        )
        aligned.extend(interpolate_inserted_words(gap_tokens, prev_end, next_start))
        prev_end = aligned[-1]["end"]
        i = j

    stats: dict[str, Any] = {
        "total": len(aligned),
        "corrected": corrected,
        "inserted": inserted,
        "removed": removed,
        "match_pct": round(100.0 * matched / len(script_tokens), 1),
    }
    return aligned, stats
