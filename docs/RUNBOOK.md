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
  regression. This is the gate to run before opening a PR that touches anything
  visual.

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

### Known baseline churn

The dashboard renders the snapshot date and a relative freshness label
("Stale · 3d ago", from [dashboard/ui/banners.py](../dashboard/ui/banners.py)).
Both change as the data ages, so a checkout that sat overnight can show diffs in
those regions with no code change behind them. Expect that noise, confirm it is
confined to the date and the freshness chip, and move on. It is not a
regression, and it is not worth chasing.

The bulletin's "Generated:" timestamp moves every minute, which would fail the
gate on every single run, so it is masked. Masks are declared in
[scripts/uxaudit/pages.py](../scripts/uxaudit/pages.py) and kept deliberately
narrow: a mask hides real regressions inside it.

### The diff runs locally, not in CI

`--mode diff` is a pre-PR tool, and the CI workflow deliberately does not run it.
The baselines record whatever data the capturing machine had, and two things make
that non-reproducible:

1. The trend features (KPI deltas, the org sparkline, the movers tables, the What
   Changed comparison) render only when an accumulated history file is available.
   That file currently 404s upstream, so it exists only where a stale copy sits in
   a local `.cache/`, and is absent on every clean checkout.
2. The snapshot is fetched live, so upstream data movement changes the rendering
   with no code change here.

This was found the hard way: baselines captured with a two-month-old local
`history.csv` failed CI immediately, because the runner had no history and so
rendered none of those features. A gate that cannot pass teaches people to ignore
gates.

So: run `--mode diff` yourself before opening a PR, and read the report. The real
fix is to render against a frozen data fixture, at which point the gate becomes
reproducible and can be strict in CI. Tracked as H9 in
[docs/UX_REVIEW_BACKLOG.md](./UX_REVIEW_BACKLOG.md).

If you regenerate baselines, do it from a checkout with no `.cache/` directory,
so what you commit is what a clean environment renders.

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

**This gate is expected to fail today.** There are real live `color-contrast`
and `heading-order` violations in our own CSS and markup. They are fixed by WP-8
and WP-9 in [UX_REMEDIATION_PLAN.md](UX_REMEDIATION_PLAN.md); until then a
non-zero exit from `--mode a11y` is the accurate answer, not a broken harness.

### Licence note

axe-core 4.10.2 is vendored at `scripts/uxaudit/vendor/axe.min.js` under the
Mozilla Public License 2.0. It is an unmodified redistribution. Keep the licence
header at the top of the file intact, and see
[scripts/uxaudit/vendor/README.md](../scripts/uxaudit/vendor/README.md) for the
checksum, the upstream source, and the upgrade procedure.
