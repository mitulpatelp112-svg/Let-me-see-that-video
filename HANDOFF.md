# Project Handoff — "Let me see that video" 🎬

> A complete record of what this project is, every decision we made, what was
> built, how to use it, and what's left to do. Hand this to anyone (or any
> future Claude session) to pick up exactly where we left off.

**Repo:** `mitulpatelp112-svg/Let-me-see-that-video`
**Working branch:** `claude/affectionate-dirac-pdzyie`
**Pull request:** [#1 — Absorb shared videos into a local, searchable library (CLI + Telegram bot)](https://github.com/mitulpatelp112-svg/Let-me-see-that-video/pull/1) (draft)
**Status:** Implementation complete, 15 tests passing, awaiting decision to mark ready / merge.

---

## 1. The original goal

> "Create a way between a video that I can send from something like Instagram,
> TikTok, or YouTube to some messaging or any form of telecommunication that is
> easily doable from a phone. I can tell Claude to run a command and it will
> retrieve all the data and absorb it and make it usable for future needs. If
> it's fully automated without me even having to give a command and runs
> automatically as soon as I send it, that's even better."

In plain terms:
1. From a phone, share a video link (Instagram / TikTok / YouTube / …).
2. Send it to a messaging channel.
3. The system retrieves all the data, "absorbs" it, and stores it so it's
   usable later (by the user or by Claude).
4. Ideally fully automatic — processed the instant it's sent, no command.

---

## 2. Decisions we made

| Decision | Choice | Why |
| --- | --- | --- |
| **Ingest channel** | **Telegram bot** | Easiest "Share → app" target from a phone; free; supports a 24/7 polling service so it's truly hands-off. |
| **Storage** | **Local library (files + JSON)** | Self-contained, no external account, and the JSON/text is directly readable by Claude for "future needs." |
| **Extraction engine** | **yt-dlp** | Single dependency that handles YouTube, TikTok, Instagram, and [1000s of sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md). |
| **Transcripts** | **Captions first, optional Whisper fallback** | Captions are free/instant where available; Whisper (offline) covers videos without them. |
| **Bot implementation** | **Python stdlib long-polling (no framework)** | Zero extra dependencies; robust and easy to run anywhere. |
| **Parallel sub-agents** | **Not used** | The codebase is small and tightly interdependent (config → library → absorber → bot/CLI). Fan-out would add coordination overhead with no speedup. Reserved for genuinely independent/parallel work. |

---

## 3. How it works

```
 phone ──Share──▶ Telegram bot ──┐
                                 ├──▶ absorber (yt-dlp) ──▶ library/index.json
 you/Claude ──▶ letmesee absorb ─┘    metadata + transcript   library/<id>/{meta.json,transcript.txt}
```

Two ways to drive it:

1. **Fully automatic** — run `letmesee bot` once on an always-on machine. On the
   phone: **Share → Telegram → your bot**. It absorbs the instant the link
   arrives and replies with a confirmation. No command needed.
2. **On demand** — tell Claude *"absorb this: <url>"* and it runs
   `letmesee absorb <url>`.

Every absorbed video becomes a folder under `library/` plus an entry in
`library/index.json` (the search source of truth). Metadata + caption
transcripts are **always** captured; downloading the actual video file and
offline Whisper transcription are opt-in.

---

## 4. What was built (file by file)

```
Let-me-see-that-video/
├── letmesee/
│   ├── __init__.py          # package metadata
│   ├── __main__.py          # enables `python -m letmesee`
│   ├── config.py            # loads settings from env / .env (tiny parser, no deps)
│   ├── library.py           # index.json + per-video folders + full-text search
│   ├── transcript.py        # VTT/SRT caption parsing + optional Whisper transcription
│   ├── absorber.py          # CORE: URL → normalized record; network parts injectable/testable
│   ├── telegram_bot.py      # stdlib long-polling bot (hands-free ingestion)
│   └── cli.py               # absorb / list / search / show / stats / bot
├── tests/
│   ├── test_library.py      # index, persistence, search, corrupt-index tolerance
│   ├── test_absorber.py     # url parsing, platform detection, absorb flow, dedupe
│   └── test_transcript.py   # caption parsing + de-duplication
├── library/.gitkeep         # library lives here (media git-ignored, JSON/text kept)
├── pyproject.toml           # installable; exposes the `letmesee` command
├── requirements.txt         # yt-dlp (+ optional faster-whisper)
├── .env.example             # config template (copy to .env)
├── .gitignore               # ignores .env and heavy media binaries
├── README.md                # user-facing docs
└── HANDOFF.md               # this file
```

### Key design points
- **`absorber.absorb()`** accepts injectable `extractor`, `caption_fetcher`, and
  `media_downloader`, so the entire flow is unit-tested **without network or
  yt-dlp**. Defaults use yt-dlp at runtime.
- **Caption/media/transcription failures never abort absorption** — metadata is
  always saved; extras degrade gracefully.
- **Dedup**: re-absorbing a known video is a no-op unless `--force` is passed.
- **Library is plain JSON + text** so Claude can read and reason over it.

---

## 5. Library data format

```
library/
  index.json                 # { "version": 1, "records": { "<id>": {record} } }
  <id>/
    meta.json                # full record for one video
    transcript.txt           # plain-text transcript (if available)
    <id>.mp4 / .m4a          # media (only if DOWNLOAD_VIDEO/AUDIO enabled; git-ignored)
```

A record contains: `id, url, webpage_url, platform, title, uploader, channel,
description, duration, upload_date, tags, thumbnail, view_count, like_count,
transcript, transcript_source, files, absorbed_at`.

---

## 6. Commands (the "command you tell Claude to run")

```bash
letmesee absorb <url> [<url> ...]   # fetch + absorb one or more videos
letmesee list                       # everything absorbed, newest first
letmesee search <terms>             # full-text over title/transcript/tags/…
letmesee show <id>                  # full metadata + transcript for one video
letmesee stats                      # quick library summary
letmesee bot                        # run the always-on Telegram bot
```
(Equivalently `python -m letmesee <command>` without installing.)

---

## 7. Setup & install

Requires Python 3.9+ and (recommended) `ffmpeg` for media downloads/transcription.

```bash
pip install -r requirements.txt     # or: pip install -e .  (adds `letmesee` to PATH)
cp .env.example .env                # then edit .env
```

### Putting it in `Documents/claude/` on your own computer
The project lives on GitHub, so clone it into its own folder:

**macOS / Linux**
```bash
mkdir -p ~/Documents/claude
cd ~/Documents/claude
git clone -b claude/affectionate-dirac-pdzyie \
  https://github.com/mitulpatelp112-svg/Let-me-see-that-video.git
cd Let-me-see-that-video
python3 -m pip install -r requirements.txt
cp .env.example .env
```

**Windows (PowerShell)**
```powershell
New-Item -ItemType Directory -Force "$HOME\Documents\claude" | Out-Null
Set-Location "$HOME\Documents\claude"
git clone -b claude/affectionate-dirac-pdzyie `
  https://github.com/mitulpatelp112-svg/Let-me-see-that-video.git
Set-Location Let-me-see-that-video
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

> Once PR #1 is merged into `main`, drop the `-b claude/...` flag and clone normally.

---

## 8. Telegram bot setup (for hands-free mode)

1. In Telegram, message **@BotFather**, send `/newbot`, follow the prompts, copy the token.
2. Put it in `.env`: `TELEGRAM_BOT_TOKEN=...`
3. Run it on an always-on machine (laptop, Raspberry Pi, small VPS):
   ```bash
   letmesee bot
   ```
4. Message the bot `/start` once — it replies with **your Telegram user id**.
   Add it to `.env` as `TELEGRAM_ALLOWED_USERS=<id>` and restart, so only you can use it.
5. On the phone: Instagram/TikTok/YouTube → **Share → Telegram → your bot**. Done.

---

## 9. Configuration reference (`.env`)

| Key | Default | Meaning |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | – | Bot token from @BotFather (required for the bot). |
| `TELEGRAM_ALLOWED_USERS` | *(empty = anyone)* | Comma-separated allowed user ids. |
| `LIBRARY_DIR` | `library` | Where data is stored. |
| `DOWNLOAD_VIDEO` | `false` | Also save the full video file. |
| `DOWNLOAD_AUDIO` | `false` | Also save the audio track. |
| `TRANSCRIBE` | `false` | Local Whisper when no captions (needs `faster-whisper`). |
| `WHISPER_MODEL` | `base` | Whisper model size. |
| `POLL_TIMEOUT` | `50` | Telegram long-poll timeout (seconds). |

---

## 10. Testing

```bash
pip install pytest
pytest          # 15 tests, network-free (extraction/download are mocked)
```

---

## 11. Environment notes & limitations

- **Development happened in a temporary cloud sandbox**, not on the user's
  machine. In that sandbox: `yt-dlp` installs fine, but `api.telegram.org` and
  `ffmpeg` were not reachable — so the bot must be run on the user's own
  always-on machine, which is the intended deployment anyway.
- Transcripts depend on the platform offering captions; otherwise enable
  `DOWNLOAD_AUDIO=true` + `TRANSCRIBE=true` with `faster-whisper`.
- Private/age-restricted/login-walled content may require yt-dlp cookies.
- Respect each platform's Terms of Service; only absorb content you're allowed to.

---

## 12. Git / GitHub state

- Repo started **empty** (no commits). We created an initial `main` commit to
  serve as the PR base, then rebased the feature branch on top of it.
- All work is on `claude/affectionate-dirac-pdzyie`, opened as **draft PR #1**.
- **No CI is configured** on the repo yet (0 checks).
- Session is subscribed to PR #1 activity (review comments / CI).

---

## 13. Open questions / next steps

- [ ] **Mark PR #1 ready and merge** into `main`? (Simplifies the clone command.)
- [ ] **Add a CI workflow** (GitHub Actions running `pytest` on push)?
- [ ] Get a Telegram bot token from @BotFather and fill in `.env`.
- [ ] Decide on the always-on host for the bot (laptop / Raspberry Pi / VPS).
- [ ] Optional: enable Whisper transcription for caption-less videos.
- [ ] Optional future ideas: auto-summaries per video, tagging, a "digest"
      command, or mirroring summaries to Notion for phone browsing.

---

*Generated as a session handoff. Update this file as the project evolves.*
