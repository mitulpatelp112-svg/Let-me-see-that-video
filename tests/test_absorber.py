import json

from letmesee.absorber import absorb, build_record, detect_platform, find_urls
from letmesee.config import Config
from letmesee.library import Library


def test_find_urls():
    text = "look at this https://youtu.be/abc123 and https://www.tiktok.com/@x/video/9."
    assert find_urls(text) == [
        "https://youtu.be/abc123",
        "https://www.tiktok.com/@x/video/9",
    ]
    assert find_urls("no links here") == []


def test_detect_platform():
    assert detect_platform("https://www.youtube.com/watch?v=x") == "youtube"
    assert detect_platform("https://youtu.be/x") == "youtube"
    assert detect_platform("https://vm.tiktok.com/abc/") == "tiktok"
    assert detect_platform("https://www.instagram.com/reel/x/") == "instagram"
    assert detect_platform("https://example.org/v") == "example.org"


def test_build_record_normalises_fields():
    info = {"id": "vid1", "title": "T", "uploader": "U",
            "webpage_url": "https://youtu.be/vid1", "duration": 65}
    rec = build_record(info, "https://youtu.be/vid1")
    assert rec["id"] == "vid1"
    assert rec["platform"] == "youtube"
    assert rec["title"] == "T"
    assert rec["duration"] == 65


def _fake_extractor(url):
    return {
        "id": "vid1",
        "title": "How to cook rice",
        "uploader": "ChefBot",
        "webpage_url": url,
        "duration": 120,
        "description": "A short cooking clip.",
        "tags": ["cooking", "rice"],
    }


def test_absorb_stores_record_transcript_and_meta(tmp_path):
    config = Config(library_dir=tmp_path / "lib")
    library = Library(config.library_dir)

    rec = absorb(
        "https://youtu.be/vid1",
        config,
        library,
        extractor=_fake_extractor,
        caption_fetcher=lambda url, d: "step one\nstep two",
        media_downloader=lambda *a, **k: None,
    )

    assert rec["id"] == "vid1"
    assert rec["transcript"] == "step one\nstep two"
    assert rec["transcript_source"] == "captions"
    assert rec["absorbed_at"]

    # Persisted into the index...
    assert library.get("vid1")["title"] == "How to cook rice"
    # ...and on disk as transcript + meta.
    item_dir = library.item_dir("vid1")
    assert (item_dir / "transcript.txt").read_text() == "step one\nstep two"
    meta = json.loads((item_dir / "meta.json").read_text())
    assert meta["uploader"] == "ChefBot"
    # And searchable.
    assert library.search("rice")[0]["id"] == "vid1"


def test_absorb_dedupes_unless_forced(tmp_path):
    config = Config(library_dir=tmp_path / "lib")
    library = Library(config.library_dir)
    common = dict(extractor=_fake_extractor,
                  caption_fetcher=lambda url, d: None,
                  media_downloader=lambda *a, **k: None)

    first = absorb("https://youtu.be/vid1", config, library, **common)
    assert not first.get("already_absorbed")
    second = absorb("https://youtu.be/vid1", config, library, **common)
    assert second.get("already_absorbed")
    forced = absorb("https://youtu.be/vid1", config, library, force=True, **common)
    assert not forced.get("already_absorbed")


def test_absorb_survives_caption_failure(tmp_path):
    config = Config(library_dir=tmp_path / "lib")
    library = Library(config.library_dir)

    def boom(url, d):
        raise RuntimeError("captions exploded")

    rec = absorb("https://youtu.be/vid1", config, library,
                 extractor=_fake_extractor, caption_fetcher=boom,
                 media_downloader=lambda *a, **k: None)
    assert rec["transcript"] is None
    assert library.has("vid1")
