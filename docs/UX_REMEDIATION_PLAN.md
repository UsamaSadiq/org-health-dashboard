# UX Remediation Plan

Execution plan for the 164 findings in [`UX_REVIEW_BACKLOG.md`](./UX_REVIEW_BACKLOG.md).
Backlog IDs (`A1`, `D32`, …) are used throughout; this document does not restate them.

**Status:** proposed, not approved. Effort figures are rough dev-days for one
engineer familiar with the codebase, and are for relative sizing only.

---

## 1. Strategy

### 1.1 Six operating principles

| # | Principle | What it changes |
|---|---|---|
| 1 | **Separate "our clock" from "someone else's clock"** | ~25% of the highest-value work is a pipeline change, a curation decision, or content authoring. Those become requests-in-flight on day 1, running parallel to all code work. |
| 2 | **Fix by deletion and disclosure before fixing by building** | The credibility cluster has cheap answers. Wave 1 ships almost no new UI and moves the trust needle further than Wave 4. |
| 3 | **Build the verification harness before touching code** | Clipped axes, colliding pills, and contrast failures are invisible to unit tests. Promote the audit scripts to `scripts/ux_audit.py` first so every wave is provable. |
| 4 | **Extract primitives, then rewrite pages** | One `repo_table()` closes ~12 findings. Page-first means writing that logic seven times and deleting it. |
| 5 | **Teach the scoring engine to express uncertainty** | One change in `scoring.py` (distinguish absent / blank / real) converts B3, B7, B10, D15, D18 from separate problems into presentation choices. |
| 6 | **Sequence page work by persona, not page number** | If Wave 4 slips, the WG-lead pages are already done. |

### 1.2 What "done" means for each item

Every work package below has explicit acceptance criteria. Three classes:

- **Behavioural** — verifiable by a test in `tests/`.
- **Visual** — verifiable by a screenshot diff from `scripts/ux_audit.py`.
- **Editorial** — needs a human to read the copy and agree. Flagged `[review]`.

An item is not done because the code changed. It is done when its class of
evidence exists.

### 1.3 Delivery model

- One branch and PR per **work package** (WP), not per wave and not per item.
  Packages are sized to be reviewable in one sitting (≤ ~400 changed lines).
- Each PR states the backlog IDs it closes in the `## Description` section.
- Waves 0–3 are strictly sequential. Waves 4–8 can overlap once Wave 3 lands.
- `main` stays deployable throughout. No long-lived feature branch.
- Feature-flag anything user-visible that spans more than one PR.

### 1.4 Risks

| Risk | Mitigation |
|---|---|
| Wave 0 upstream asks stall, blocking Waves 1 and 4 | Ship the *disclosure* half of each dependent item regardless (say "trend data unavailable" even if history never arrives). Never let an upstream dependency block honesty. |
| `theme.py` CSS overrides break on a Streamlit upgrade | WP-1 pins the Streamlit version; WP-2's screenshot baseline catches breakage on the next bump. See also E8 — the strategic answer may be to stop fighting it. |
| Scoring changes silently move every repo's grade | WP-6 requires a before/after grade-distribution diff in the PR body. Any change to a published grade must be intentional and stated. |
| Wave 4 grows without bound | Each page is one WP with a fixed item list. New findings go to the backlog, not into the open PR. |

---

## 2. Wave 0 — Upstream asks and decisions (start day 1)

Not code. Each item is a request or a decision with multi-week lead time, and
each gates later work. **Owner** is who must act, not who files the request.

### WP-0A · Collect the four missing activity metrics
**Closes** L1 · **Unblocks** B1, B3, A5, D9, D15 · **Owner** pipeline maintainers · **Effort** n/a (external)

The snapshot must gain four columns. Exact names are already contracted by
`dashboard/config/openedx/scoring.yaml`:

| Column | Type | Metric | Weight |
|---|---|---|---|
| `github.median_pr_response_seconds` | integer seconds | `pr_response_time` | 0.15 |
| `github.pr_closure_ratio_90d` | float 0–1 | `pr_closure_ratio` | 0.15 |
| `github.release_count_12mo` | integer | `release_frequency` | 0.10 |
| `github.contributor_count_90d` | integer | `contributor_absence_factor` | 0.10 |

**Deliverable:** a request to the `openedx/wg-maintenance` pipeline owners
containing this table, the thresholds from `scoring.yaml`, and the statement that
50% of the composite score is currently a constant without them.

**Acceptance:** the four columns appear in `dashboard_main.csv`, and
`score_coverage` on Overview reads 100%.

**Interim:** do not wait. WP-5 discloses the gap.

---

### WP-0B · Publish the history file
**Closes** A3 · **Unblocks** A4, D5, D16, D25, D40–D45, all KPI deltas · **Owner** pipeline maintainers · **Effort** n/a (external)

`https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_history.csv`
returns 404 on every load. `dashboard/lib/trends.py` already expects the format:
one accumulated CSV, one row-block per snapshot, each row carrying its own
`TIMESTAMP`, 30-day retention (`data_source.yaml: history_days: 30`).

**Acceptance:** the URL returns 200; `load_history(days=30)` yields ≥ 2 snapshots
in a clean checkout with no `.cache/` directory.

**Interim:** WP-5 replaces silent failure with an explicit message.

---

### WP-0C · Populate `tiers.yaml`
**Closes** D34 · **Unblocks** D32, D33, D37, A2 · **Owner** Maintenance WG · **Effort** n/a (curation)

Currently 4 of 171 repos are classified (2 critical, 2 important, 0 standard), so
every tier-scoped attention rule is effectively off.

**Deliverable:** a WG decision on tier definitions and an initial classification.
Realistic target: 15–30 critical, 40–60 important, remainder standard.

**Acceptance:** ≥ 80% of non-archived repos have a non-default tier, and
Needing Attention returns > 30 rows at `tier=all`.

---

### WP-0D · Write the 63 missing check descriptions
**Closes** B5 · **Unblocks** D18, D47, D49, I10 · **Owner** WG + maintainers · **Effort** ~3 days of authoring, parallelisable

Add to `dashboard/config/openedx/check_descriptions.yaml`, per check:

```yaml
checks:
  readme.security:
    title: "Security contact in README"          # human title  → D18, D47
    description: "…what the check inspects…"     # → Catalog body
    why_it_matters: "…consequence of failing…"   # NEW field    → I10
    chaoss_metric: "…"                           # optional
    scorecard_check: "…"                         # optional
    source_url: "…"                              # optional
```

`why_it_matters` is a new field; WP-4 extends
`dashboard/config/schemas/check_descriptions.schema.json` to accept it.

**Acceptance:** Checks Catalog's "Missing descriptions" tile reads 0, and
`tests/test_config_schemas.py` asserts every snapshot check column has a title.

---

### WP-0E · Decide the scoring scope
**Closes** B4 · **Unblocks** D49, B6 · **Owner** WG + project lead · **Effort** 1 meeting

Only 3 of 76 collected checks feed the score. Pick one:

- **(a) Widen** — promote more structural checks into `scoring.yaml` with weights.
- **(b) Reframe** — keep scoring narrow, and relabel the other 73 as
  "informational" in the UI so the ratio stops reading as an oversight.
- **(c) Both** — widen modestly, reframe the remainder.

**Acceptance:** a written decision in this repo. If (a), a `scoring.yaml` v2.1
with the new weights and a stated grade-distribution impact.

---

### WP-0F · Sign off the provisional thresholds
**Closes** B8 · **Unblocks** B1, B6 · **Owner** Maintenance WG · **Effort** 1 meeting

Four activity metrics carry `# Provisional thresholds (pending maintainer
sign-off)` in `scoring.yaml` but are presented in the UI as settled.

**Acceptance:** either the comments are removed after sign-off, or WP-5 surfaces
provisional status in the UI.

---

### WP-0G · Decide the public framing of low performers
**Closes** K5 · **Unblocks** D3, D12, K6 · **Owner** WG + community · **Effort** 1 discussion

"Bottom 5" names volunteer-maintained repos publicly. Options: keep as-is;
rename to opportunity framing; show only above a data-coverage threshold; or
restrict to authenticated/maintainer views.

**Acceptance:** a written decision. It determines copy in WP-12 and WP-14.

---

## 3. Wave 1 — Foundation and honesty

### WP-1 · Verification harness
**Closes** nothing directly · **Enables** all visual acceptance criteria · **Effort** 1.5 days

Create `scripts/ux_audit.py`, promoting the throwaway review scripts:

```
scripts/ux_audit.py --mode screenshots   # all pages, 1440px + 390px, full scroll
scripts/ux_audit.py --mode a11y          # axe-core 4.10, fail on serious/critical
scripts/ux_audit.py --mode baseline      # write reference PNGs
scripts/ux_audit.py --mode diff          # compare against baseline, emit report
```

Implementation notes:
- Streamlit scrolls `section[data-testid="stMain"]`, **not** the document, so
  `full_page=True` silently captures only the first viewport. Scroll-and-stitch.
- Allow a per-page settle delay; charts and cached fetches need ~6s cold.
- Pin `playwright` and the axe-core version in `requirements-dev.txt`.
- Baseline PNGs go in `tests/baseline/` and are reviewed like code.

**Also in this WP:** pin the Streamlit version in `requirements.txt`. The CSS in
`theme.py` depends on `st-emotion-cache-*` internals and already carries four
defensive comments; an unpinned minor bump can break the sidebar silently.

**Readiness gating (added after the first run).** `settle_seconds` alone is not a
correctness guarantee. A narrowed run such as `--pages repo_detail` starts a cold
server and navigates straight to a sub-page, which triggers A0 — the entry script
is bypassed, so the capture is of an *unstyled* page with the wrong nav. Measured:
sidebar pixel `(255,255,255)` instead of the dark teal, stitched height 2947px vs
the styled 2912px, and the run still exited 0. Silently baselining a broken render
is the one failure mode that makes a visual gate actively harmful.

Both `capture_all` and `audit_all` must therefore:
1. Load `/` first to establish a session before visiting any sub-page.
2. Poll for a readiness marker (the `--color-primary` custom property from
   `apply_base_style`) rather than sleeping a fixed interval.
3. **Fail loudly** if the marker is absent when the settle budget expires.

Step 1 is a workaround for A0 and should be *kept* after WP-2A fixes the root
cause, because step 3 is what stops a future regression being silently recorded.

**Acceptance:** `--mode a11y` exits non-zero today (it will — F1/F2/F3 are live),
`--mode diff` reports zero diffs on an unchanged checkout, and
`--mode screenshots --pages repo_detail` produces a *styled* capture or fails.

---

### WP-2A · Entry-script bypass and feature-flag enforcement
**Closes** A0, A0b, A14 · **Effort** 1 day · **Runs before every other code package**

Found by the WP-1 harness on its first run; not in the original 164 findings.

Streamlit's automatic `pages/` discovery serves any non-root URL *before*
`streamlit_app.py` executes. That file holds both `apply_base_style()` and the
`st.navigation()` flag gating, so a direct deep link gets neither. Verified on a
cold server: base CSS absent after 45s and never recovering, while `/` styles in
0.9s; and `GET /sql` serving a working query textarea and Run button despite
`enable_sql_page: false`.

| Item | Change |
|---|---|
| **A0** | Shared per-page init helper (e.g. `dashboard/ui.page_init()`) that calls `apply_base_style()` and `hydrate_from_query_params()`. Every module in `pages/` calls it first. `st.markdown` output from the entry script cannot be relied on to reach a deep-linked page. |
| **A0b** | Enforce flags *inside* each gated page — `pages/07_sql.py`, `08_badges.py`, `10_cards.py` each check their own flag and render a "not enabled" stub otherwise. Nav-level gating is presentation, not access control. Decide separately whether `99_healthz.py` should be reachable (it probably should, but deliberately). |
| **A14** | `sorted()` the unavailable-metrics set in `pages/02_repo_detail.py:99-100`. Lands here because non-deterministic label order also poisons screenshot baselines. |

**Acceptance:** [behavioural] a test asserts each flag-gated page module refuses to
render its feature when its flag is false, independent of nav. [visual] a
cold-server `--mode screenshots --pages repo_detail` capture is styled and
byte-comparable to the same page reached via `/`.

**Ordering note:** this precedes WP-2 through WP-6 because it is the difference
between measuring the real app and measuring a broken render of it.

---

### WP-2 · Dark mode: real, or gone
**Closes** A1 · **Effort** 1.5 days

`apply_base_style()` injects `<script>document.documentElement.setAttribute(...)`
via `st.markdown`. Browsers do not execute scripts inserted as innerHTML, so
`data-theme` is never set and the entire `[data-theme="dark"]` block is dead.

**Recommended fix — no JavaScript.** Emit different token values instead of
toggling an attribute:

```python
# dashboard/ui/theme.py
LIGHT_TOKENS = {"page": "#F1F5F9", "surface_alt": "#FFFFFF", "text": "#0F172A", ...}
DARK_TOKENS  = {"page": "#0F172A", "surface_alt": "#1E293B", "text": "#F1F5F9", ...}

def apply_base_style() -> None:
    dark = bool(st.session_state.get("theme_dark", False))
    tokens = DARK_TOKENS if dark else LIGHT_TOKENS
    register_plotly_template(dark=dark)          # template must follow the theme
    st.markdown(_base_css(tokens), unsafe_allow_html=True)
```

Then:
- Delete `_DARK_TOGGLE_JS` and both `<script>` injections.
- Delete the `[data-theme="dark"]` CSS block; tokens replace it.
- `register_plotly_template(dark)` — `paper_bgcolor`, `plot_bgcolor`, font, and
  grid colours must switch, or every chart stays light-on-dark.
- Audit the ~30 hardcoded hex values in `kpi.py` and `charts.py`; they bypass
  tokens and will not follow the theme. This is most of the work.
- Remove `base = "light"` from `.streamlit/config.toml` so the native theme
  no longer conflicts.

Ordering works because the toggle sets session state → rerun →
`streamlit_app.py` calls `apply_base_style()` before the page body.

**Fallback if the hardcoded-colour audit overruns:** delete the toggle and the
dark CSS entirely. A missing feature beats a broken one.

**Acceptance:** [visual] `--mode screenshots` with `theme_dark=True` produces a
dark page including all charts. [behavioural] no `<script>` tags in any
`stMarkdownContainer`.

---

### WP-3 · Tier annotation, applied once
**Closes** A2 · **Depends on** WP-0C for usefulness (ships without it) · **Effort** 1 day

`FilterState.apply()` filters on `repo_tier`, which no code creates and the
snapshot does not contain — so the sidebar Tier control is a silent no-op.

New `dashboard/lib/tiers.py`:

```python
def annotate_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `repo_tier` column from tiers.yaml. Unlisted repos → 'standard'."""
```

- Call it inside the cached loader (WP-7), so every page gets `repo_tier`.
- Replace the private `_repo_tier()` in `pages/04_needing_attention.py` with it.
- Add per-tier counts to the sidebar option labels (`critical (18)`).

**Acceptance:** [behavioural] `tests/test_data_filters.py` asserts
`FilterState(tier="critical").apply(df)` returns strictly fewer rows than
`tier="all"` on a fixture with mixed tiers.

---

### WP-4 · Scoring engine expresses uncertainty
**Closes** B7 · **Enables** B3, B10, D15, D18 · **Effort** 2 days

`calculate_scores()` currently exposes `score_unavailable_metrics` (column absent
from the snapshot) but cannot distinguish a **blank value in a present column**
from a **real score of 50**. Both silently become `default_when_missing: 50`.

Add to `dashboard/lib/scoring.py`:

| New column | Meaning |
|---|---|
| `score_defaulted_metrics` | list of metrics whose column exists but whose value was NaN/blank |
| `score_metric_confidence` | dict metric → `"measured"` \| `"defaulted"` \| `"unavailable"` |

`score_coverage` keeps its current meaning (fraction of weight from present
columns); a second `score_measured_weight` reports the fraction actually
*measured*, which is the number the UI should lead with.

Add a fourth status to `dashboard/ui/theme.py`:

```python
STATUS_COLORS["nodata"] = MUTED          # status_chip("nodata", "no data")
```
with a visually distinct treatment — a dashed border, not just a grey fill, so it
does not read as a muted pass (F6: colour is never the sole signal).

**Acceptance:** [behavioural] `tests/test_scoring.py` asserts that a fixture with
a present-but-blank `github.last_push` yields `commit_recency` in
`score_defaulted_metrics` and *not* in `score_unavailable_metrics`, and that a
real value yields neither. Grade distribution must be unchanged — this WP adds
metadata only.

---

### WP-5 · Stop overstating the score
**Closes** B1, B2, B3, A5 · **Depends on** WP-4 · **Effort** 3 days

The single most important package in the plan.

**Gauge (`dashboard/ui/kpi.py: _gauge_figure`)** — take `measured_weight` and
render the unmeasured remainder as a ghosted/hatched arc segment, with a
subtitle: `based on 50% of metric weight`. The caveat belongs on the number, not
in a fourth tile.

**Overview** — a persistent main-content banner when `measured_weight < 0.8`:
> Half of the scoring weight cannot be computed from the current snapshot
> (4 of 9 metrics). Scores are directional. [What's missing →]

Link to the WP-13 Scoring page.

**Repo Detail** — `Activity` and `Structural` tiles render `—` with a `no data`
chip when their category has no measured metric, instead of a confident `100.0`.

**Radar → bar chart (A5).** `_metric_radar` currently does:

```python
values = [per_metric.get(label, 100.0 if label in unavailable else 0.0) for label in labels]
```

Unavailable metrics are plotted at full radius, so a 5/9-metric repo looks
near-perfect. Replace with `charts.metric_score_bar(repo_row)`: a horizontal bar
per metric, measured metrics coloured by score, defaulted metrics muted and
labelled `default (50)`, unavailable metrics as a zero-width row labelled
`not collected`. This also fixes the overlapping radial ticks and the
single-series legend (D15) and reads on mobile (G3).

**Acceptance:** [visual] no chart or tile displays a value for an unavailable
metric. [behavioural] a test asserts `metric_score_bar` emits no numeric value
for any metric in `score_unavailable_metrics`. [review] banner copy.

---

### WP-6 · Honest trends and honest labels
**Closes** A4, A6, A7, A13, C4, D51, D53 · **Effort** 2 days

| Item | Change |
|---|---|
| A4 | Every trend chart labels its actual date range. Warn when the newest history snapshot is older than the current snapshot — the live bug: "May 2026" sparklines under a July snapshot. |
| A6 | `_top_movers` — losers via `nsmallest(5)`, and show only negative deltas. If none, say "no repositories declined" rather than presenting the smallest gains as losses. |
| A7 | Rename What Changed to state the real comparison window. Interim wording until WP-14 adds a period selector: *"Changes since the previous snapshot (6h)"*. |
| A13 | `dashboard/lib/bulletin.py` — omit the `Commit:` line when `GITHUB_SHA` is unset, rather than printing `local`. |
| C4, D51 | `streamlit_app.py` — gate the Ownership nav section on data presence, not just the feature flag: `if flags.get(...) and ownership_coverage(df) > 0`. Requires a cheap coverage probe in the loader. Also moots D52/D54/D55. |
| D53 | Replace "below the PRD trigger threshold (20%)" and equivalents with user-facing language. |

**Acceptance:** [behavioural] tests for A6 (all-positive-delta fixture) and A13.
[visual] Ownership absent from nav on a snapshot with no ownership columns.
[review] A7 and D53 copy.

**PR must include** a before/after grade-distribution diff — WP-5 and WP-6 touch
score presentation, and no published grade may move unintentionally.

---

## 4. Wave 2 — Defect sweep

### WP-7 · Caching and load consolidation
**Closes** H1, H2, H3 · **Effort** 1.5 days

Overview currently loads history three times per render (`_baseline_frame`,
`_top_movers`, `_load_org_avg_history`) and re-scores every snapshot each time.
`calculate_scores()` runs uncached on every page over 171 × 111 cells with
per-row Python loops.

In `dashboard/data.py`:

```python
@st.cache_data(ttl=300)
def load_scored_snapshot() -> pd.DataFrame:      # load → annotate_tiers → calculate_scores
@st.cache_data(ttl=300)
def load_scored_history(days: int = 30) -> list[Snapshot]:   # scored once, shared
```

Migrate all seven pages off `calculate_scores(load_snapshot())`. Add spinners on
the cold path; remove `show_spinner=False` from `_history_for_repo`.

Do this **before** WP-8 so the screenshot harness isn't fighting slow renders.

**Acceptance:** [behavioural] a test asserts `load_scored_snapshot` is cached and
that no page module imports `calculate_scores` directly.

---

### WP-8 · Visual defect batch
**Closes** A8, A9, A10, A11, A12, D6, D7, D8, D17, D19, D20, B12, C3, I8, E12, E13 · **Effort** 2 days

Independent one-liners. One PR, one screenshot-diff review.

| Item | Fix |
|---|---|
| A8 | `hide_index=True` on the `pages/03` dataframe. |
| A9 | Gauge tick clipping — `margin.l/r` 12 → 40, or narrow the indicator domain. `0` currently renders as a sliver and `100` as `1`. |
| A10 | `grade_histogram` — `margin.l` 12 → 56, or drop the y-axis title (the summary annotation already carries the meaning). |
| A11 | `render_repo_pill_list` — `min-width:0; overflow:hidden; text-overflow:ellipsis` on the name span, `flex-shrink:0` on the pill group, `title` attribute for the full name. |
| A12 | New `humanize_check()` in `dashboard/lib/schema.py`: collapse `exists..coveragerc` → `.coveragerc`, prefer the config title. Use everywhere a raw column name is displayed. |
| D6 | Drop the duplicate snapshot caption. |
| D7 | Replace "drill in via the sidebar nav" with the `org_branding.yaml` tagline (also closes part of I6). |
| D8 | `_delta_str` returns an explicit "no change" marker rather than `None`, so a suppressed delta doesn't read as a rendering bug. |
| D17 | Copy-link → icon button with clipboard copy, not a full-width `st.code`. |
| D19 | Filter labels: "All / Failing / Passing / Unknown". |
| D20 | Replace `st.code(f"value = {value!r}")` with a formatted value. |
| B12 | Move "Scoring config" out of the KPI row into the share/export block. |
| C3 | Move "Showing X of Y" directly under the filter group. |
| I8 | UTC label on every displayed date. |
| E12 | `page_icon` in `st.set_page_config`. |
| E13 | `toolbarMode = "minimal"` in `.streamlit/config.toml` to hide Deploy and the menu. |

**Acceptance:** [visual] screenshot diff reviewed for each; A9/A10/A11 verified
at 1440px and 390px.

---

### WP-9 · Contrast and heading structure
**Closes** F1, F2, F3, F4, E6 · **Effort** 1 day

Axe-confirmed, all in our own CSS or markup.

- **F1** `.status-chip.status-warn` — `#D97706` on a 12%-alpha tint of itself
  fails AA. Re-derive all four chip variants against their actual computed
  backgrounds. `theme.py`'s "WCAG AA against Surface" header comment is
  currently false; make it true or delete the claim.
- **F2** sidebar input placeholder on `rgba(255,255,255,0.10)`.
- **F3** `st.metric` delta green on `#FFFFFF` — override via CSS.
- **F4/E6** `st.markdown("##### Grade mix")` emits `h5` under `h1`; `pages/03`
  emits `h3`. Use `st.subheader` consistently.

**Acceptance:** [behavioural] `scripts/ux_audit.py --mode a11y` reports zero
`color-contrast` and zero `heading-order` violations on all seven pages, and is
wired into CI as a required check. Remaining violations
(`list`/`listitem`/`region`/`aria-allowed-attr`) are Streamlit-internal —
document them as known-and-accepted so the gate stays meaningful.

---

## 5. Wave 3 — Primitives

### WP-10 · Shared table component
**Closes** E2, E3, E4 · **Enables** D3, D11, D28, D35 · **Effort** 2.5 days

`dashboard/ui/tables.py` is a 7-line stub, which is why five pages each
reinvented a table and all of them leak raw column names.

```python
def repo_table(
    df: pd.DataFrame, *,
    columns: list[str] | None = None,
    show_grade_pill: bool = True,
    link_to_detail: bool = True,
    height: int | None = None,
) -> None:
```

Central `column_config` map, applied everywhere:

| Column | Config |
|---|---|
| `repo_name` | `TextColumn("Repository")` |
| `score_composite` | `ProgressColumn("Score", min_value=0, max_value=100, format="%.1f")` |
| `score_letter` | `TextColumn("Grade", width="small")` |
| `delta` | `NumberColumn("Δ 30d", format="%+.1f")` |
| `repo_tier` | `TextColumn("Tier", width="small")` |
| `reasons` | `TextColumn("Why flagged", width="large")` |
| `repo_link` | `LinkColumn("", display_text="Open")` — kills the truncated-URL problem |

`hide_index=True` is the default and not overridable. That is the actual fix for
A8 as a class rather than an instance.

**Acceptance:** [behavioural] a test asserts every `st.dataframe` call in
`pages/` routes through `repo_table` (AST check, or grep gate in CI).
[visual] all five tables re-screenshotted.

---

### WP-11 · Empty states, chart idiom, freshness banner
**Closes** I4, I5, E1, E10, C2 · **Effort** 2 days

- **I4/I5** One `empty_state(kind, title, body, action=None)` in `banners.py`,
  `kind ∈ {good, info, warn, error}` with fixed semantics. Seven pages currently
  use six different treatments; `render_empty_state()` exists and is called once.
  Fixes green-vs-blue being used interchangeably for "nothing here".
- **E1** Route every chart through themed helpers in `charts.py`. Delete the raw
  `px.bar` / `px.line` path — it is why `pages/03` bypasses the design system.
- **E10/C2** Call the already-written `render_freshness_banner()` in main content.
  A 3-day-stale snapshot past the 48h threshold currently signals only via a
  small amber dot in a dark sidebar.

**Acceptance:** [behavioural] no page module imports `plotly.express` directly.
[visual] stale-snapshot banner visible above the fold on all seven pages.

---

## 6. Wave 4 — Page rewrites

One WP per page. Ordered by PRD §1.2 persona priority so value lands early if the
wave slips. All depend on WP-10 and WP-11.

### WP-12 · What Changed → the weekly-meeting page
**Closes** D40, D41, D42, D43, D44, D45 · **Depends on** WP-0B · **Effort** 3 days · **Persona 1**

| Item | Change |
|---|---|
| D41 | Period selector (24h / 7d / 30d), defaulting to the shortest window that returns rows. Root cause of D40: comparing two 6-hour-apart snapshots yields nothing. |
| D40 | Empty state distinguishes "genuinely no change" from "insufficient history" — currently both render as green success. |
| D44 | Add score/grade change reporting: repos that changed grade, repos that crossed a tier, org-average delta. Absent today; this is the page WG leads open first. |
| D45 | Auto-written narrative summary, copy-pasteable into a meeting agenda. |
| D42 | Suppress the bulletin when there is nothing to report, instead of emitting a block full of `None`. |
| D43 | Render the bulletin; offer "copy source" as a toggle. Red monospace markdown source currently looks like an error. |

**Acceptance:** [behavioural] tests for the 7d/30d windows and for the
insufficient-history vs no-change distinction. [review] narrative copy.

---

### WP-13 · Needing Attention → a triage queue
**Closes** D32, D33, D35, D36, D37, D38 · **Depends on** WP-0C, WP-3 · **Effort** 2.5 days · **Persona 1**

Currently 9 of 171 rows, 8 with the identical reason "no commits in 90+ days";
`edx-platform` absent; grade-F repos with recent commits never flagged.

- **D32** Rework `attention_rules.yaml` so rules fire across tiers, not only for
  the 2 configured critical repos. Add a tier-independent low-grade rule.
- **D33** Severity ordering — rank by rule severity then score, not by tier
  string then score. A grade-B repo currently outranks grade-F ones.
- **D36** Show which rule fired, with a link to its definition; stop truncating
  multi-reason rows.
- **D35** `repo_table` with tier badges and grade pills.
- **D37** Tier options with counts, title-cased.
- **D38** Promote the download; demote the share block.

**Acceptance:** [behavioural] a test asserts every grade-F non-archived repo
appears at `tier=all`. Row count > 30 once WP-0C lands.

---

### WP-14 · Failing Checks → a work queue
**Closes** D26, D27, D28, D29, D30, D31 · **Effort** 3 days · **Personas 1–2**

**D31 is the package.** Invert the page: lead with a ranked list of *checks* —
human title, N repos failing, one-line remediation, actionability indicator —
each expanding to its repo list. That is the shape of the actual task, and it
makes D29 (a list of all 171 repos with no indication of which checks fail)
disappear rather than get fixed.

- **D26** Replace the 40-bar, 40-colour, rotated-label chart with the themed
  lollipop already used on Overview, capped at top-N with the remainder disclosed
  (never silently truncate).
- **D27** Add an explicit check selector alongside click-to-filter. `on_select`
  is wired but undiscoverable and needs a precise 12px click.
- **D28** `repo_table`.
- **D30** Collapse the three nested titles.

**Acceptance:** [visual] all axis labels legible at 1440px and 390px.
[behavioural] a test asserts the top-N cap emits a disclosure line.

---

### WP-15 · Repo Detail
**Closes** D13, D14, D16, D18, D21, D22, D23 · **Depends on** WP-4, WP-5 · **Effort** 3 days · **Persona 2**

- **D18** Status chip + human title in the *collapsed* expander header. Today you
  must open each of 43 expanders to learn its status. Highest-value item here.
- **D13** One search control. The selectbox already types-to-search; the extra
  text input silently caps at 30 results.
- **D14** Link to the actual GitHub repository. Currently absent.
- **D21** Repo header card from the unused columns: `github.description`,
  `license`, `created_at`, `fork_count`, `pulls_count`, `language_bytes.*`,
  `readthedocs_config.*`, `renovate.total_open_prs`.
- **D16** Category sparklines — shrink to true sparklines (no axes, ~28px) or
  drop. 160px charts in 3-across cards showing flat lines earn no space.
- **D22** Rewrite the `5/9 metrics (50% weight)` chip copy (contrast fixed in WP-9).
- **D23** Landing with no `?repo=` selects `openedx/DoneXBlock` alphabetically;
  prompt instead, or default to something meaningful.

**Acceptance:** [visual] collapsed check list shows status without interaction.
[behavioural] deep-link test for `?repo=`.

---

### WP-16 · Overview
**Closes** D1, D2, D3, D4, D5, D9, D11, D12 · **Depends on** WP-0G · **Effort** 2.5 days · **Personas 1–4**

- **D1** Grade-mix ribbon and Grade-distribution tab show identical data ~20px
  apart. Keep one.
- **D12** "What to look at first" — three callouts (worst critical repo, biggest
  regression, most-failed check) with direct links. Turns a dashboard into a
  to-do list.
- **D3** Mover tables via `repo_table` — labelled columns, consistent decimals,
  linked repos, grade context.
- **D4** Investigate implausible deltas (+44, +35 in 30d; five repos at exactly
  −15) before shipping. Likely a partial-baseline artifact; may be a WP-0B data
  bug rather than a UI one.
- **D9** "Stale repos 171" means every repo is stale, so the metric carries no
  signal. Re-derive the threshold for this org or replace the metric.
- **D11** Make the full table workable — sort, filter, pagination, pills.
- **D2** Label the F ribbon segment; the most alarming grade is currently the one
  you cannot see.
- **D5** Label the org sparkline with axis bounds and endpoint values.

**Acceptance:** [behavioural] D4 resolved with a stated root cause — data or
presentation. [review] D12 copy, and D3 wording per WP-0G.

---

### WP-17 · Checks Catalog
**Closes** D46, D47, D48, D49, D50 · **Depends on** WP-0D, WP-0E · **Effort** 2 days · **Personas 2–3**

- **D46** Search and filter over 76 expanders in a 5,900px scroll.
- **D49** Separate scored from informational checks per the WP-0E decision.
- **D48** Cross-link each check to the repos failing it. The page knows the org
  pass rate and links nowhere.
- **D47** Title fallback via `humanize_check()` (WP-8).
- **D50** Split the proposed/phase-2 roadmap out of the reference material.

**Acceptance:** [behavioural] search returns the correct check for a raw column
name, a human title, and a partial match.

---

### WP-18 · IA de-duplication
**Closes** C5, C6 · **Effort** 1 day

Deliberately last in the wave — deduplicating pages only makes sense once you
know what each has become.

- **C5** Merge Failing Checks with the Overview "Top failing checks" tab: the tab
  becomes a teaser linking into the full page.
- **C6** Move "Biggest gainers/losers" from Overview to What Changed, where score
  movement belongs and where WP-12 has already built the surface.

**Acceptance:** [visual] no data series appears on two pages with different
treatments.

---

## 7. Wave 5 — Adoption and orientation

### WP-19 · Footer, share, feedback, badges
**Closes** C9, K1, K2, K4, D10 · **Effort** 2.5 days

`org_branding.yaml` defines `footer.source_url` and `footer.privacy_url` and
**nothing reads that file**. There is no link to the source repo, the data
source, the privacy doc, or a way to report a problem.

- **C9** Footer from `org_branding.yaml`: source, data source CSV, privacy,
  pipeline, feedback.
- **K1** Share links first-class: one-click copy, plus OG/Twitter card meta so a
  pasted link previews in Slack rather than rendering as a bare URL. This is the
  core distribution mechanism per PRD §1.3 and is currently a collapsed
  expander containing an `st.code` block.
- **D10** Persistent share button in the page header, not at the bottom of a
  2,000px page.
- **K4** Report-a-problem / contribute-a-check link.
- **K2** Flip `enable_badge_links` — badges in repo READMEs are the highest-leverage
  distribution channel available, and the page is already built.

**Acceptance:** [visual] footer on all seven pages; OG preview verified with a
card validator.

---

### WP-20 · Navigation and orientation
**Closes** C1, C7, C8, C12, C13, I9 · **Effort** 2 days

- **C1** Brand and freshness above nav. `st.navigation` renders before
  `st.sidebar` content, so this needs `st.logo()` or a different composition —
  the wordmark currently sits *below* the nav links.
- **C8** Global "jump to repo" from every page — the highest-frequency action,
  currently requiring two stacked controls on one specific page.
- **C13** Task-order the nav: What Changed → Needing Attention → Overview → …
  for persona 1.
- **C7/I9** One vocabulary per concept. "Ownership" vs "Maintainer and Working
  Group Views"; "Repo Detail" vs "Repository Detail"; four names for the
  attention concept.
- **C12** Breadcrumbs for deep-link arrivals.

**Acceptance:** [visual] sidebar order at 1440px and 390px. [review] vocabulary.

---

### WP-21 · Scoring transparency surface
**Closes** B6, B9, B10, B11 · **Depends on** WP-4, WP-0E, WP-0F · **Effort** 2 days

- **B6** A Scoring page: the 9 metrics, weights, letter bands, the
  `default_when_missing: 50` policy, and current measured coverage per metric.
  No such explainer exists; it answers the first question every viewer has.
- **B11** Grade-band tooltip on every pill (a viewer seeing "Grade B" cannot
  learn that B = 60–79 without leaving the page).
- **B9** Surface ties — all five "Top 5" repos score exactly 96.7 and there are
  almost certainly more.
- **B10** n-metrics-measured badge in table contexts, so rankings stop mixing
  well-measured and poorly-measured repos silently.

**Acceptance:** [behavioural] the Scoring page renders weights read from
`scoring.yaml`, never hardcoded. [visual] tie disclosure on Overview.

---

### WP-22 · Copy pass
**Closes** I1, I2, I3, I6, I7 · **Effort** 2 days · Largely `[review]`

- **I1** First-run orientation: what is measured, by whom, how often, what to do.
- **I2** De-jargon: "PRD trigger threshold", "Scoring config", "score coverage",
  "structural/activity", "N/A", raw check keys.
- **I3** Empty states say what to do, not just what is absent.
- **I7** Tell people how to fix the two big data gaps — the missing activity
  metrics and missing ownership both need actions the dashboard can name
  precisely.
- **I6** Use the tagline (partly done in WP-8).

**Acceptance:** [review] a named reviewer outside the project reads every string.

---

## 8. Wave 6 — The action loop

### WP-23 · Remediation surfacing
**Closes** J1, J2, J6, I10 · **Depends on** WP-14, WP-0D · **Effort** 2 days

- **J6** State which failures are actionable *before* the user clicks.
  `missing_remediation_checks()` exists and is used only for a config-gap caption.
- **J1** Promote remediation out of three-levels-deep (page → expander → scroll
  past status, description, and a Python repr).
- **J2** State PR-template coverage — how many of the failing checks actually
  offer the button.
- **I10** Surface `why_it_matters` from WP-0D. One sentence on consequence is what
  converts a report into behaviour change.

**Acceptance:** [visual] actionability visible in the collapsed check list.

---

### WP-24 · Blast-radius ranking and bulk action
**Closes** J3, J4, J5, J7 · **Depends on** WP-23 · **Effort** 3.5 days

- **J4** Rank checks by repos-failing × ease-of-fix. This is the most valuable
  artifact the dataset can produce and it is not shown anywhere.
- **J3** Bulk action for the ~150-repo checks. `readme.security` fails on roughly
  150 repos and the only path is 150 individual visits. Even generating a
  checklist or a `gh` command line would change the economics.
- **J7** Fix-it-Friday view — mechanically-fixable checks by blast radius with
  copy-paste snippets. A recurring community ritual the dashboard can anchor.
- **J5** Feedback that an action was taken (link to issues referencing the
  dashboard), since the next snapshot is up to 6 hours away.

**Acceptance:** [behavioural] the ranking is reproducible from a fixture.
[review] bulk-action ergonomics with a real maintainer before shipping.

---

## 9. Wave 7 — Accessibility and mobile, structurally

> **Escalate this wave ahead of Waves 5 and 6 if any consumer has a procurement
> or compliance requirement.** Several Open edX operators are public-sector, and
> this ordering assumes none of them has a hard requirement. Confirm that
> assumption before accepting the sequence.

### WP-25 · Non-visual access
**Closes** F5, F6, F7, F8, F9, F10, F11, E11 · **Effort** 3 days

- **F7** Text alternatives for every chart — Plotly output is canvas/SVG with no
  `aria-label`, so a screen-reader user gets nothing from the gauge, ribbon,
  histogram, or metric bars. A "view as table" toggle per chart is the cheapest
  complete answer and helps sighted users too.
- **F6** Colour is never the sole signal: freshness dot, unlabelled ribbon
  segments, mover delta signs. `status_chip()` already does this correctly.
- **F5** Landmarks and skip-links (44 elements outside landmarks on Overview).
- **F8** Extend `aria-label` from grade pills to all chips.
- **F9** Contrast-check the focus ring on both the dark sidebar and white cards.
- **F10** Keyboard path through long expander lists (WP-17 search helps).
- **F11** Audit all ~15 `unsafe_allow_html` sites. `render_repo_pill_list`
  escapes correctly; confirm the rest. Repo names come from an upstream CSV.
- **E11** Distinguish grade A (`#15803D`) from B (`#16A34A`) — near-identical at
  pill size.

**Acceptance:** [behavioural] axe gate stays green; manual VoiceOver pass on
Overview and Repo Detail documented in the PR.

---

### WP-26 · Responsive layout
**Closes** G1, G2, G3, G4, G5, G6 · **Effort** 3 days

At 390px the title wraps to three lines, the gauge fills the first viewport, and
four KPI tiles stack one per row — roughly four screens before any content.

- **G1/G2** Real mobile layout; `st.columns` currently squeezes rather than
  reflows (5-across KPIs, 3-across category cards).
- **G3** Reflowing charts — fixed heights (`280`, `64`, `160`, `max(280, 32n+80)`)
  and label sets designed for 1400px.
- **G4** Horizontal-scroll affordance for wide tables; content is currently cut.
- **G5** The hamburger hides filters, freshness, *and* brand, leaving an
  unlabelled page.
- **G6** Mobile glance view: org grade, three deltas, top 3 attention items.

**Acceptance:** [visual] 390px and 768px screenshots of all seven pages in the
baseline set; no horizontal body scroll at any width ≥ 320px.

---

## 10. Wave 8 — Performance and robustness

### WP-27 · Render and cache hardening
**Closes** H4, H5, H6, H7, H8, E5 · **Effort** 2 days

Deferred deliberately: at 171 repos none of this is user-visible today. It
becomes urgent if repo count or traffic grows.

- **H4/H7** `st.fragment` for filters, tabs, and Repo Detail. Repo Detail
  currently re-renders 43 expanders, 5 cards, 5 charts, and a radar on every
  keystroke in the search box.
- **H5** Align the 300s snapshot TTL with the 86,400s history TTL — KPI values
  and their deltas can disagree for up to 24 hours after a pipeline run.
- **H6** Bound the per-repo history cache (browsing 20 repos holds 20 copies of
  the 30-day history).
- **H8** Revisit `expected_min_columns: 100` against an actual 111 — a modest
  upstream change trips validation and silently swaps in last-known-good with no
  user-visible notice. Add that notice too.
- **E5** Self-host or drop the Google Fonts `@import`: render-blocking, and it
  fails silently behind restrictive CSPs, reverting typography to system sans.

**Acceptance:** [behavioural] a test asserts a stale-fallback event produces a
user-visible banner.

---

## 11. Wave 9 — Decide before scheduling

Each item needs a yes/no before it earns a WP. Several are reject candidates and
that is a fine outcome. **No effort estimates** — estimating unapproved work is
how backlogs rot.

**Cleanup decisions**
- **C10** `strings.yaml` is read by nothing and every label is hardcoded, so the
  i18n scaffolding and `scripts/check_i18n_readiness.py` are inert. Wire it up or
  delete it. Do not leave it as decoration.
- **C11** SQL / Badges / Cards are built, working, flag-off, and self-labelled
  "Phase 2". Ship as a Labs section or delete the wiring. (K2 already flips
  Badges.)
- **E9** Delete the unused `card()` context manager.
- **E7** Lighten the shadow treatment — everything has a shadow, so nothing
  stands out.
- **E8** **Is the custom dark sidebar worth its fragility?** `theme.py` carries
  four defensive comments about fighting Streamlit's emotion CSS, including one
  about Material icons rendering as literal ligature text. This is a standing
  maintenance tax on every Streamlit upgrade.

**Moot if WP-6 hides Ownership:** D52, D54, D55.

**Feature proposals:** D24 compare mode · D25 per-repo score history ·
D39 triage state · K3 RSS/digest · K6 celebrate improvements ·
F12 accessibility statement.

**Bigger bets:** L2 static OG score cards · L3 time-machine slider ·
L4 cohort comparison · L5 anomaly detection · L6 public JSON API (cheap given the
pre-compute architecture) · L7 health budgets · L8 new-repo onboarding wizard.

**Park explicitly: L9** — moving the public read-only surface off Streamlit.
Almost everything is static per snapshot, so the case is real, but it should not
be decided in the same pass as a UX backlog.

---

## 12. Sequencing and totals

| Wave | Packages | Effort | Can start |
|---|---|---|---|
| 0 | WP-0A … WP-0G | external | **day 1** |
| 1 | WP-1, **WP-2A**, WP-2 … WP-6 | ~12 d | day 1 (WP-1, then WP-2A) |
| 2 | WP-7, WP-8, WP-9 | ~4.5 d | after WP-1 |
| 3 | WP-10, WP-11 | ~4.5 d | after WP-7 |
| 4 | WP-12 … WP-18 | ~17 d | after WP-10, WP-11 |
| 5 | WP-19 … WP-22 | ~8.5 d | after Wave 4 (WP-19 can run parallel) |
| 6 | WP-23, WP-24 | ~5.5 d | after WP-14 |
| 7 | WP-25, WP-26 | ~6 d | after Wave 4 — **escalate if compliance applies** |
| 8 | WP-27 | ~2 d | any time after Wave 3 |
| 9 | — | unestimated | after decisions |

**Total scheduled: ~59 dev-days** across Waves 1–8, plus Wave 0 external
dependencies and Wave 9 pending decisions.

### Hard dependencies

```
WP-1  ─→ every "[visual]" acceptance criterion
WP-2A ─→ every "[visual]" criterion being of the REAL app, not an unstyled render
WP-4  ─→ WP-5 ─→ WP-15, WP-21
WP-7  ─→ WP-8 ─→ (screenshot baselines stay stable)
WP-10 ─→ WP-12, WP-13, WP-14, WP-15, WP-16
WP-11 ─→ all of Wave 4
WP-14 ─→ WP-23 ─→ WP-24
WP-0B ─→ WP-12          (ship the disclosure half regardless)
WP-0C ─→ WP-13          (ship the rule rework regardless)
WP-0D ─→ WP-17, WP-23
WP-0E ─→ WP-17, WP-21
WP-0G ─→ WP-16 copy
```

### Suggested first three PRs

1. **WP-1** — harness and version pin. Everything else is unverifiable without it.
2. **WP-2A** — entry-script bypass. Found by WP-1 on its first run. Without it the
   harness measures a broken render, and a flag-disabled page is live in production.
3. **WP-4** — scoring uncertainty. Metadata only, no visible change, unblocks the
   whole honesty wave.
4. **WP-5** — stop overstating the score. The highest-value user-visible change
   in this document.

In parallel, on day 1: file WP-0A and WP-0B upstream, and put WP-0C, WP-0E, and
WP-0G on the next WG agenda.
