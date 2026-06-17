"""Transcript helpers: parse caption files and (optionally) run Whisper."""

from __future__ import annotations

import re
from pathlib import Path

_TIMESTAMP_RE = re.compile(r"-->")
_CUE_NUMBER_RE = re.compile(r"^\d+$")
# Inline tags such as <00:00:01.000> or <c> used by YouTube auto-captions.
_TAG_RE = re.compile(r"<[^>]+>")


def parse_vtt(text: str) -> str:
    """Turn WebVTT / SRT caption text into clean, de-duplicated plain text."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if line.startswith(("NOTE", "STYLE", "Kind:", "Language:")):
            continue
        if _TIMESTAMP_RE.search(line):
            continue
        if _CUE_NUMBER_RE.match(line):
            continue
        cleaned = _TAG_RE.sub("", line).strip()
        cleaned = cleaned.replace("&nbsp;", " ")
        if not cleaned:
            continue
        # YouTube auto-captions repeat each line as it scrolls; drop consecutive
        # duplicates and lines fully contained in the previous one.
        if lines and (cleaned == lines[-1] or cleaned in lines[-1]):
            continue
        lines.append(cleaned)
    return "\n".join(lines).strip()


def parse_caption_file(path: str | Path) -> str:
    return parse_vtt(Path(path).read_text(encoding="utf-8", errors="replace"))


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        pass
    try:
        import whisper  # noqa: F401

        return True
    except ImportError:
        return False


def transcribe_audio(audio_path: str | Path, model_name: str = "base") -> str | None:
    """Transcribe an audio file locally using Whisper, if it is installed.

    Returns ``None`` when no Whisper backend is available so callers can fall
    back gracefully instead of crashing.
    """
    audio_path = str(audio_path)
    # Prefer faster-whisper (lighter, no torch requirement on many platforms).
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path)
        return "\n".join(seg.text.strip() for seg in segments).strip() or None
    except ImportError:
        pass

    try:
        import whisper

        model = whisper.load_model(model_name)
        result = model.transcribe(audio_path)
        return str(result.get("text", "")).strip() or None
    except ImportError:
        return None
