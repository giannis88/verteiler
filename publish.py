"""Postet ausschliesslich freigegebene Pack-Bloecke ueber die mitgegebenen Adapter.

Sicherheitsregeln: liest nur status=="freigegeben" (freigabe.freigegebene), drafts
werden nie angeruehrt. Jeder Versuch - auch Fehlschlag - landet in
logs/publish-YYYY-MM-DD.log und in state.json.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

if __package__ in (None, ""):  # Direkt-Aufruf: Package-Root auf den Pfad
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verteiler import freigabe


def _now(now):
    return now or datetime.now().isoformat(timespec="seconds")


def _log(log_dir, line, now, today):
    today = today or date.today()
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"publish-{today.isoformat()}.log"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{_now(now)} {line}\n")
    return path


def _load_block(packs_root, key):
    slug, target_id = key.split("/", 1)
    pack = json.loads(
        (Path(packs_root) / slug / "pack.json").read_text(encoding="utf-8")
    )
    for block in pack:
        if block["target_id"] == target_id:
            return block
    raise ValueError(f"Block {target_id} fehlt in pack.json von {slug}")


def publish(state_path, packs_root, log_dir, adapters, now=None, today=None):
    """Verarbeitet alle freigegebenen Bloecke, gibt (key, ergebnis) zurueck."""
    results = []
    for key, _entry in freigabe.freigegebene(state_path):
        block = _load_block(packs_root, key)
        adapter = adapters.get(block["platform"])
        if adapter is None:
            _log(log_dir, f"MANUELL {key} ({block['platform']}) - kein Adapter", now, today)
            results.append((key, "manuell"))
            continue
        try:
            adapter(block)
        except Exception as exc:  # Netz-/Plattformfehler duerfen den Batch nicht killen
            freigabe.mark_fehler(state_path, key, str(exc), now=now)
            _log(log_dir, f"FEHLER {key} {exc}", now, today)
            results.append((key, "fehler"))
        else:
            freigabe.mark_gepostet(state_path, key, now=now)
            _log(log_dir, f"OK {key}", now, today)
            results.append((key, "gepostet"))
    return results


def make_discord_adapter(webhook_url, http_post):
    """Webhook-POST: Blurb aus body, Link darunter - Discord kennt kein Titelfeld."""

    def adapter(block):
        content = block["body"]
        if block.get("link"):
            content = f"{content}\n{block['link']}"
        response = http_post(webhook_url, json={"content": content})
        response.raise_for_status()

    return adapter


def build_adapters(secrets, http_post):
    """secrets.json -> Adapter-Map; fehlt ein Block, gibt es den Adapter nicht
    (und publish.py loggt den Block als MANUELL)."""
    adapters = {}
    if secrets.get("discord_webhook"):
        adapters["discord"] = make_discord_adapter(secrets["discord_webhook"], http_post)
    if secrets.get("reddit"):
        adapters["reddit"] = make_reddit_adapter(secrets["reddit"], http_post)
    return adapters


def make_reddit_adapter(config, http_post):
    """Script-App OAuth: Passwort-Grant holen, dann self-Post auf oauth.reddit.com.

    config braucht client_id, client_secret, username, password, user_agent.
    Der Link landet nur im Text, wenn der Block include_link setzt.
    """

    def adapter(block):
        token_response = http_post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(config["client_id"], config["client_secret"]),
            data={
                "grant_type": "password",
                "username": config["username"],
                "password": config["password"],
            },
            headers={"User-Agent": config["user_agent"]},
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]

        text = block["body"]
        if block.get("include_link") and block.get("link"):
            text = f"{text}\n\n{block['link']}"

        submit_response = http_post(
            "https://oauth.reddit.com/api/submit",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": config["user_agent"],
            },
            data={
                "api_type": "json",
                "kind": "self",
                "sr": block["name"].removeprefix("r/"),
                "title": block["title"],
                "text": text,
            },
        )
        submit_response.raise_for_status()
        errors = submit_response.json().get("json", {}).get("errors") or []
        if errors:
            raise RuntimeError(f"Reddit abgelehnt: {errors}")

    return adapter


if __name__ == "__main__":
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    base = Path(__file__).parent
    parser = argparse.ArgumentParser(
        description="Postet freigegebene Bloecke (liest nie draft)"
    )
    parser.add_argument("--state", default=str(base / "state.json"))
    parser.add_argument("--packs", default=str(base / "out"))
    parser.add_argument("--logs", default=str(base / "logs"))
    parser.add_argument("--secrets", default=str(base / "secrets.json"))
    args = parser.parse_args()

    import requests

    secrets_path = Path(args.secrets)
    secrets = (
        json.loads(secrets_path.read_text(encoding="utf-8"))
        if secrets_path.exists()
        else {}
    )
    adapters = build_adapters(secrets, requests.post)

    results = publish(args.state, args.packs, args.logs, adapters)
    if not results:
        print("nichts freigegeben")
    for key, outcome in results:
        print(f"{outcome:<9} {key}")
    if not secrets:
        print("Hinweis: secrets.json fehlt - alle Plattformen laufen als MANUELL")
