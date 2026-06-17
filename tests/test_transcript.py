from letmesee.transcript import parse_vtt


def test_parse_vtt_strips_headers_timestamps_and_tags():
    vtt = """WEBVTT
Kind: captions
Language: en

1
00:00:00.000 --> 00:00:02.000
<c>Hello</c> there

2
00:00:02.000 --> 00:00:04.000
welcome to <00:00:03.000>the show
"""
    assert parse_vtt(vtt) == "Hello there\nwelcome to the show"


def test_parse_vtt_dedupes_scrolling_captions():
    vtt = """WEBVTT

00:00:00.000 --> 00:00:01.000
hello

00:00:01.000 --> 00:00:02.000
hello

00:00:02.000 --> 00:00:03.000
hello world
"""
    # Consecutive duplicate + substring-of-previous handling.
    assert parse_vtt(vtt) == "hello\nhello world"


def test_parse_vtt_empty():
    assert parse_vtt("WEBVTT\n\n") == ""
