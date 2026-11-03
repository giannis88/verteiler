"""Tests fuer publish.py - postet ausschliesslich freigegebene Bloecke.

TDD: erst Test, dann Implementierung. Siehe CLAUDE.md RED-GREEN-REFACTOR.
"""

import json
from datetime import date
from pathlib import Path

from verteiler import publish, freigabe

PACK = [
    {
        "target_id": "reddit_ki_de",
        "platform": "reddit",
        "name": "r/KI_de",
        "status": "draft",
        "title": "Ein KI-Experiment mit acht Sprachmodellen",
        "body": "Acht Sprachmodelle spielen eine Runde Werwolf.",
        "link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "include_link": False,
    },
    {
        "target_id": "discord_eigen",
        "platform": "discord",
        "name": "Leuchtfeuer Community",
        "status": "draft",
        "title": "Werwolf: Acht KI-Agenten, eine Luege - Folge 2",
        "body": "Neue Folge steht. Werwolf: Acht KI-Agenten, eine Luege - Folge 2 ist raus.",
        "link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "include_link": True,
    },
]


def _inputs(tmp_path, freigeben_keys=()):
    """pack + state anlegen; uebergebene Keys werden freigegeben."""
    pack_dir = tmp_path / "packs" / "werwolf-folge-2"
    pack_dir.mkdir(parents=True)
    pack_path = pack_dir / "pack.json"
    pack_path.write_text(json.dumps(PACK, ensure_ascii=False), encoding="utf-8")

    state_path = tmp_path / "state.json"
    freigabe.register_pack(pack_path, state_path, now="2026-10-18T08:00:00")
    for target_id in freigeben_keys:
        freigabe.freigeben(state_path, f"werwolf-folge-2/{target_id}", now="2026-10-18T08:05:00")
    return pack_path, state_path


def test_publish_postet_nur_freigegebene_bloecke(tmp_path):
    """Der zentrale Sicherheits-Satz des Kits: drafts gehen nie raus."""
    _, state_path = _inputs(tmp_path, freigeben_keys=("discord_eigen",))
    seen = []

    results = publish.publish(
        state_path,
        packs_root=tmp_path / "packs",
        log_dir=tmp_path / "logs",
        adapters={"reddit": lambda block: seen.append(block["target_id"]),
                  "discord": lambda block: seen.append(block["target_id"])},
        now="2026-10-18T10:00:00",
        today=date(2026, 10, 18),
    )

    assert seen == ["discord_eigen"], "nur der freigegebene Block darf zum Adapter"
    state = freigabe.load_state(state_path)
    assert state["werwolf-folge-2/reddit_ki_de"]["status"] == "draft", "Draft bleibt unberuehrt"
    assert state["werwolf-folge-2/discord_eigen"]["status"] == "gepostet"
    assert results == [("werwolf-folge-2/discord_eigen", "gepostet")]


def test_publish_loggt_erfolg_mit_zeitstempel(tmp_path):
    """Plan: Logfile mit jedem Versuch, auch Fehlschlaegen - hier der Erfolgsfall."""
    _, state_path = _inputs(tmp_path, freigeben_keys=("discord_eigen",))

    publish.publish(
        state_path,
        packs_root=tmp_path / "packs",
        log_dir=tmp_path / "logs",
        adapters={"discord": lambda block: None},
        now="2026-10-18T10:00:00",
        today=date(2026, 10, 18),
    )

    log = tmp_path / "logs" / "publish-2026-10-18.log"
    assert log.exists(), "Logfile pro Tag fehlt"
    content = log.read_text(encoding="utf-8")
    assert "2026-10-18T10:00:00 OK werwolf-folge-2/discord_eigen" in content


def test_publish_fehlschlag_bleibt_freigegeben_und_landet_im_log(tmp_path):
    """Plan: Logfile mit jedem Versuch, auch Fehlschlaegen. Und: ein Fehlschlag
    darf die Freigabe nicht zerstoeren - der naechste Lauf versucht es erneut."""
    _, state_path = _inputs(tmp_path, freigeben_keys=("discord_eigen",))

    def kaputter_adapter(block):
        raise RuntimeError("Webhook 401")

    results = publish.publish(
        state_path,
        packs_root=tmp_path / "packs",
        log_dir=tmp_path / "logs",
        adapters={"discord": kaputter_adapter},
        now="2026-10-18T10:00:00",
        today=date(2026, 10, 18),
    )

    entry = freigabe.load_state(state_path)["werwolf-folge-2/discord_eigen"]
    assert entry["status"] == "freigegeben", "Fehlschlag darf die Freigabe nicht loeschen"
    assert entry["letzter_fehler"] == "2026-10-18T10:00:00 Webhook 401"
    assert entry["gepostet_am"] is None
    content = (tmp_path / "logs" / "publish-2026-10-18.log").read_text(encoding="utf-8")
    assert "FEHLER werwolf-folge-2/discord_eigen Webhook 401" in content
    assert results == [("werwolf-folge-2/discord_eigen", "fehler")]


class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_discord_adapter_postet_body_und_link_an_webhook(tmp_path):
    """Discord-Blurb: kurzer Text plus Link, an die Webhook-URL, als JSON."""
    calls = []

    def fake_post(url, json=None, **kwargs):
        calls.append((url, json))
        return _FakeResponse()

    adapter = publish.make_discord_adapter(
        "https://discord.com/api/webhooks/123/abc", fake_post
    )
    adapter(PACK[1])

    assert calls[0][0] == "https://discord.com/api/webhooks/123/abc"
    content = calls[0][1]["content"]
    assert PACK[1]["body"] in content, "Blurb muss mitkommen"
    assert PACK[1]["link"] in content, "Link muss mitkommen"


_REDDIT_CONFIG = {
    "client_id": "cid",
    "client_secret": "csec",
    "username": "user",
    "password": "geheim",
    "user_agent": "verteiler/1.0 by user",
}


def test_reddit_adapter_holt_token_und_submittet_den_block():
    """Zwei Requests: OAuth-Token, dann /api/submit mit Titel und Text.
    Ohne include_link bleibt die URL draussen (default der deutschen Subs)."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/v1/access_token"):
            return _FakeResponse(payload={"access_token": "tok123"})
        return _FakeResponse(payload={"json": {"errors": []}})

    adapter = publish.make_reddit_adapter(_REDDIT_CONFIG, fake_post)
    adapter(PACK[0])

    token_call, submit_call = calls
    assert token_call[0] == "https://www.reddit.com/api/v1/access_token"
    assert token_call[1]["data"]["grant_type"] == "password"
    assert token_call[1]["auth"] == ("cid", "csec")

    assert submit_call[0] == "https://oauth.reddit.com/api/submit"
    assert submit_call[1]["headers"]["Authorization"] == "Bearer tok123"
    data = submit_call[1]["data"]
    assert data["sr"] == "KI_de", "r/ vor dem Subreddit-Namen weg"
    assert data["kind"] == "self"
    assert data["title"] == PACK[0]["title"]
    assert data["text"] == PACK[0]["body"], "ohne include_link kein Link im Text"
    assert "utm_" not in data["text"]


def test_reddit_adapter_haengt_link_nur_bei_include_link():
    """r/Finanzen erlaubt Links - der Block sagt es ueber include_link, der
    Adapter parst keine Regeltexte."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/v1/access_token"):
            return _FakeResponse(payload={"access_token": "tok123"})
        return _FakeResponse(payload={"json": {"errors": []}})

    block = dict(PACK[0], include_link=True)
    publish.make_reddit_adapter(_REDDIT_CONFIG, fake_post)(block)

    data = calls[1][1]["data"]
    assert data["text"] == f"{PACK[0]['body']}\n\n{PACK[0]['link']}"


def test_reddit_adapter_wirft_wenn_reddit_ablehnt():
    """Reddits eigene Fehlerliste (z.B. Sub-Regel-Verstoss) muss als Fehler
    durchkommen - publish.py loggt ihn und laesst die Freigabe stehen."""
    def fake_post(url, **kwargs):
        if url.endswith("/api/v1/access_token"):
            return _FakeResponse(payload={"access_token": "tok123"})
        return _FakeResponse(payload={"json": {"errors": [["SUBREDDIT_NOEXIST", "x"]]}})

    adapter = publish.make_reddit_adapter(_REDDIT_CONFIG, fake_post)
    try:
        adapter(PACK[0])
    except RuntimeError as exc:
        assert "Reddit abgelehnt" in str(exc)
    else:
        raise AssertionError("Adapter muss bei Reddit-Fehlern werfen")


def test_build_adapters_nur_fuer_konfigurierte_plattformen():
    """Fehlt der Discord-Webhook oder die Reddit-App, gibt es keinen Adapter -
    solche Bloecke laufen als MANUELL weiter, statt unvorbereitet zu scheitern."""
    http = lambda *args, **kwargs: _FakeResponse()
    secrets = {
        "discord_webhook": "https://discord.com/api/webhooks/1/x",
        "reddit": _REDDIT_CONFIG,
    }
    adapters = publish.build_adapters(secrets, http)
    assert set(adapters) == {"discord", "reddit"}

    assert publish.build_adapters({}, http) == {}, "leeres secrets = keine Adapter"


def test_publish_ohne_adapter_plattform_bleibt_manuell(tmp_path):
    """tiktok/pinterest/comment haben keinen publish-Adapter (siehe BACKEND.md):
    der Block bleibt freigegeben, damit er von Hand nachgetragen werden kann."""
    _, state_path = _inputs(tmp_path, freigeben_keys=("reddit_ki_de",))

    results = publish.publish(
        state_path,
        packs_root=tmp_path / "packs",
        log_dir=tmp_path / "logs",
        adapters={},
        now="2026-10-18T10:00:00",
        today=date(2026, 10, 18),
    )

    entry = freigabe.load_state(state_path)["werwolf-folge-2/reddit_ki_de"]
    assert entry["status"] == "freigegeben", "ohne Adapter wird nicht geupdated"
    content = (tmp_path / "logs" / "publish-2026-10-18.log").read_text(encoding="utf-8")
    assert "MANUELL werwolf-folge-2/reddit_ki_de" in content
    assert results == [("werwolf-folge-2/reddit_ki_de", "manuell")]
