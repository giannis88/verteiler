# Backend-Wahl Verteilungs-Kit — Stand 18.10.2026

Entscheidungsgrundlage für Phase 3b/3c. Kriterien aus dem Plan:
**Was ist in 2 Wochen produktiv?** und **"Kein Scheduler-Abo, keine Dienstekette"**.

## Kandidaten-Matrix (belegt, nicht geschätzt)

| Kandidat | Plattformen | Abo nötig? | In 2 Wochen produktiv? | Urteil |
|---|---|---|---|---|
| **cogsend** | nur Mastodon, Bluesky, LinkedIn, Threads, X | nein (self-hosted) | - | **raus**: keines unserer Ziele (Reddit/Discord/TikTok/IG/Pinterest/YT) |
| **socialclaw** | deckt alle Ziele ab | **ja** - Cloud-Workspace mit Pflicht-Abo | - | **raus**: verletzt "kein Scheduler-Abo" |
| **postiz (Cloud)** | deckt alle Ziele ab | **ja** - Subscription (7 Tage Test) | ja | **raus**: Abo |
| **postiz (self-hosted)** | deckt alle Ziele ab | nein | **nein** - eigene OAuth-Apps, Meta/YT/TikTok "kann Wochen dauern" | Fallback, nicht Start |
| **cross_platform_uploader.py** (eigen) | YT, TikTok, IG, FB - kein Reddit/Discord | nein | **ja** - laeuft heute | **drin** fuer Video-Plattformen |
| **eigener duenner Backend** (publish.py) | Reddit + Discord | nein | **ja** - Webhook sofort, Reddit-Script-App sofort | **drin** fuer Community-Plattformen |

Belege:

- **cogsend** (README, 18.10.2026): *"Self-hosted social scheduler for Mastodon, Bluesky,
  LinkedIn, Threads and X"* - Plattformliste deckt kein Ziel.
- **socialclaw** (README, 18.10.2026): nur Cloud: *"the CLI works against a deployed
  SocialClaw workspace via API key auth"* und *"the workspace must also have an active
  trial or paid plan"* - Fehlercode `plan_required` verweist auf getsocialclaw.com/pricing.
- **postiz-app** (README): Cloud = *"Pre-approved apps for every channel, ready to use"*
  aber Subscription; self-hosted = Docker/Postgres/Redis + eigene Apps, dort wörtlich
  *"Meta, YouTube, TikTok can take weeks"*. AGPL-Lizenz beim Selbstbau.
- **postiz-agent** (SKILL.md/QUICK_START.md): braucht laeufige Postiz-Instanz -
  `POSTIZ_API_URL` + `POSTIZ_API_KEY` (oder OAuth device flow), Media erst per
  `postiz upload`, Reddit-Post via `--settings '{"subreddit":[...]}';` TikTok braucht
  zwingend `content_posting_method: DIRECT_POST`. Nützlich nur als CLI obendrauf auf
  einer Postiz-Instanz, nicht als eigenstaendiges Backend.
- **cross_platform_uploader.py** (lokal, G:\Games\MoneyPrinterTurbo\, 2237 Zeilen):
  Browser-Automation mit Cookies (tiktok_cookies.txt), PLATFORM_CONFIGS mit Tageslimits
  (YT 50/Tag, TikTok 4/Tag, IG/FB disabled), Shadowban-Recovery-Phasen. Kein Reddit,
  kein Discord, kein Pinterest. **Limits werden nicht angehoben.**
- **Reddit-Zugang von dieser IP (gemessen 18.10.2026)**: unauthentifizierte `.json`-Endpunkte
  liefern 403, HTML nur die "Welcome to Reddit"-Hülle; **lesen** funktioniert ueber RSS und
  shreddit-svc. **Schreiben** geht nur per OAuth (oauth.reddit.com) - der Write-Pfad ist
  noch ungetestet und wird in Phase 3b/Verifikation 7 geprueft.

## Entscheidung: eigener duennner Backend

Passt zu Plan ("kein Scheduler-Abo, keine Dienstekette") und zum 2-Wochen-Kriterium.
`publish.py` bekommt zwei duenne Adapter, die Video-Plattformen laufen ueber das
vorhandene Upload-Skript:

| Ziel (targets.yaml) | Weg | Warum |
|---|---|---|
| `reddit_*` (3 Subs) | publish.py Reddit-Adapter: Script-App OAuth | Script-Apps werden in prefs/apps sofort erstellt, kein Review; Post nur nach manueller Freigabe |
| `discord_eigen` | publish.py Discord-Adapter: Webhook-POST | kein OAuth, keine App-Registrierung - einfachster Weg ueberhaupt |
| `tiktok_eigen`, `instagram_eigen` | `cross_platform_uploader.py` | laeuft heute, Cookies liegen vor, Tageslimits bleiben |
| `pinterest_strom` | manuell (pack.md als Quelle) | kein der Tools deckt Pinterest ohne Abo/Cloud ab |
| `comment_*` | manuell (pack.md als Quelle) | Fremd-Kommentare brauchen echten Kontext - bewusst Handarbeit |

Ergaenzung: YouTube-Upload lauft wie bisher ueber `werwolf/youtube_hochladen.py`
(gehört nicht zum Push).

## Fallback (dokumentiert, nicht aufgebaut)

Wenn der eigene Weg waechst oder mehr Plattformen dazukommen:
**postiz self-hosted** (Docker-Stack lokal waere nutzbar - Docker 29.1.3, node v24.20.0
sind da), sobald die OAuth-Apps fuer Meta/YT/TikTok durch sind. Bis dahin gilt:
kein Cloud-Abo, kein socialclaw, kein cogsend.

## Test-Status (Verifikation, Stand 18.10.2026)

| Pruefung | Ergebnis |
|---|---|
| Publish-Lauf 1 (18.10. 19:28, ohne secrets.json) | **6x MANUELL** in `logs/publish-2026-10-18.log`, Status aller 6 Bloecke bleiben `freigegeben` - genau das erwartete Verhalten ohne Adapter |
| TikTok-Test (Verifikation 6, 18.10. 19:30) | ** Cookies abgelaufen.** `cross_platform_uploader.py --tiktok-test` mit `short-16.mp4` (1080x1920, 32 s, 4,5 MB): Browser startet, landet auf der Login-Seite (Beleg `debug_screenshots/tiktok_193115_00_upload_page.png`), gibt `"Not logged in - cookies expired"` aus, Exit 0. Der Datei-Input wurde nie erreicht - **es ist nichts hochgeladen.** Cookies `tiktok_cookies.txt` sind vom 25.01.2026 (9 Monate alt). |
| Watch-Digest (Verifikation 5) | Task `Verteiler Watch Digest` lief 18.10. 17:31 mit LastTaskResult 0, Digest geschrieben. 24h-Spiegel morgen 19.10. 07:57. |

**TikTok-Naechster Schritt (User-Schritt):** `python cross_platform_uploader.py
--tiktok-login` in `G:\Games\MoneyPrinterTurbo` startet den Browser fuer manuelles
Login, danach Cookies per "Get cookies.txt"-Extension nach `tiktok_cookies.txt`
exportieren. Danach --tiktok-test wiederholen.

## Offene Aktionen (benötigen User-Eingriff oder Freigabe)

1. **Reddit-Script-App anlegen** (User, prefs/apps) + Token-Datei - Pfade genannt,
   Werte nie ausgegeben.
2. **Discord-Webhook-URL** aus dem Ziel-Channel kopieren.
3. **postiz-agent-Skill installieren**: Klassifikator hat `npx skills add
   gitroomhq/postiz-agent` am 18.10.2026 abgelehnt (externes Code-Integration ohne
   ausdruecklichen Usersatz). Nur installieren, wenn explizit beauftragt - Vergleich
   und BACKEND.md liefen ohne Install.
4. **TikTok-Cookies auffrischen** (`--tiktok-login`, manuell) - Testupload selbst war
   freigegeben und gelaufen, Ergebnis siehe Test-Status; Hochladen kam nur an der
   abgelaufenen Anmeldung.
5. **Erster Reddit-Post + Shadowban-Check** (Verifikation 7) - freigeben getan, Posten
   wartet auf `secrets.json` (User).
