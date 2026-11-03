"""Content-Pack-Generator: erzeugt pro Ziel-Community einen Posting-Entwurf.

Pro Ziel ein Block. Alle starten als "draft" - erst eine manuelle Freigabe
setzt sie auf "freigegeben". Die Sub-Regel steht in `rule_note`, nie im
postbaren Text.
"""

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

_UMLAUT = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss"}


def main(video_path, targets_path, out_root="out"):
    """Liest video.json und targets.yaml, schreibt out/<slug>/pack.json + pack.md."""
    video = json.loads(Path(video_path).read_text(encoding="utf-8"))
    targets = yaml.safe_load(Path(targets_path).read_text(encoding="utf-8"))
    blocks = build_pack(video, targets)

    out_dir = Path(out_root) / slugify(video.get("title", "video"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pack.json").write_text(
        json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "pack.md").write_text(_markdown(video, blocks), encoding="utf-8")
    return out_dir


def slugify(text):
    """Pfadfaehiger Slug - Umlaute ins ASCII, Leerzeichen zu Bindestrich."""
    text = str(text)
    for src, dst in _UMLAUT.items():
        text = text.replace(src, dst)
    chars = [
        ch if (ch.isascii() and ch.isalnum()) else "-" for ch in text.lower()
    ]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _markdown(video, blocks):
    lines = [f"# {video.get('title', '')}", "", video.get("description", ""), ""]
    for block in blocks:
        lines.append(f"## {block['name']} ({block['platform']}) - {block['status']}")
        lines.append("")
        if block.get("title"):
            lines.append(f"**Titel:** {block['title']}")
        if block.get("body"):
            lines += ["", block["body"]]
        if block.get("link"):
            lines += ["", f"**Link:** {block['link']}"]
        if block.get("hashtags"):
            lines += ["", "**Hashtags:** " + " ".join(block["hashtags"])]
        if block.get("clip_hint"):
            lines.append(f"**Ausschnitt:** {block['clip_hint']}")
        if block.get("seo_description"):
            lines.append(f"**SEO:** {block['seo_description']}")
        if block.get("channel"):
            lines.append(f"**Channel:** {block['channel']}")
        for i, draft in enumerate(block.get("drafts") or [], 1):
            lines.append(f"**Entwurf {i}:** {draft}")
        if block.get("rule_note"):
            lines.append(f"**Notiz:** {block['rule_note']}")
        lines.append("")
    return "\n".join(lines)


def build_pack(video, targets):
    """Gibt eine Liste von Bloecken zurueck - ein Block pro Ziel."""
    return [_build_block(video, target) for target in targets]


def _build_block(video, target):
    platform = target["platform"]
    return {
        "target_id": target["id"],
        "platform": platform,
        "name": target["name"],
        "language": target.get("language", video.get("language", "")),
        "status": "draft",
        "title": _title(video, target),
        "body": _body(video, target),
        "link": _clean_link(video.get("video_url", "")),
        "include_link": bool(target.get("include_link")),
        "rule_note": _rule_note(target),
        "hashtags": _hashtags(video) if platform in ("tiktok", "instagram") else None,
        "clip_hint": _clip_hint(video, target) if platform in ("tiktok", "instagram") else None,
        "seo_description": _seo_description(video, target) if platform == "pinterest" else None,
        "channel": target.get("channel"),
        "drafts": _comment_drafts(video, target) if platform == "comment" else None,
    }


def _rule_note(target):
    """Regel und Link-Policy als Notiz fuer den Menschen, nicht fuer den Post."""
    notes = []
    if target.get("rule"):
        notes.append(f"Regel: {target['rule']}")
    if target.get("link_policy"):
        notes.append(f"Link: {target['link_policy']}")
    return " | ".join(notes) if notes else None


def _title(video, target):
    """Auf Reddit traegt jeder Sub seinen eigenen Titel - gleiche Titel ueber
    viele Subs hinweg wirken wie Spam. Andere Plattformen behalten den Videotitel.
    """
    angle = (target.get("angle") or "").strip()
    if target["platform"] == "reddit" and angle:
        return angle
    return video.get("title", "")


def _body(video, target):
    platform = target["platform"]
    angle = (target.get("angle") or "").strip()
    description = (video.get("description") or "").strip()
    title = (video.get("title") or "").strip()

    if platform == "discord":
        # Hoechstens zwei Saetze: kurzer Hinweis, dann der Link aus `link`.
        return f"{angle or title}. {title} ist raus."

    parts = (angle, description) if angle else (title, description)
    return "\n\n".join(part for part in parts if part)


def _clean_link(url):
    """Entfernt Tracking-Parameter - utm_ und Co. sind Reddit-Spam-Signal."""
    if not url:
        return ""
    parsed = urlparse(url)
    kept = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_")]
    return urlunparse(parsed._replace(query=urlencode(kept)))


def _hashtags(video):
    """Leerzeichen raus - ein Hashtag ist ein Wort, sonst klappt er nicht."""
    return [
        "#" + "".join(str(tag).split()).lstrip("#")
        for tag in video.get("topic_tags", [])[:5]
    ]


def _clip_hint(video, target):
    angle = (target.get("angle") or "").strip() or video.get("title", "")
    return f"15-30s Ausschnitt: {angle}"


def _seo_description(video, target):
    angle = (target.get("angle") or "").strip()
    return f"{video.get('title', '')} - {angle}. {video.get('description', '')}".strip()


def _comment_drafts(video, target):
    angle = (target.get("angle") or "").strip()
    description = video.get("description", "")
    title = video.get("title", "")
    return [
        f"{angle}. {description}",
        f"Habe ich mir gerade angesehen: {title}. {description}",
        f"Genau der Punkt - {angle}. Passt dazu, was man sonst dazu liest.",
    ]
