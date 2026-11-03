"""Reddit-Opportunity-Watcher: findet Threads, in denen eines der Videos die Antwort ist.

Sucht die Keywords aus targets.yaml, behaelt nur Frageformen, ordnet ein Video
zu und schreibt out/digest-YYYY-MM-DD.md. KEIN Auto-Reply - der Digest ist zum
manuellen Bearbeiten. Videos kommen als *.json aus dem videos/-Ordner
(gleiche Schluessel wie bei pack.py: title, description, topic_tags, video_url).
"""

import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

# Frageform-Marker fuer Titel ohne Fragezeichen.
_QUESTION_PATTERNS = (
    r"\bwas ist\b",
    r"\bwarum\b",
    r"\bwieso\b",
    r"\bwie funktioniert\b",
    r"\bkann mir jemand\b",
    r"\bhat jemand\b",
    r"\bwo finde ich\b",
    r"\bwelche[rn]?\b",
    r"\bwas kostet\b",
    r"\bist es normal\b",
)


def load_keywords(targets_path):
    """Alle keywords aus targets.yaml, in Reihenfolge, ohne Duplikate."""
    targets = yaml.safe_load(Path(targets_path).read_text(encoding="utf-8")) or []
    seen, out = set(), []
    for target in targets:
        for keyword in (target or {}).get("keywords") or []:
            keyword = str(keyword).strip()
            key = keyword.lower()
            if keyword and key not in seen:
                seen.add(key)
                out.append(keyword)
    return out


def is_question(text):
    """Frageform erkennen - nur Fragethreads kommen ins Digest."""
    title = (text or "").strip()
    if not title:
        return False
    if title.endswith("?"):
        return True
    return any(
        re.search(pattern, title, re.IGNORECASE) for pattern in _QUESTION_PATTERNS
    )


def load_videos(videos_dir):
    """Liest *.json aus dem videos/-Ordner - jeder Eintrag ein Video."""
    directory = Path(videos_dir)
    videos = []
    if not directory.is_dir():
        return videos
    for path in sorted(directory.glob("*.json")):
        try:
            video = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(video, dict) and video.get("title"):
            videos.append(video)
    return videos


def match_video(post, videos):
    """Video mit den meisten topic_tags im Posttext, sonst None."""
    text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
    best, best_hits = None, 0
    for video in videos:
        hits = 0
        for tag in video.get("topic_tags") or []:
            tag = str(tag).strip().lower()
            if tag and tag in text:
                hits += 1
        if hits > best_hits:
            best, best_hits = video, hits
    return best


def _digest_md(hits):
    lines = [
        "# Reddit-Moeglichkeiten",
        "",
        f"{len(hits)} Frage-Threads, in denen eines der Videos die Antwort ist.",
        "",
    ]
    if not hits:
        lines.append(
            "Keine Treffer. Pruefen ob die Reddit-Suche lieferte "
            "(leere Antwort = Quelle tot, nicht = keine Fragen)."
        )
    for post, video in hits:
        description = (video.get("description") or "").split(".")[0].strip()
        lines += [
            f"## {post.get('title', '')}",
            "",
            f"- Sub: r/{post.get('subreddit', '')} | Score: {post.get('score')} | "
            f"{post.get('date') or 'Datum unbekannt'}",
            f"- Thread: {post.get('url')}",
            f"- Video: {video.get('title')} {video.get('video_url', '')}".rstrip(),
            "- Reply-Gliederung:",
            "  1. Frage in einem Satz direkt beantworten",
            f"  2. Beleg aus dem Video: {description}.",
            "  3. Videolink nur wenn die Sub-Regel das erlaubt (siehe targets.yaml)",
            "",
        ]
    return "\n".join(lines)


def _default_search(topic, from_date, to_date):
    """Suche ueber die keyless-Pipeline der last30days-Bibliothek (kein neuer Client)."""
    scripts = os.path.expanduser(r"~\.claude\skills\last30days\scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from lib import reddit_keyless

    posts = reddit_keyless.search_and_enrich(topic, from_date, to_date, depth="quick")
    return posts or []


def watch(targets_path, videos_dir, out_root="out", search_fn=None, today=None):
    """Sucht, filtert, schreibt den Digest und gibt dessen Pfad zurueck."""
    today = today or date.today()
    search = search_fn or _default_search
    keywords = load_keywords(targets_path)
    videos = load_videos(videos_dir)

    from_date = (today - timedelta(days=1)).isoformat()
    to_date = today.isoformat()

    posts = {}
    for keyword in keywords:
        for post in search(keyword, from_date, to_date) or []:
            url = (post or {}).get("url") or ""
            if url:
                posts.setdefault(url, post)

    hits = []
    for post in posts.values():
        if not is_question(post.get("title", "")):
            continue
        video = match_video(post, videos)
        if video:
            hits.append((post, video))
    hits.sort(key=lambda pair: pair[0].get("score") or 0, reverse=True)

    out_dir = Path(out_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = out_dir / f"digest-{today.isoformat()}.md"
    digest.write_text(_digest_md(hits), encoding="utf-8")
    return digest


if __name__ == "__main__":
    import argparse

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Reddit-Opportunity-Digest bauen")
    parser.add_argument("--targets", default=str(Path(__file__).parent / "targets.yaml"))
    parser.add_argument("--videos", default=str(Path(__file__).parent / "videos"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "out"))
    args = parser.parse_args()
    print(watch(args.targets, args.videos, out_root=args.out))
