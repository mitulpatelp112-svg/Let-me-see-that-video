"""Core absorption logic: URL in, structured library record out.

The network-touching pieces (metadata extraction, caption download, media
download) are injectable so the absorber can be unit-tested without hitting the
network or needing yt-dlp installed.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .config import Config
from .library import Library
from . import transcript as _transcript

# A function that takes a URL and returns yt-dlp's info dict.
Extractor = Callable[[str], dict[str, Any]]
# A function that downloads captions into a dir and returns plain text or None.
CaptionFetcher = Callable[[str, Path], Optional[str]]
# A function that downloads media into a dir and returns the saved file path.
MediaDownloader = Callable[[str, Path, bool, bool], Optional[str]]

_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)

_PLATFORM_HOSTS = {
    "youtube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "tiktok": ("tiktok.com",),
    "instagram": ("instagram.com", "instagr.am"),
    "twitter": ("twitter.com", "x.com"),
    "facebook": ("facebook.com", "fb.watch"),
    "vimeo": ("vimeo.com",),
    "reddit": ("reddit.com", "redd.it"),
}


def find_urls(text: str) -> list[str]:
    """Extract http(s) URLs from arbitrary text (e.g. a shared message)."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _URL_RE.findall(text or ""):
        url = match.rstrip(".,);]")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    for platform, hosts in _PLATFORM_HOSTS.items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return platform
    return host or "unknown"


# --------------------------------------------------------------------------
# Default network implementations (require yt-dlp at runtime).
# --------------------------------------------------------------------------
def _ydl_extract(url: str) -> dict[str, Any]:
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return ydl.sanitize_info(info)


def _ydl_fetch_captions(url: str, dest_dir: Path) -> Optional[str]:
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en.*", "en"],
        "subtitlesformat": "vtt/srt/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    caption_files = sorted(dest_dir.glob("*.vtt")) + sorted(dest_dir.glob("*.srt"))
    if not caption_files:
        return None
    return _transcript.parse_caption_file(caption_files[0])


def _ydl_download_media(
    url: str, dest_dir: Path, want_video: bool, want_audio: bool
) -> Optional[str]:
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
    }
    if want_audio and not want_video:
        opts["format"] = "bestaudio/best"
    else:
        opts["format"] = "bv*+ba/best"
    saved: list[str] = []

    def _hook(d: dict[str, Any]) -> None:
        if d.get("status") == "finished" and d.get("filename"):
            saved.append(d["filename"])

    opts["progress_hooks"] = [_hook]
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return saved[-1] if saved else None


# --------------------------------------------------------------------------
def build_record(info: dict[str, Any], url: str) -> dict[str, Any]:
    """Normalise a yt-dlp info dict into a compact library record."""
    record_id = str(info.get("id") or _hash_url(url))
    webpage_url = info.get("webpage_url") or url
    return {
        "id": record_id,
        "url": url,
        "webpage_url": webpage_url,
        "platform": detect_platform(webpage_url),
        "title": info.get("title") or info.get("fulltitle") or "(untitled)",
        "uploader": info.get("uploader") or info.get("uploader_id"),
        "channel": info.get("channel") or info.get("channel_id"),
        "description": info.get("description"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "tags": info.get("tags") or info.get("categories") or [],
        "thumbnail": info.get("thumbnail"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
    }


def absorb(
    url: str,
    config: Config,
    library: Library | None = None,
    *,
    extractor: Extractor | None = None,
    caption_fetcher: CaptionFetcher | None = None,
    media_downloader: MediaDownloader | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Absorb a single URL into the library and return the stored record."""
    library = library or Library(config.library_dir)
    extractor = extractor or _ydl_extract
    caption_fetcher = caption_fetcher or _ydl_fetch_captions
    media_downloader = media_downloader or _ydl_download_media

    info = extractor(url)
    record = build_record(info, url)
    record_id = record["id"]

    if not force and library.has(record_id):
        existing = library.get(record_id)
        if existing is not None:
            existing["already_absorbed"] = True
            return existing

    item_dir = library.item_dir(record_id)
    item_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}

    # 1) Transcript — prefer captions, fall back to local Whisper if enabled.
    transcript_text: str | None = None
    transcript_source: str | None = None
    try:
        transcript_text = caption_fetcher(url, item_dir)
        if transcript_text:
            transcript_source = "captions"
    except Exception:  # noqa: BLE001 — never let captions break absorption
        transcript_text = None

    # 2) Media download (optional).
    if config.download_video or config.download_audio:
        try:
            saved = media_downloader(
                url, item_dir, config.download_video, config.download_audio
            )
            if saved:
                key = "audio" if (config.download_audio and not config.download_video) else "video"
                files[key] = _relpath(saved, library.root)
        except Exception:  # noqa: BLE001
            pass

    # 3) Whisper fallback when there were no captions.
    if not transcript_text and config.transcribe and files.get("audio"):
        try:
            text = _transcript.transcribe_audio(
                library.root / files["audio"], config.whisper_model
            )
            if text:
                transcript_text = text
                transcript_source = "whisper"
        except Exception:  # noqa: BLE001
            pass

    if transcript_text:
        transcript_path = item_dir / "transcript.txt"
        transcript_path.write_text(transcript_text, encoding="utf-8")
        files["transcript"] = _relpath(transcript_path, library.root)

    record["transcript"] = transcript_text
    record["transcript_source"] = transcript_source
    record["files"] = files
    record["absorbed_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()

    # Persist the full per-item metadata next to its media.
    (item_dir / "meta.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    library.add(record)
    return record


def _hash_url(url: str) -> str:
    import hashlib

    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _relpath(path: str | Path, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)
