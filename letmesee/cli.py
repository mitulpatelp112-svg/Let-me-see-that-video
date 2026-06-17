"""Command-line interface — this is the command you tell Claude to run.

    letmesee absorb <url> [<url> ...]   # fetch + absorb one or more videos
    letmesee list                       # list everything in the library
    letmesee search <query>             # full-text search title/transcript/...
    letmesee show <id>                  # print full detail for one video
    letmesee stats                      # quick library summary
    letmesee bot                        # run the always-on Telegram bot
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from .absorber import absorb
from .config import Config
from .library import Library


def _fmt_duration(seconds: Any) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "?"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _print_record_line(record: dict[str, Any]) -> None:
    print(f"  [{record.get('platform','?'):<9}] {record.get('title')}")
    meta = []
    if record.get("uploader"):
        meta.append(str(record["uploader"]))
    meta.append(_fmt_duration(record.get("duration")))
    if record.get("transcript_source"):
        meta.append(f"transcript:{record['transcript_source']}")
    print(f"             {' · '.join(meta)}  ({record.get('id')})")


def _cmd_absorb(args: argparse.Namespace, config: Config, library: Library) -> int:
    failed = 0
    for url in args.urls:
        try:
            record = absorb(url, config, library, force=args.force)
            status = "already absorbed" if record.get("already_absorbed") else "absorbed"
            print(f"✅ {status}: {record.get('title')}  ({record.get('id')})")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"⚠️  failed to absorb {url}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 1 if failed else 0


def _cmd_list(args: argparse.Namespace, config: Config, library: Library) -> int:
    records = library.all()
    if not records:
        print("Library is empty. Absorb something with: letmesee absorb <url>")
        return 0
    print(f"{len(records)} video(s):")
    for record in records:
        _print_record_line(record)
    return 0


def _cmd_search(args: argparse.Namespace, config: Config, library: Library) -> int:
    query = " ".join(args.query)
    results = library.search(query)
    print(f"{len(results)} match(es) for {query!r}:")
    for record in results:
        _print_record_line(record)
    return 0


def _cmd_show(args: argparse.Namespace, config: Config, library: Library) -> int:
    record = library.get(args.id)
    if not record:
        print(f"No video with id {args.id!r}.", file=sys.stderr)
        return 1
    for key in ("title", "uploader", "channel", "platform", "webpage_url",
                "duration", "upload_date", "view_count", "like_count",
                "transcript_source"):
        if record.get(key) is not None:
            value = _fmt_duration(record[key]) if key == "duration" else record[key]
            print(f"{key:>18}: {value}")
    if record.get("tags"):
        print(f"{'tags':>18}: {', '.join(map(str, record['tags']))}")
    if record.get("description"):
        print("\nDescription:\n" + record["description"])
    if record.get("transcript"):
        print("\nTranscript:\n" + record["transcript"])
    return 0


def _cmd_stats(args: argparse.Namespace, config: Config, library: Library) -> int:
    records = library.all()
    by_platform: dict[str, int] = {}
    with_transcript = 0
    for record in records:
        by_platform[record.get("platform", "?")] = by_platform.get(record.get("platform", "?"), 0) + 1
        if record.get("transcript"):
            with_transcript += 1
    print(f"Library: {config.library_dir}")
    print(f"Total videos: {len(records)}")
    print(f"With transcript: {with_transcript}")
    for platform, count in sorted(by_platform.items(), key=lambda kv: -kv[1]):
        print(f"  {platform}: {count}")
    return 0


def _cmd_bot(args: argparse.Namespace, config: Config, library: Library) -> int:
    from .telegram_bot import run_bot

    run_bot(config)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="letmesee",
        description="Absorb videos from Instagram/TikTok/YouTube into a local library.",
    )
    parser.add_argument("--library", help="Override the library directory.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_absorb = sub.add_parser("absorb", help="Fetch and absorb one or more video URLs.")
    p_absorb.add_argument("urls", nargs="+")
    p_absorb.add_argument("--force", action="store_true", help="Re-absorb even if present.")
    p_absorb.set_defaults(func=_cmd_absorb)

    sub.add_parser("list", help="List everything in the library.").set_defaults(func=_cmd_list)

    p_search = sub.add_parser("search", help="Search titles, transcripts and metadata.")
    p_search.add_argument("query", nargs="+")
    p_search.set_defaults(func=_cmd_search)

    p_show = sub.add_parser("show", help="Show full detail for one video id.")
    p_show.add_argument("id")
    p_show.set_defaults(func=_cmd_show)

    sub.add_parser("stats", help="Print a library summary.").set_defaults(func=_cmd_stats)
    sub.add_parser("bot", help="Run the always-on Telegram bot.").set_defaults(func=_cmd_bot)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = Config.load()
    if args.library:
        config.library_dir = type(config.library_dir)(args.library)
    library = Library(config.library_dir)
    return args.func(args, config, library)


if __name__ == "__main__":
    raise SystemExit(main())
