# Let me see that video 🎬

Send a video link from your phone — from **Instagram, TikTok, YouTube** (and
[anything yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)) —
and have it **absorbed into a local, searchable library**: title, author,
description, tags, and the **transcript**. Then ask Claude (or use the CLI) to
search and reuse it later.

Two ways to drive it:

1. **Fully automatic** — run the Telegram bot once. From your phone you just
   tap **Share → Telegram → your bot**, and it absorbs the video the moment it
   arrives. No command needed.
2. **On demand** — tell Claude *"absorb this: <url>"* and it runs one command.

---

## How it works

```
 phone  ──Share──▶  Telegram bot  ──┐
                                    ├──▶  absorber (yt-dlp)  ──▶  library/
 you/Claude ──▶  letmesee absorb ──┘        metadata + transcript        index.json
                                                                         <id>/meta.json
                                                                         <id>/transcript.txt
```

Every absorbed video becomes a folder under `library/` plus an entry in
`library/index.json`, which is what `search` reads. Metadata and the transcript
(from the video's captions) are always captured; downloading the actual video
file or running offline transcription are opt-in.

---

## Setup

Requires Python 3.9+ and [ffmpeg](https://ffmpeg.org/) (recommended, for media
downloads/transcription).

```bash
pip install -r requirements.txt          # installs yt-dlp
# or, to get the `letmesee` command on your PATH:
pip install -e .

cp .env.example .env                      # then edit .env
```

---

## Option 1 — Fully automatic via Telegram (recommended)

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the token.
2. Put it in `.env` as `TELEGRAM_BOT_TOKEN=...`.
3. Start the bot once, somewhere always-on (your laptop, a Raspberry Pi, a
   small VPS):

   ```bash
   letmesee bot          # or: python -m letmesee bot
   ```

4. Message your bot `/start` once — it replies with **your Telegram user id**.
   Paste that into `.env` as `TELEGRAM_ALLOWED_USERS=<id>` and restart, so only
   you can use it.
5. On your phone: open Instagram/TikTok/YouTube → **Share → Telegram → your
   bot**. Done. It absorbs automatically and replies with a confirmation.

---

## Option 2 — On demand (the command you tell Claude to run)

```bash
letmesee absorb https://www.youtube.com/watch?v=XXXX
letmesee absorb <url1> <url2> ...      # several at once
```

You can literally say to Claude: *"absorb https://… into the library"* and it
runs the command above.

---

## Using the library

```bash
letmesee list                 # everything you've absorbed, newest first
letmesee search onion pasta   # full-text over titles, transcripts, tags, …
letmesee show <id>            # full metadata + transcript for one video
letmesee stats                # quick summary
```

Because the library is just JSON + text files on disk, Claude can read and
reason over it directly for "future needs" — summarise, cross-reference, pull
quotes from transcripts, etc.

---

## Configuration (`.env`)

| Key | Default | Meaning |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | – | Bot token from @BotFather (required for the bot). |
| `TELEGRAM_ALLOWED_USERS` | *(empty = anyone)* | Comma-separated user ids allowed to use the bot. |
| `LIBRARY_DIR` | `library` | Where data is stored. |
| `DOWNLOAD_VIDEO` | `false` | Also save the full video file. |
| `DOWNLOAD_AUDIO` | `false` | Also save the audio track. |
| `TRANSCRIBE` | `false` | Run local Whisper when a video has no captions (needs `faster-whisper`). |
| `WHISPER_MODEL` | `base` | Whisper model size. |

Metadata and caption-based transcripts are absorbed regardless of these flags;
the flags only control the heavier extras.

---

## Notes & limits

- Transcripts come from the platform's captions when available (most YouTube
  videos, many others). For videos with none, set `DOWNLOAD_AUDIO=true` and
  `TRANSCRIBE=true` with `faster-whisper` installed to transcribe locally.
- Private/age-restricted/login-walled content may need yt-dlp cookies — see the
  [yt-dlp docs](https://github.com/yt-dlp/yt-dlp#filesystem-options).
- Respect each platform's Terms of Service and only absorb content you're
  allowed to.

---

## Development

```bash
pip install pytest
pytest            # network-free: extraction/download are mocked in tests
```
