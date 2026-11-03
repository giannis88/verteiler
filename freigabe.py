"""Freigabe-Workflow fuer die Pack-Bloecke: draft -> freigegeben -> gepostet.

Zustand liegt in state.json, Key = <pack-slug>/<target_id>. Kein Block verlaesst
"draft" ohne manuelle Freigabe; publish.py liest nur "freigegeben".
"""

import json
from datetime import datetime
from pathlib import Path


def _now(now):
    return now or datetime.now().isoformat(timespec="seconds")


def load_state(state_path):
    path = Path(state_path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state_path, state):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def register_pack(pack_json_path, state_path, now=None):
    pack_path = Path(pack_json_path)
    slug = pack_path.parent.name
    blocks = json.loads(pack_path.read_text(encoding="utf-8"))

    state = load_state(state_path)
    for block in blocks:
        key = f"{slug}/{block['target_id']}"
        if key not in state:
            state[key] = {
                "platform": block["platform"],
                "status": "draft",
                "registriert_am": _now(now),
                "freigegeben_am": None,
                "gepostet_am": None,
                "letzter_fehler": None,
            }
    save_state(state_path, state)
    return state


def freigeben(state_path, key, now=None):
    state = load_state(state_path)
    if key not in state:
        raise ValueError(f"unbekannter Block: {key}")
    if state[key]["status"] != "draft":
        raise ValueError(
            f"{key} hat Status {state[key]['status']} - nur draft kann freigegeben werden"
        )
    state[key]["status"] = "freigegeben"
    state[key]["freigegeben_am"] = _now(now)
    save_state(state_path, state)
    return state[key]


def mark_gepostet(state_path, key, now=None):
    state = load_state(state_path)
    if key not in state:
        raise ValueError(f"unbekannter Block: {key}")
    if state[key]["status"] != "freigegeben":
        raise ValueError(
            f"{key} hat Status {state[key]['status']} - nur freigegeben kann gepostet werden"
        )
    state[key]["status"] = "gepostet"
    state[key]["gepostet_am"] = _now(now)
    state[key]["letzter_fehler"] = None
    save_state(state_path, state)
    return state[key]


def mark_fehler(state_path, key, message, now=None):
    state = load_state(state_path)
    if key not in state:
        raise ValueError(f"unbekannter Block: {key}")
    state[key]["letzter_fehler"] = f"{_now(now)} {message}"
    save_state(state_path, state)
    return state[key]


def freigegebene(state_path):
    state = load_state(state_path)
    return [
        (key, entry)
        for key, entry in state.items()
        if entry["status"] == "freigegeben"
    ]


if __name__ == "__main__":
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    default_state = Path(__file__).parent / "state.json"

    parser = argparse.ArgumentParser(description="Freigabe-Workflow des Verteiler-Kits")
    parser.add_argument("--state", default=str(default_state))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("register", help="pack.json in state.json eintragen").add_argument("pack")
    for name in ("freigeben", "gepostet"):
        sub.add_parser(name).add_argument("key")
    sub.add_parser("status")
    args = parser.parse_args()

    if args.cmd == "register":
        state = register_pack(args.pack, args.state)
        print(f"{len(state)} Bloecke in {args.state}")
    elif args.cmd == "freigeben":
        print(freigeben(args.state, args.key))
    elif args.cmd == "gepostet":
        print(mark_gepostet(args.state, args.key))
    else:
        for key, entry in load_state(args.state).items():
            print(f"{entry['status']:<13} {key}")
