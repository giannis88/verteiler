# verteiler

Distribution kit for publishing one video across several platforms — Reddit,
Discord, TikTok, Instagram, Pinterest — without a scheduler subscription and
without chaining together hosted services.

## The decision

Four backend candidates were evaluated against two written criteria: *what is
productive within two weeks*, and *no subscription, no service chain*. The
matrix — with sourced quotes from each candidate's own documentation, not
estimates — is in [`BACKEND.md`](BACKEND.md). Three were rejected:

- **cogsend** — self-hosted, but covers none of the target platforms
- **socialclaw** — covers all of them, but requires a paid cloud workspace
  (`plan_required`)
- **postiz (cloud)** — covers all of them, but subscription-only
- **postiz (self-hosted)** — documented as fallback, not start: own OAuth apps
  for Meta/YouTube/TikTok "can take weeks"

What shipped is a thin own backend instead: `publish.py` with two small
adapters (Reddit script-app OAuth, Discord webhook) and the existing browser
uploader for the video platforms.

## Design notes

- **Everything that reaches a human goes through a release step first**
  (`freigabe.py`). Nothing posts automatically.
- **Platform rate limits are not raised.** The upload config carries daily caps
  and they stay where they are.
- **Failed verification is documented next to the passing one.** The TikTok
  test upload on 18.10.2026 failed because the cookies were nine months old —
  the runbook records that nothing was uploaded, with the screenshot path as
  evidence, rather than only reporting success.
- **Access was measured, not assumed.** Reddit returns 403 on unauthenticated
  JSON endpoints from this network; reading works via RSS, writing only via
  OAuth. That was checked before the design was fixed.

## Run the tests

```powershell
python -m pytest
```

31 tests. They import the package as `verteiler`, so `pytest.ini` puts the
parent directory on the path — `pytest` runs straight inside a normal clone,
no install step.

## Layout

| File | Role |
|---|---|
| `pack.py` | builds per-target post blocks from the content plan |
| `publish.py` | thin adapters: Reddit OAuth, Discord webhook |
| `freigabe.py` | release gate — nothing sends without it |
| `watch.py` | keyword watch across Reddit, produces digests |
| `targets.yaml` | targets, per-platform rules and angles |
| `state.json` | runtime state (git-ignored) |

Decision record and verification log: [`BACKEND.md`](BACKEND.md) (German).
