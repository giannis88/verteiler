"""Tests fuer pack.py - Content-Pack-Generator.

TDD: erst Test, dann Implementierung. Siehe CLAUDE.md RED-GREEN-REFACTOR.
"""

import json
import re

import yaml

from verteiler.pack import build_pack, main


VIDEO = {
    "title": "Warum Strompreise im Winter explodieren",
    "description": (
        "Der Winterstrompreis haengt an drei Groessen: Gaspreis, "
        "Kaltresiduael und Netzengpaessen im Sueden."
    ),
    "transcript": "Ab Minute zwoehn sehen wir, dass die Grenzkraftwerke den Preis setzen.",
    "thumbnail_path": "out/strompreis/thumb.png",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "topic_tags": ["strompreis", "energie", "winter"],
    "language": "de",
}

TARGETS = [
    {
        "id": "reddit_energie_de",
        "platform": "reddit",
        "name": "r/energie",
        "language": "de",
        "allows_selfpromo": True,
        "rule": "nur im Wochenthread, Flair Pflicht",
        "tone": "sachlich, kein Clickbait",
        "link_policy": "nur im Text, kein Direktlink-Post",
        "angle": "Warum der Preis an der Grenzkraftwerk-Berechnung haengt",
    },
    {
        "id": "discord_leuchtfeuer",
        "platform": "discord",
        "name": "Leuchtfeuer Community",
        "language": "de",
        "channel": "#allgemein",
        "tone": "locker",
        "angle": "Neue Folge steht",
    },
    {
        "id": "tiktok_strom",
        "platform": "tiktok",
        "name": "TikTok Hauptkanal",
        "language": "de",
        "tone": "knapp",
        "angle": "Der Zahlkontrast aus dem Hook",
    },
]


def test_build_pack_erzeugt_block_pro_target():
    blocks = build_pack(VIDEO, TARGETS)
    assert len(blocks) == len(TARGETS)
    assert {b["target_id"] for b in blocks} == {t["id"] for t in TARGETS}


def test_reddit_bloecke_sind_inhaltlich_verschieden():
    """Gleicher Post auf viele Subs in 24h ist ein Reddit-Spam-Flag.

    Zwei Subs mit gleichem Video, aber WINKEL im Ziel muessen unterschiedliche
    Texte ergeben. Zusatz: die Sub-Regel gehoert in eine eigene Notiz, nicht
    in den postbaren Text.
    """
    reddit_a = dict(TARGETS[0])  # Winkel: Grenzkraftwerk
    reddit_b = dict(TARGETS[0], id="reddit_strompreis_frage", name="r/strompreis")
    reddit_b["angle"] = "Frage an die Community: Was zahlt ihr pro Kilowattstunde?"

    blocks = build_pack(VIDEO, [reddit_a, reddit_b])
    bodies = [b.get("body") for b in blocks]

    assert all(bodies), "jeder Reddit-Block braucht einen postbaren Text"
    assert bodies[0] != bodies[1], "identische Texte in 24h = Spam-Flag"
    assert reddit_a["rule"] in blocks[0].get("rule_note", ""), "Regel als Notiz"
    assert reddit_a["rule"] not in bodies[0], "Regel darf nicht im Posttext landen"


def test_reddit_titel_unterschiedlich():
    """Reddit verlangt pro Sub einen eigenen Titel, nicht nur anderen Text."""
    a = dict(TARGETS[0])
    b = dict(TARGETS[0], id="reddit_zwei", name="r/zwei")
    b["angle"] = "Frage an die Community"

    blocks = build_pack(VIDEO, [a, b])
    titles = [blk.get("title") for blk in blocks]

    assert all(titles), "jeder Reddit-Block braucht einen Titel"
    assert titles[0] != titles[1], "identischer Titel ueber Subs hinweg wirkt wie Spam"


def test_discord_blurb_kurz_mit_link_und_channel():
    blocks = build_pack(VIDEO, [TARGETS[1]])
    block = blocks[0]

    assert block["channel"] == "#allgemein", "Ziel-Channel mitfuehren"
    assert block["link"] == VIDEO["video_url"], "Discord-Blurb braucht den Link"
    sentences = [s for s in re.split(r"[.!?]+", block["body"]) if s.strip()]
    assert len(sentences) <= 2, "Discord-Blurb: hoechstens 2 Saetze"


def test_kurzform_caption_und_hashtags():
    """TikTok/Instagram: Caption + 3-5 Hashtags + Vorschlag fuer den Ausschnitt."""
    for target in [t for t in TARGETS if t["platform"] in ("tiktok", "instagram")]:
        block = build_pack(VIDEO, [target])[0]
        assert 3 <= len(block["hashtags"]) <= 5, f"{target['id']}: 3-5 Hashtags"
        assert block["clip_hint"], f"{target['id']}: Ausschnittsvorschlag fehlt"


def test_hashtags_ohne_leerzeichen():
    """Leerzeichen im Tag machen den Hashtag unklappbar - '#agenten protokoll' ist keins."""
    video = dict(VIDEO, topic_tags=["agenten protokoll", "werwolf", "ki experiment"])
    block = build_pack(video, [TARGETS[2]])[0]
    assert block["hashtags"] == ["#agentenprotokoll", "#werwolf", "#kiexperiment"]


def test_pinterest_hat_seo_beschreibung():
    pinterest = {
        "id": "pinterest_energie",
        "platform": "pinterest",
        "name": "Pinterest Energie-Board",
        "language": "de",
        "tone": "sachlich, suchbar",
        "angle": "Infografik Winterstrompreis",
    }
    block = build_pack(VIDEO, [pinterest])[0]
    assert block.get("seo_description"), "Pinterest braucht eine SEO-Beschreibung"


def test_kommentarvorlagen_zwei_bis_drei():
    comment = {
        "id": "yt_kommentare",
        "platform": "comment",
        "name": "Grosse Videos im Themenfeld",
        "language": "de",
        "tone": "helfend, konkret",
        "angle": "Zahlkontrast aus der Folge erklaeren",
    }
    block = build_pack(VIDEO, [comment])[0]
    drafts = block.get("drafts") or []
    assert 2 <= len(drafts) <= 3, "2-3 Kommentar-Entwuerfe erwartet"
    assert all(d.strip() for d in drafts), "kein leerer Entwurf"


def test_keine_tracking_parameter_und_keine_shortener():
    """Tracking-Parameter und URL-Shortener sind Reddit-Spam-Signal."""
    pinterest = {
        "id": "pinterest_check",
        "platform": "pinterest",
        "name": "Board",
        "language": "de",
        "angle": "Infografik",
    }
    comment = {
        "id": "yt_check",
        "platform": "comment",
        "name": "Kommentare",
        "language": "de",
        "angle": "Zahlkontrast erklaeren",
    }
    video = dict(VIDEO, video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ&utm_source=teil")

    for target in TARGETS + [pinterest, comment]:
        block = build_pack(video, [target])[0]
        text = " ".join(
            str(block.get(key) or "")
            for key in ("title", "body", "seo_description", "link", "clip_hint", "caption")
        ) + " ".join(block.get("hashtags") or []) + " ".join(block.get("drafts") or [])
        lowered = text.lower()
        assert "utm_" not in lowered, f"{target['id']}: Tracking-Parameter entfernen"
        for shortener in ("bit.ly", "tinyurl", "goo.gl", "t.co/", "is.gd"):
            assert shortener not in lowered, f"{target['id']}: Shortener {shortener}"


def test_main_schreibt_pack_json_und_pack_md(tmp_path):
    video_path = tmp_path / "video.json"
    video_path.write_text(json.dumps(VIDEO), encoding="utf-8")
    targets_path = tmp_path / "targets.yaml"
    targets_path.write_text(yaml.safe_dump(TARGETS, allow_unicode=True), encoding="utf-8")

    out_dir = main(video_path, targets_path, out_root=tmp_path / "out")

    pack_json = out_dir / "pack.json"
    pack_md = out_dir / "pack.md"
    assert pack_json.exists(), "pack.json fehlt"
    assert pack_md.exists(), "pack.md fehlt"

    blocks = json.loads(pack_json.read_text(encoding="utf-8"))
    assert len(blocks) == len(TARGETS)
    assert all(b["status"] == "draft" for b in blocks), "nichts startet freigegeben"

    markdown = pack_md.read_text(encoding="utf-8")
    assert "r/energie" in markdown, "Markdown soll die Ziele nennen"
    assert VIDEO["title"] in markdown, "Markdown soll den Videotitel zeigen"


def test_include_link_wird_in_block_uebernommen():
    """Die Linkentscheidung steht im Ziel (link_policy), nicht in einer Regel-Analyse.

    Subs mit erlaubter Linkregel bekommen den Link mit, alle anderen nicht -
    pack uebernimmt die Entscheidung als Flag, publish.py schaut nur darauf.
    """
    mit_link = dict(TARGETS[0], include_link=True)
    block = build_pack(VIDEO, [mit_link])[0]
    assert block["include_link"] is True

    block_ohne = build_pack(VIDEO, [TARGETS[0]])[0]
    assert block_ohne["include_link"] is False


def test_slug_ohne_umlauten_und_mit_bindestrich():
    from verteiler.pack import slugify

    assert slugify("Warum Strompreise im Winter explodieren") == "warum-strompreise-im-winter-explodieren"
    assert slugify("Grüße aus München") == "gruesse-aus-muenchen", "Umlaute ins ASCII"
