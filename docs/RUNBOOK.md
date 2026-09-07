# Runbook

## Upstream outage

1. Verify the CSV URL in [dashboard/config/openedx/data_source.yaml](../dashboard/config/openedx/data_source.yaml).
2. Confirm cached fallback still renders pages.
3. If upstream is down, keep fallback enabled and publish status to users.

## Emergency pinning

1. Update csv_url to a known-good raw CSV snapshot URL.
2. Redeploy and confirm [pages/99_healthz.py](../pages/99_healthz.py) reports status=ok.

## Validation checks

- Run tests: `python -m pytest -q tests`
- Run i18n readiness: `python scripts/check_i18n_readiness.py --strict`

## UX audit harness

[scripts/ux_audit.py](../scripts/ux_audit.py) captures screenshots and runs an
accessibility scan against a real browser. It starts and stops the Streamlit app
itself, so there is no server to launch first and nothing to clean up after.

### Setup

1. `pip install -r requirements-dev.txt`
2. `playwright install chromium`

Step 2 downloads the browser binary and is not optional. Without it every mode
fails at browser launch.

For `--mode diff` and `--mode baseline` you need Docker instead of these two
steps; see "Baselines are Linux-rendered" below.

### Modes

Run all four from the repo root:

- `python scripts/ux_audit.py --mode screenshots` captures every page at every
  viewport into `.ux-audit/current/<viewport>/<page>.png`. Reach for this when
  you want to look at a change, not to gate it.
- `python scripts/ux_audit.py --mode a11y` runs the axe-core scan and exits 1 on
  a blocking violation. See "Accessibility gate" below.
- `python scripts/ux_audit.py --mode baseline` overwrites the committed
  reference PNGs in `tests/baseline/<viewport>/<page>.png`.
- `python scripts/ux_audit.py --mode diff` compares a fresh capture against
  those baselines, writes diff images to `.ux-audit/diff/`, and exits 1 on a
  regression. CI runs this as a blocking gate.

Run the last two through
[scripts/ux_audit_container.sh](../scripts/ux_audit_container.sh) rather than
directly — see "Baselines are Linux-rendered" below.

Everything under `.ux-audit/` is transient and gitignored. Everything under
`tests/baseline/` is tracked.

### Baseline review workflow

Baselines are reviewed like code. A diff to `tests/baseline/` in a pull request
is a claim that the visual change is intentional, and a reviewer is expected to
open the images and agree with that claim.

1. Make the change, then run `--mode diff`.
2. If it fails, open the diff images and work out why.
3. Only once the change is understood and wanted, run `--mode baseline` and
   commit the updated PNGs alongside the code change that justifies them.

Never regenerate baselines to turn a red gate green. That converts a caught
regression into a committed one, and the commit will read as if someone approved
it. Investigate first, always.

### What makes the diff reproducible

Rendering is a function of the code, and of nothing else. Three inputs that would
otherwise move on their own are pinned:

| Input | Pinned by | Without it |
|---|---|---|
| The two upstream CSVs | `tests/fixtures/data/`, via `DASHBOARD_DATA_FIXTURE` | Upstream churn — a repo added, a check flipping, a score moving a tenth — repaints the page with no code change |
| The clock | `DASHBOARD_FROZEN_NOW`, via [dashboard/lib/clock.py](../dashboard/lib/clock.py) | The freshness chip ("9d ago"), the staleness banner and the Needing Attention rules re-render every day |
| Set iteration order | `PYTHONHASHSEED=0` | Any page building a list from a set shuffles between runs |
| The build's commit | `GITHUB_SHA`, overwritten by the harness | The bulletin's "Commit: &lt;sha&gt;" provenance line changes on every commit, and is absent outside CI |
| Tie order in every ranking | [dashboard/lib/ordering.py](../dashboard/lib/ordering.py) | Repos on equal scores permute between machines, so "Top 5" is a different five |

[scripts/uxaudit/app.py](../scripts/uxaudit/app.py) sets all three for the
Streamlit child process, so every mode gets them without you doing anything. To
render live data instead — reproducing a bug that only appears on current
upstream data — set `DASHBOARD_DATA_FIXTURE=` to an explicit empty value. A
baseline captured that way is not comparable with the committed ones.

Nothing is masked, and that is the goal rather than a coincidence. The bulletin's
"Generated:" timestamp used to need a mask because it read the wall clock at
render time; pinning the clock removed the need. A mask is a blind spot — it
hides any regression inside it, and its coordinates rot silently against layout
change — so when something renders non-deterministically, pin the value rather
than mask the pixels. `MASKS` in
[scripts/uxaudit/pages.py](../scripts/uxaudit/pages.py) is where an entry would
go if one were ever genuinely outside our control.

### Baselines are Linux-rendered — use the container

Text rasterisation differs between operating systems by far more than the gate's
tolerance. A baseline captured on macOS and diffed on a Linux runner reports
1.2–10.6% of pixels changed, with whole-page bounding boxes and page heights
shifting 25px from line-wrap differences. No tolerance absorbs that while still
catching a clipped axis label.

So there is one reference environment — the pinned
`mcr.microsoft.com/playwright/python` image — and both CI and contributors render
in it:

```bash
scripts/ux_audit_container.sh --mode diff
scripts/ux_audit_container.sh --mode baseline
```

That script takes the same arguments as `ux_audit.py` and needs only Docker
running. The first run installs dependencies into a cached volume (~40s); later
runs skip it, and a changed pin in `requirements*.txt` reinstalls automatically.

Running `ux_audit.py` directly on your machine is still the right thing for
`--mode a11y` and `--mode screenshots` — neither compares against a committed
baseline, so host rendering is fine. Only `--mode diff` and `--mode baseline`
need the container.

The image tag appears in three places that must agree: the `container:` key in
`.github/workflows/ux-audit.yml`, `IMAGE` in
[scripts/ux_audit_container.sh](../scripts/ux_audit_container.sh), and the
`playwright` pin in [requirements-dev.txt](../requirements-dev.txt).

### Refreshing the data fixture

Rarely, and never to make a red gate green. See
[tests/fixtures/data/README.md](../tests/fixtures/data/README.md) for the
procedure and for why a fixture refresh belongs in its own commit, separate from
any code change.

### After a Streamlit upgrade

Run `--mode diff` immediately and expect sidebar and chart styling breakage.
`streamlit` is pinned exactly in [requirements.txt](../requirements.txt) for this
reason, with the full explanation in the comment above the pin: the CSS in
[dashboard/ui/theme.py](../dashboard/ui/theme.py) targets Streamlit's generated
`st-emotion-cache-*` classes and `data-testid` selectors, which are free to move
in a minor release. The failure mode is silent, so the diff is the only warning
you get.

### Accessibility gate

`--mode a11y` splits axe-core findings in two:

- Violations in markup and CSS we own are blocking and fail the run.
- Violations baked into Streamlit's own DOM are reported but accepted, through a
  per-rule allowlist documented in
  [scripts/uxaudit/a11y.py](../scripts/uxaudit/a11y.py).

The allowlist is per-rule on purpose rather than a severity threshold. A
threshold set high enough to tolerate Streamlit's own DOM would also silence our
serious `color-contrast` failures, which is exactly what the gate exists to
catch. Adding a rule to the allowlist is a deliberate, reviewable act.

The gate passes as of WP-9, which fixed the `color-contrast` and `heading-order`
violations in our own CSS and markup. A non-zero exit now means a real
regression, not a known-bad baseline.

### Licence note

axe-core 4.10.2 is vendored at `scripts/uxaudit/vendor/axe.min.js` under the
Mozilla Public License 2.0. It is an unmodified redistribution. Keep the licence
header at the top of the file intact, and see
[scripts/uxaudit/vendor/README.md](../scripts/uxaudit/vendor/README.md) for the
checksum, the upstream source, and the upgrade procedure.
