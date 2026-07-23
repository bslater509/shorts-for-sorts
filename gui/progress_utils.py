"""Progress display utilities extracted from batch.py — zero behavioral change."""

import os
import re
import time

import psutil
from rich.table import Table

from gui.config import console, logger


def log_memory_usage(stage: str):
    proc = psutil.Process()
    rss_mb = proc.memory_info().rss / 1024 / 1024
    mem = psutil.virtual_memory()
    logger.info(
        f"[Batch Memory] {stage}: RSS={rss_mb:.0f}MB | "
        f"Avail={mem.available / 1024 / 1024:.0f}MB / "
        f"{mem.total / 1024 / 1024:.0f}MB ({mem.percent}%)"
    )


def get_progress_percentage(status):
    if status == "Queued":
        return 0
    elif status == "Waiting for LLM":
        return 5
    elif status.startswith("LLM Script"):
        match = re.search(r"\((\d+)\s*words\)", status)
        if match:
            word_count = int(match.group(1))
            pct = min(14, 5 + int((word_count / 400) * 9))
            return pct
        return 10
    elif status == "LLM Metadata":
        return 15
    elif status == "Waiting for Compilation":
        return 20
    elif status.startswith("Voice Generation"):
        match = re.search(r"\((\d+)/(\d+)\)", status)
        if match:
            s_idx = int(match.group(1))
            total = int(match.group(2))
            if total > 0:
                return 20 + int((s_idx / total) * 25)
        return 30
    elif status == "Reusing Cache (Voice)":
        return 45
    elif status == "Compiling":
        return 28
    elif status.startswith("Transcription"):
        match = re.search(r"\((\d+)%\)", status)
        if match:
            pct = int(match.group(1))
            return 45 + int((pct / 100) * 10)
        return 48
    elif status == "Subtitles":
        return 55
    elif status.startswith("FFmpeg Rendering"):
        match = re.search(r"\((\d+\.?\d*)%\)", status)
        if match:
            pct = float(match.group(1))
            return 55 + int((pct / 100) * 45)
        return 75
    elif status == "Done":
        return 100
    elif status.startswith("Failed"):
        return None
    return 0


def make_progress_bar(percentage, status, width=15):
    filled = int(width * percentage / 100)
    filled = max(0, min(width, filled))
    empty = width - filled

    if status == "Done":
        bar_color = "green"
        pct_color = "green"
        desc = "[bold green]✓ Done[/]"
    elif status == "Queued":
        bar_color = "grey37"
        pct_color = "grey37"
        desc = "[dim]Queued...[/]"
    else:
        bar_color = "cyan"
        pct_color = "yellow"
        desc = f"[bold yellow]🔄 {status}...[/]"

    bar = f"[{bar_color}]" + "█" * filled + f"[/{bar_color}][grey37]" + "░" * empty + "[/grey37]"
    return f"{bar} [{pct_color}]{percentage:3d}%[/{pct_color}] {desc}"


def format_elapsed(duration):
    total_seconds = int(duration) if duration >= 0 else 0
    m = total_seconds // 60
    s = total_seconds % 60
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def display_progress_table(progress_dict, total_shorts, job_details):
    table = Table(
        title="[bold magenta]Concurrent Batch Generation Progress[/bold magenta]",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Short #", justify="center", style="dim", width=8)
    table.add_column("Category & Topic", justify="left")
    table.add_column("Voice & Layout", justify="left")
    table.add_column("Status / Progress", justify="left")
    table.add_column("Elapsed", justify="center", style="dim", width=12)

    for idx in range(1, total_shorts + 1):
        details = job_details.get(idx, {})
        topic = details.get("topic", "Unknown")
        voice_layout = f"{details.get('voice', 'Unknown')} | {details.get('layout', 'Unknown')}"
        status = progress_dict.get(idx, "Queued")

        # Calculate elapsed time
        start_time = progress_dict.get(f"{idx}_start")
        end_time = progress_dict.get(f"{idx}_end")

        elapsed_str = "--"
        if start_time:
            if end_time:
                duration = end_time - start_time
                elapsed_str = (
                    f"{format_elapsed(duration)} (Done)"
                    if status == "Done"
                    else format_elapsed(duration)
                )
            else:
                duration = time.time() - start_time
                elapsed_str = format_elapsed(duration)

        # Calculate percentage
        pct = get_progress_percentage(status)

        if pct is None:
            status_str = f"[bold red]✗ {status}[/]"
        else:
            status_str = make_progress_bar(pct, status)

        table.add_row(f"#{idx}", topic, voice_layout, status_str, elapsed_str)

    return table
