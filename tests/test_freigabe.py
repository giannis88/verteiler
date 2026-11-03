"""Tests fuer freigabe.py - Freigabe-Workflow (draft -> freigegeben -> gepostet).

TDD: erst Test, dann Implementierung. Siehe CLAUDE.md RED-GREEN-REFACTOR.
"""

import json

import pytest

from verteiler import freigabe

PACK = [
    {
        "target_id": "reddit_ki_de",
        "platform": "reddit",
        "status": "draft",
        "title": "Titel A",
        "body": "Text A",
    },
    {
        "target_id": "discord_eigen",
        "platform": "discord",
        "status": "draft",
        "title": "Titel B",
        "body": "Text B",
        "link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    },
]


def _pack_file(tmp_path):
    pack_dir = tmp_path / "packs" / "werwolf-folge-2"
    pack_dir.mkdir(parents=True)
    path = pack_dir / "pack.json"
    path.write_text(json.dumps(PACK, ensure_ascii=False), encoding="utf-8")
    return path


def test_register_pack_registriert_alle_bloecke_als_draft(tmp_path):
    """Jeder Block aus pack.json bekommt einen Eintrag - Status draft, mit Plattform."""
    state_path = tmp_path / "state.json"

    freigabe.register_pack(_pack_file(tmp_path), state_path)

    state = freigabe.load_state(state_path)
    assert set(state) == {
        "werwolf-folge-2/reddit_ki_de",
        "werwolf-folge-2/discord_eigen",
    }
    assert state["werwolf-folge-2/reddit_ki_de"]["status"] == "draft"
    assert state["werwolf-folge-2/reddit_ki_de"]["platform"] == "reddit"
    assert state["werwolf-folge-2/reddit_ki_de"]["registriert_am"]


def test_register_pack_setzt_freigaben_nicht_zurueck(tmp_path):
    """pack.json neu einlesen darf eine erteilte Freigabe nicht loeschen - sonst
    postet publish.py beim naechsten Lauf nie wieder (oder alles doppelt)."""
    state_path = tmp_path / "state.json"
    pack_path = _pack_file(tmp_path)

    freigabe.register_pack(pack_path, state_path, now="2026-10-18T08:00:00")
    freigabe.freigeben(state_path, "werwolf-folge-2/discord_eigen", now="2026-10-18T08:05:00")
    freigabe.register_pack(pack_path, state_path, now="2026-10-18T09:00:00")

    entry = freigabe.load_state(state_path)["werwolf-folge-2/discord_eigen"]
    assert entry["status"] == "freigegeben"
    assert entry["freigegeben_am"] == "2026-10-18T08:05:00"


def test_freigeben_lehnt_unbekannte_und_nicht_draft_bloecke_ab(tmp_path):
    """Doppelte Freigabe und Freigabe aus dem Nichts sind Fehler, keine stille No-ops."""
    state_path = tmp_path / "state.json"
    freigabe.register_pack(_pack_file(tmp_path), state_path, now="2026-10-18T08:00:00")

    with pytest.raises(ValueError, match="unbekannter Block"):
        freigabe.freigeben(state_path, "werwolf-folge-2/gibts_nicht")

    freigabe.freigeben(state_path, "werwolf-folge-2/reddit_ki_de", now="2026-10-18T08:05:00")
    with pytest.raises(ValueError, match="nur draft"):
        freigabe.freigeben(state_path, "werwolf-folge-2/reddit_ki_de", now="2026-10-18T08:10:00")


def test_mark_gepostet_nur_aus_freigegeben(tmp_path):
    """Ein nie freigegebener Block kann nie gepostet sein - publish darf nur
    freigegeben weiterreichen, und der Zustand muss das auch erzwingen."""
    state_path = tmp_path / "state.json"
    freigabe.register_pack(_pack_file(tmp_path), state_path, now="2026-10-18T08:00:00")

    with pytest.raises(ValueError, match="nur freigegeben"):
        freigabe.mark_gepostet(state_path, "werwolf-folge-2/discord_eigen", now="2026-10-18T09:00:00")

    freigabe.freigeben(state_path, "werwolf-folge-2/discord_eigen", now="2026-10-18T09:01:00")
    entry = freigabe.mark_gepostet(state_path, "werwolf-folge-2/discord_eigen", now="2026-10-18T09:02:00")
    assert entry["status"] == "gepostet"
    assert entry["gepostet_am"] == "2026-10-18T09:02:00"
    assert entry["freigegeben_am"] == "2026-10-18T09:01:00"


def test_mark_fehler_laesst_status_unangetastet(tmp_path):
    """Fehlschlag darf die Freigabe nicht zerstoeren - der Block bleibt
    freigegeben und kann erneut versucht werden, mit Meldung im Eintrag."""
    state_path = tmp_path / "state.json"
    freigabe.register_pack(_pack_file(tmp_path), state_path, now="2026-10-18T08:00:00")
    freigabe.freigeben(state_path, "werwolf-folge-2/discord_eigen", now="2026-10-18T08:05:00")

    entry = freigabe.mark_fehler(
        state_path, "werwolf-folge-2/discord_eigen", "Webhook 401", now="2026-10-18T09:00:00"
    )
    assert entry["status"] == "freigegeben"
    assert entry["gepostet_am"] is None
    assert entry["letzter_fehler"] == "2026-10-18T09:00:00 Webhook 401"


def test_freigegebene_listet_nur_freigegebene(tmp_path):
    """publish.py bekommt nur den freigegebenen Teil - drafts duerfen nie dabei sein."""
    state_path = tmp_path / "state.json"
    freigabe.register_pack(_pack_file(tmp_path), state_path, now="2026-10-18T08:00:00")
    freigabe.freigeben(state_path, "werwolf-folge-2/reddit_ki_de", now="2026-10-18T08:05:00")

    keys = [key for key, _ in freigabe.freigegebene(state_path)]
    assert keys == ["werwolf-folge-2/reddit_ki_de"]
