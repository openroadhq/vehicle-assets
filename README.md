# Open Road vehicle assets

Static vehicle profile images served via CDN. Slug: `v1/<make>/<model>.webp` (lowercase, spaces to dashes). `manifest.json` lists available slugs.

## Daily vehicle requests

`tools/requests-daily.sh` reads both Firestore request collections, fetches
`origin/main`, and creates a local `renders-YYYY-MM-DD` branch and fresh dated
worktree. It writes a dated delta under `~/Projects/506-2026-09-12/vehicle-requests`
and a self-contained phone review plus contact sheet under
`~/Desktop/Galahad/vault/projects/vehicle-requests-YYYY-MM-DD/`.

Only unseen request slugs are processed. A durable state file and lock in the
Git common directory prevent overlapping runs, repeated renders, and duplicate
Telegram messages. Existing aliases are never changed or removed. Known body
exceptions live in `tools/requests/curated.json`; ambiguous models are listed as
unresolved. Automatic image checks cover alpha, framing and clipping; every daily
image remains visibly marked as awaiting human visual review until inspected.

Generation uses the existing subscription generator and BiRefNet cutout. The
shared Codex weekly meter is read from Galahad's usage mirror, falling back to the
local OpenUsage API. Every attempt, including the one allowed retry, checks the
meter and stops at 85% used or unknown/stale usage. This is not an image-specific
quota. Cutouts wait while Xcode builds are active. Dependencies are Python with
`google-cloud-firestore` and Pillow, the existing `chatgpt-imagegen`, `cwebp`, ADC
read access, and the existing rembg venv (or the generator's venv setup).

Normal usage: `tools/requests-daily.sh`. To prepare without generation or a
message, add `--prepare-only`. Use `--no-notify` to withhold Telegram during local
verification. `--use-export` explicitly resumes from that day's existing raw
snapshot. `--worktree PATH` resumes an existing branch for the same date.
Configuration paths can be overridden with `--repo`, `--deltas`, `--reviews`, and
`--state-dir`; `REQUESTS_PYTHON` selects the Python interpreter.

When there is new work, the routine sends one review HTML document through
Galahad's existing Telegram sender. Raw user identifiers stay in permission-600
raw exports, outside this repository. Nothing is scheduled, committed, pushed,
merged, or CDN-purged by the routine. The release chat installs the schedule and
reviews all images before publishing. GitHub Pages is the primary host; jsDelivr's
50 MB package limit makes it unreliable for newly added assets.
