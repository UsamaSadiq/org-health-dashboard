# Frozen data fixture

A verbatim copy of the two `openedx/wg-maintenance` CSVs, captured **2026-09-03**
from the `2026-08-31` upstream snapshot.

| File | Rows | Columns | Snapshot dates |
|---|---|---|---|
| `dashboard_main.csv` | 168 | 119 | `2026-08-31` |
| `dashboard_history.csv` | 680 | 83 | `2026-08-16`, `2026-08-20`, `2026-08-25`, `2026-08-31` |

## What it is for

`scripts/ux_audit.py --mode diff` compares rendered pixels against
`tests/baseline/`. Against live data the comparison is meaningless: a repo added
upstream, a check flipping, a score moving a tenth all repaint the page with no
code change. Pinning the data is what makes a pixel difference mean "someone
changed the UI" rather than "Tuesday happened".

The harness points `DASHBOARD_DATA_FIXTURE` at this directory automatically. See
`dashboard/lib/fixtures.py` for the contract and `scripts/uxaudit/app.py` for
where it is set.

Pinning the data is only half of determinism — the freshness chip, the staleness
banner and the Needing Attention rules are functions of the clock, so the harness
also pins `DASHBOARD_FROZEN_NOW` to `2026-08-31T12:00:00+00:00`, the same UTC day
as the snapshot. See `dashboard/lib/clock.py`.

## These are copies, not edits

Nothing here is hand-tuned, and nothing should be. The value of the fixture is
that it is *what upstream actually served*, so the baselines show the real
dashboard rather than a curated one. If a rendering problem only reproduces on
some other data shape, add a separate fixture directory for it rather than
editing these.

## Refreshing

Rarely, and never to make a red gate go green — a changed fixture changes every
baseline, which hides whatever regression the gate was about to catch. Legitimate
reasons are an upstream schema change or fixture data so old it no longer
exercises the app realistically.

```bash
base=https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards
curl -sSfo tests/fixtures/data/dashboard_main.csv    "$base/dashboard_main.csv"
curl -sSfo tests/fixtures/data/dashboard_history.csv "$base/dashboard_history.csv"

# Re-pin the clock to the new snapshot date in scripts/uxaudit/app.py, then
# regenerate through the container - a host-rendered baseline fails CI on font
# rasterisation alone, and in a commit with no code change to blame it reads as
# a harness bug. See docs/RUNBOOK.md.
scripts/ux_audit_container.sh --mode baseline
```

Commit the refreshed CSVs and the regenerated baselines **in their own commit**,
separate from any code change, and say in the message what moved upstream. A
reviewer needs to be able to tell data churn from a UI change, and a diff that
mixes them is unreviewable.
