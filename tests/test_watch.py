"""Tests fuer watch.py - Reddit-Opportunity-Watcher.

TDD: erst Test, dann Implementierung. Siehe CLAUDE.md RED-GREEN-REFACTOR.
"""

import json
from datetime import date
from pathlib import Path

import yaml

from verteiler import watch

VIDEO = {
    "title": "Warum Strompreise im Winter explodieren",
    "description": (
        "Der Winterstrompreis haengt an drei Groessen: Gaspreis, "
        "Kaltresiduael und Netzengpaessen im Sueden."
    ),
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "topic_tags": ["strompreis", "winter"],
    "language": "de",
}

POSTS = [
    {
        "title": "Warum steigt der Strompreis gerade so?",
        "url": "https://www.reddit.com/r/Finanzen/comments/aaa/wareum/",
        "subreddit": "Finanzen",
        "score": 12,
        "selftext": "siehe strompreis",
        "date": "2026-10-17",
    },
    {
        # Keine Frage -> darf nicht ins Digest.
        "title": "Unser Strompreis-Update vom Montag",
        "url": "https://www.reddit.com/r/Finanzen/comments/bbb/update/",
        "subreddit": "Finanzen",
        "score": 40,
        "selftext": "",
        "date": "2026-10-17",
    },
    {
        "title": "Strompreis: Welcher Anbieter ist am guenstigsten?",
        "url": "https://www.reddit.com/r/Finanzen/comments/ccc/anbieter/",
        "subreddit": "Finanzen",
        "score": 7,
        "selftext": "",
        "date": "2026-10-17",
    },
    {
        # Frage, aber keines der Videos passt -> darf nicht ins Digest.
        "title": "Ist Berlin eigentlich die teuerste Stadt?",
        "url": "https://www.reddit.com/r/de/comments/ddd/berlin/",
        "subreddit": "de",
        "score": 5,
        "selftext": "",
        "date": "2026-10-17",
    },
]


def _inputs(tmp_path):
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        yaml.safe_dump(
            [
                {
                    "id": "r_finanzen",
                    "platform": "reddit",
                    "name": "r/Finanzen",
                    "keywords": ["strompreis", "grenzstrom"],
                },
                {
                    "id": "pinterest_strom",
                    "platform": "pinterest",
                    "name": "Board",
                    "keywords": ["strompreis", "winterstrom"],
                },
            ],
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "strompreis.json").write_text(
        json.dumps(VIDEO, ensure_ascii=False), encoding="utf-8"
    )
    return targets, videos


def test_keywords_aus_targets_ohne_duplikate(tmp_path):
    targets, _ = _inputs(tmp_path)
    assert watch.load_keywords(targets) == ["strompreis", "grenzstrom", "winterstrom"]


def test_frageform_filter_trennt_fragen_von_meldungen():
    assert watch.is_question("Warum steigt der Strompreis?")
    assert watch.is_question("Kann mir jemand den guenstigsten Anbieter nennen?")
    assert watch.is_question("Wie funktioniert die Grenzkraftwerks-Berechnung?")
    assert not watch.is_question("Strompreis aktuell bei 32 Cent")
    assert not watch.is_question("")


def test_digest_listiert_nur_fragen_mit_passendem_video(tmp_path):
    targets, videos = _inputs(tmp_path)
    called = []

    def fake_search(topic, from_date, to_date):
        called.append(topic)
        return POSTS

    digest = watch.watch(
        targets,
        videos,
        out_root=tmp_path / "out",
        search_fn=fake_search,
        today=date(2026, 10, 18),
    )

    assert digest == tmp_path / "out" / "digest-2026-10-18.md"
    text = digest.read_text(encoding="utf-8")
    assert "comments/aaa" in text, "Frage mit passendem Video muss rein"
    assert "comments/ccc" in text, "zweite Frage mit Video muss rein"
    assert "comments/bbb" not in text, "keine Frage -> nicht ins Digest"
    assert "comments/ddd" not in text, "Frage ohne passendes Video -> nicht ins Digest"
    assert VIDEO["title"] in text, "passendes Video nennen"
    assert VIDEO["video_url"] in text, "Videolink nennen"
    assert "Reply-Gliederung" in text, "Reply-Gliederung nennen"
    assert "strompreis" in called, "Keyword aus targets.yaml wird gesucht"


def test_watch_schreibt_nur_den_digest_und_postt_nicht(tmp_path):
    targets, videos = _inputs(tmp_path)

    digest = watch.watch(
        targets,
        videos,
        out_root=tmp_path / "out",
        search_fn=lambda *args: POSTS,
        today=date(2026, 10, 18),
    )

    files = sorted(p.name for p in (tmp_path / "out").rglob("*") if p.is_file())
    assert files == [digest.name], "neben dem Digest darf nichts entstehen"

    src = Path(watch.__file__).read_text(encoding="utf-8")
    for forbidden in (".reply(", ".submit(", "add_comment", "post_comment"):
        assert forbidden not in src, f"watch.py darf nicht posten: {forbidden}"
