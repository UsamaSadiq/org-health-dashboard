# Open edX Repository Health Dashboard — Product Requirements Document (v3)

## Document Status

| Field | Value |
|---|---|
| Document version | 3.0 |
| Status | Approved for Phase 1 implementation (final, post-validation pass) |
| Owner | Usama Sadiq (Principal Software Engineer, Arbisoft; Open edX Distinguished Core Contributor) |
| Last updated | 2026-05-15 |
| Supersedes | `docs/PRD_v2.md` |
| Target repositories | `UsamaSadiq/org-health-dashboard` (primary), `openedx/wg-maintenance` (limited), `openedx/edx-repo-health` (out of scope) |
| Live dashboard (current) | https://share.streamlit.io (first-cut viewer, single-file `streamlit_app.py`, 374 lines) |
| Upstream data contract | https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_main.csv |
| Live CSV shape (verified 2026-05-15) | 181 rows × 123 columns, snapshot date `2026-05-08` |

### Changes from v2.0

v2 was structurally sound but contained verifiable inaccuracies against the shipped code and the live CSV, and it lagged the 2026 Streamlit, CHAOSS, and OpenSSF release surface. v3 incorporates the following decisive corrections and targeted improvements drawn from a full validation pass against `streamlit_app.py`, the upstream CSV, Streamlit 1.57 release notes, the current CHAOSS metric catalogue, the current OpenSSF Scorecard check list, and the open-source-licensing landscape in 2024–2026.

**Decisive corrections (no debate, factual):**

1. **Python runtime aligned to 3.12.** v2 stated a Python 3.11 floor; the shipped `runtime.txt` already specifies `python-3.12`. v3 standardizes on 3.12 throughout (`runtime.txt`, `pyproject.toml`, CI matrix).
2. **Streamlit dependency floor raised to 1.56.** v2 specified ≥ 1.40; current stable is **1.57.0** (released 2026-04-28). `st.experimental_get_query_params` and `st.experimental_set_query_params` have been **removed** in the 2026 release line — v3 references `st.query_params` only.
3. **`streamlit-plotly-events` removed from the stack.** v2 §3.1.2 named the third-party library; it is now obsolete. v3 uses native `st.plotly_chart(..., on_select="rerun", selection_mode=...)`.
4. **Pandas floor raised to 2.2; Plotly floor to 5.20 retained.**
5. **Upstream CSV schema clarifications:**
   - `TIMESTAMP` is a **`YYYY-MM-DD`** date string (not a full ISO 8601 datetime). `github.last_push` is **`YYYY-MM-DD HH:MM:SS`** with no timezone suffix. v2's "ISO 8601" wording is replaced with explicit formats and parsing notes.
   - `ownership.theme`, `ownership.squad`, `ownership.priority`, and `org_name` **columns exist in the upstream CSV** as of 2026-05-15 but are populated with empty strings for all 181 rows. v2 stated these columns "do not yet exist." v3 reframes the Phase 2 maintainer-view trigger as **"upstream populates these columns"** rather than "upstream adds them."
   - The live CSV has **123 columns**, of which v2 named ~15. Appendix B has been expanded to catalogue all columns relevant to the dashboard, with explicit Phase 1 / Phase 2 / unused dispositions.
6. **CHAOSS metric name updated: "Bus Factor" → "Contributor Absence Factor"** (CAF). CHAOSS renamed the metric in 2024; v3 uses the canonical name with "Bus Factor" preserved as an alias in the glossary.
7. **OpenSSF Scorecard cross-reference expanded to all 20 canonical checks** (v2 listed 7). The Scorecard public API endpoint is `https://api.securityscorecards.dev` (v2 hinted at `api.scorecard.dev`, which does not exist).
8. **WCAG 2.2 AA criteria explicitly enumerated.** v2 named "WCAG 2.2 AA" but only addressed contrast and labels. v3 adds the three criteria *new* in 2.2 vs 2.1: **2.4.11 Focus Not Obscured**, **2.5.7 Dragging Movements**, **2.5.8 Target Size (Minimum)**.

**Targeted enhancements:**

9. **Adopt Streamlit 1.55+ widget `bind=` for URL state sync** where it cleanly replaces manual query-param plumbing in `linking.py`. Manual plumbing is retained only for state that does not map 1:1 to a single widget (e.g., compound filters).
10. **Adopt `st.column_config.LinkColumn`** for clickable repo cells in the All-Repos table and **`st.dialog`** for the "view raw check output" surface.
11. **Streamlit Community Cloud cold-start and memory limits qualified.** Official documentation does not publish numeric limits; v3 marks any specific numbers as community-reported and treats Hetzner migration as a documented but unscheduled trigger.
12. **CLA decision preserved, OpenStack DCO precedent explicitly acknowledged.** OpenStack moved from CLA to DCO effective 2025-07-01. v3 retains the AGPL-3.0-or-later + CLA combination on the productization rationale documented in Appendix C, but adds explicit prose in §10.5 and Appendix C explaining why this project's situation diverges from OpenStack's.
13. **Implementation honesty.** The shipped `streamlit_app.py` has no error handling on the CSV fetch. v3 calls this out as a PR 2 deliverable, not pretending it is already there.
14. **Glossary, Risk Register, and Definition-of-Done refined; no new top-level sections versus v2.**

---

## Executive Summary

The Open edX Repository Health Dashboard is a community-maintained analytics surface filling the gap left by the Bitergia Analytics shutdown in March 2026. Phase 0 (a daily-cron data pipeline that commits `dashboard_main.csv` into `openedx/wg-maintenance`) is shipped. A first-cut Streamlit visualization is also shipped at `UsamaSadiq/org-health-dashboard` but is currently functioning as a CSV viewer with light styling and no error handling.

This document specifies the work to convert that snapshot viewer into a **visualization-first, deep-linkable, scoring-aware, trend-aware, resilient** community tool that is also architecturally compatible with future generalization to non-Open-edX organizations and with future commercial productization. The dashboard does not own check definitions; those live upstream in `openedx/edx-repo-health` and reach the dashboard through `dashboard_main.csv`. The dashboard owns presentation, scoring, deep-linking, trend computation, remediation linkage, and action-loop deep links.

Phase 1, the immediate scope, is delivered through five sequenced pull requests over an estimated four to six weeks of part-time effort. Phase 2 and Phase 3 items are documented for traceability but not implemented under this PRD.

---

## 1. Strategic Context

### 1.1 Problem

Bitergia Analytics, the previous community-visible health dashboard for Open edX, was shut down in March 2026. The ecosystem lost real-time repository health visibility, contributor trend analysis, maintenance-risk signals, and compliance tracking. Existing internal tooling (`edx-repo-health`, `pytest-repo-health`) produces health-check data but had no public dashboard. The first-cut Streamlit dashboard exposes this data but does not yet drive action.

### 1.2 Audience

In priority order:

1. **Maintenance Working Group leads** running weekly meetings, needing "what got worse this week" and "which critical repos need attention" views.
2. **Repo maintainers** wanting to know the health of repos they own and how to fix specific failing checks.
3. **Working group members and contributors** browsing for context before opening PRs or filing issues.
4. **Axim and 2U engineering leadership** needing ecosystem health rollups for strategic planning.
5. **External community observers** (conference attendees, prospective contributors, researchers) evaluating ecosystem health from outside.

### 1.3 Vision

The dashboard becomes the canonical surface that working group members reference in Slack, forum threads, and conference talks. URLs from the dashboard are pasted into discussion alongside text. Failing checks have one-click paths to remediation. The dashboard makes maintenance work visible enough that ignoring it has social cost, and easy enough that fixing it has low effort cost.

Architecturally, the dashboard is built as a generic engine with Open-edX-specific configuration. The same codebase, with a different config directory, can run for any GitHub organization that has a similar CSV pipeline. The corporate-product path (hosted multi-tenant version with enterprise features) is preserved through the license and architectural choices below.

### 1.4 Prior art and positioning

The dashboard is positioned alongside, not in competition with, the following projects (full comparison in Appendix E):

- **OpenSSF Scorecard** — Linux Foundation security-posture checks across ~20 named checks. Complementary; the dashboard cross-references Scorecard check IDs (Appendix A and Appendix E). A Phase 2 enhancement reads upstream Scorecard JSON from `api.securityscorecards.dev` when available.
- **CHAOSS metrics / Cauldron / GrimoireLab** — community-health metric definitions and tooling. The 9-metric formula in Appendix A is annotated with current CHAOSS metric names (e.g., *Contributor Absence Factor*, formerly *Bus Factor*).
- **libraries.io, Snyk Advisor, GitHub Insights** — single-repo health surfaces. The dashboard is **org-scoped and curated**, which none of these are.
- **OSSF Allstar, deps.dev** — org-level policy enforcement and dependency observability. The dashboard does not enforce; it surfaces.

The dashboard's distinct value proposition: **org-curated, openedx-aware, scoring-transparent, deep-linkable, and action-loop-enabled**.

### 1.5 Non-goals

- The dashboard does not define, modify, or own health checks. Those live in `openedx/edx-repo-health`.
- The dashboard does not write to repos, file PRs, or take any actions on the user's behalf. It generates deep links that hand the user off to GitHub with pre-filled state, never API calls that mutate.
- The dashboard does not host a database, authentication system, or user accounts in Phase 1.
- The dashboard does not replace `pytest-repo-health` or compete with it. It consumes its output.
- The dashboard does not aim to replicate the contributor-affiliation and identity-resolution features of GrimoireLab in Phase 1. Those are documented as Phase 2 deferred work.
- The dashboard does not act as a security scanner. Where a check overlaps OpenSSF Scorecard, the dashboard cross-references but does not duplicate Scorecard execution.

---

## 2. Architectural Decisions (Locked)

### 2.1 Stack

| Layer | Choice | Rationale |
|---|---|---|
| Visualization | Streamlit ≥ 1.56 (stable line 1.57+ targeted) | Already shipped, zero hosting cost on Community Cloud, productization port is mechanical. 1.55+ required for widget `bind=` (URL-state sync); 1.56+ required for `st.navigation` with external URLs and `st.dialog` GA. `st.experimental_*` query-param APIs have been removed in the 2026 release line. |
| Charting | Plotly ≥ 5.20 | Streamlit-native, sufficient quality for radar, sparkline, histogram, stacked-bar. Plotly events are handled via `st.plotly_chart(on_select="rerun")`; `streamlit-plotly-events` is **not** a dependency. |
| Data format | CSV from `openedx/wg-maintenance/main:dashboards/dashboard_main.csv` | Already the contract with upstream. The CSV is committed by the `repo-health-job` workflow. |
| Pandas | ≥ 2.2 | PyArrow-backed nullable types; faster CSV parse. |
| Python | 3.12 floor | Matches shipped `runtime.txt` and `openedx/wg-maintenance` runtime. |
| Fuzzy search | `rapidfuzz` ≥ 3.5 | Permissively licensed, fast C++ backend; preferred over `thefuzz` (GPL transitive risk). |
| Optional analytical layer (Phase 2) | DuckDB ≥ 1.0 | In-process, reads CSV/Parquet directly, no infrastructure. |
| Deferred future analytics engine | Perceval (CLI subprocess only, JSON output) | Preserves AGPL-clean separation from GrimoireLab's GPLv3. |
| Hosting (Phase 1) | Streamlit Community Cloud (free) | Zero cost. Resource and idle-sleep limits are not publicly documented; cold-start figures cited in this PRD are community-reported, not official. |
| Hosting (Phase 2 trigger) | Hetzner CX22 at approximately EUR 4.50 per month | Documented, not yet executed. |

**Rejected:** Metabase (configuration outside git, fragments domain logic, no support for two-way features like badges and deep links). GrimoireLab full stack (GPLv3 licensing forecloses productization, 4–16GB RAM operational footprint, aging Kibiter UI). Dash (heavier framework, less idiomatic Python). Panel/Holoviz (capable but smaller community, less Streamlit Cloud parity). `streamlit-plotly-events` (obsoleted by Streamlit's native `on_select` API in 2025).

### 2.2 License

**Repository license: AGPL-3.0-or-later.**
**Contribution model: CLA via cla-assistant.io, text modeled on the Apache ICLA, with a DCO fast path for trivial contributions.**

The 2024–2026 licensing landscape strongly validates AGPL: Elastic re-added AGPLv3 alongside SSPL in August 2024, and Redis re-added AGPLv3 by May 2025 after losing community trust to the Linux Foundation's Valkey fork. The CLA half is more contested — OpenStack moved from CLA to DCO effective 2025-07-01. v3 retains the CLA on the productization rationale in Appendix C, with an explicit acknowledgment of the OpenStack precedent in §10.5 and Appendix C.5.

Rationale, alternatives, and operational details: see Appendix C.

### 2.3 Repository boundaries

This PRD touches three repositories with sharply different scopes:

**`UsamaSadiq/org-health-dashboard`** (primary): all dashboard code, configuration, scoring logic, remediation snippets, badge-rendering logic, deep-link routing, trend computation. Approximately 95 percent of the implementation work.

**`openedx/wg-maintenance`** (limited): one Phase 2 deferred change, a workflow step that pre-generates badge SVGs into `dashboards/badges/`. Phase 1 makes no changes to this repository.

**`openedx/edx-repo-health`** (out of scope): no changes. If a Phase 2 or Phase 3 feature requires a new check, it is filed as a separate issue against this repository following the normal Open edX contribution flow.

### 2.4 Productization compatibility

The codebase enforces a strict separation between domain logic (portable Python in `dashboard/lib/`) and presentation (Streamlit code in `streamlit_app.py` and `pages/`). All Open-edX-specific content lives in `dashboard/config/openedx/`. The data source URL is config. The repository contains no hardcoded reference to "openedx" outside the README, the `docs/` directory, and the `config/openedx/` directory.

A future closed-source commercial version, if pursued, replaces the Streamlit presentation layer with a Next.js or similar frontend, swaps the `config/` directory for a managed control plane, and reuses the entire `dashboard/lib/` domain layer unchanged. The CLA preserves the legal right to do so.

---

## 3. Functional Scope

### 3.1 Phase 1 (in scope, this PRD)

#### 3.1.1 Architectural refactor

Convert the current single-file `streamlit_app.py` (374 lines, no error handling on the upstream CSV fetch) into a multi-module layout. No user-visible behavior change in this PR beyond the freshness banner and fallback-to-last-known-good (§4.7).

Acceptance criteria:

- `dashboard/lib/` contains pure-Python modules with zero Streamlit imports: `scoring.py`, `trends.py`, `remediation.py`, `linking.py`, `badge.py`, `bulletin.py`, `schema.py`.
- `dashboard/data.py` exposes `load_snapshot() -> pd.DataFrame`, `load_history() -> List[Tuple[datetime, pd.DataFrame]]`, `load_config(name: str) -> dict`. `load_snapshot` wraps the CSV fetch with explicit error handling and fallback to the last-known-good snapshot per §4.7.
- `dashboard/config/openedx/` contains `check_groups.yaml`, `check_descriptions.yaml`, `remediation.yaml`, `tiers.yaml`, `scoring.yaml`, `org_branding.yaml`, `data_source.yaml`, `pr_templates.yaml`, `attention_rules.yaml`, `strings.yaml`.
- All Open-edX-specific strings (URLs, check-name references, working-group names) live in YAML config, not Python.
- `streamlit_app.py` reduced to under 100 lines; thin orchestrator only.
- `pages/01_overview.py`, `pages/02_repo_detail.py`, `pages/03_failing_checks.py`, `pages/04_needing_attention.py`, `pages/05_what_changed.py`, `pages/06_glossary.py` exist as separate page files via `st.navigation` / `st.Page`.
- All dependencies pinned to exact versions in `requirements.txt`, with floors documented in §2.1.
- A `pytest` suite under `tests/` exercises `dashboard/lib/` modules without Streamlit (i.e., zero Streamlit imports in test files for `lib/`).
- A schema-shape soft assertion in `data.py` logs but does not raise on missing columns; logged misses are persisted to `dashboard/lib/schema.py.MISSING_COLUMNS` for surfacing in the Glossary.
- The canonical repo identifier column is **`repo_name`** (confirmed against the live CSV) and the snapshot timestamp column is **`TIMESTAMP`** (a `YYYY-MM-DD` date string, **not** a full ISO 8601 datetime). The repo last-push column **`github.last_push`** is a naive `YYYY-MM-DD HH:MM:SS` string with no timezone — treated as UTC. These constants and parser hints live in `dashboard/lib/schema.py` and are referenced everywhere else by import, not by string literal.

#### 3.1.2 Visualizations-first UX

No tab's default view is a wide table. Tables exist behind toggles, downloads, or as expandable rows under a chart.

Acceptance criteria:

- Overview tab opens with: KPI strip, grade histogram, per-category pass-rate bars, top 10 most-failing checks across the org, top 5 best and bottom 5 worst repos by composite score. Plotly only. No data grid in the default view.
- A "Show as table" toggle reveals the legacy emoji-grid table, off by default. State persisted via `?view=table` query param.
- A "Download data" button always visible, exports filtered data as CSV and JSON.
- Failing Checks tab keeps its tabular layout (the rows are the actions) but adds a stacked bar chart at the top, with click-to-filter behavior on bar segments via Plotly `customdata` and **native** `st.plotly_chart(..., on_select="rerun", selection_mode=["points"])`. The third-party `streamlit-plotly-events` package is **not** used.
- The All-Repos table uses `st.column_config.LinkColumn` so repo names render as clickable links into the Repo Detail view.
- "View raw check output" for a single check on Repo Detail is implemented as `st.dialog`.

#### 3.1.3 Repo Detail: URL-first, search-first, compare-capable

Single Repo Detail surface, opens with a prominent search box and a typeahead populated from the repo list. URL parameter `?repo=X&tab=detail` opens the page directly to that repo.

Acceptance criteria:

- Search box uses fuzzy matching (`rapidfuzz` library, pinned).
- `?repo=edx-platform&tab=detail` deep-links to a fully-rendered Repo Detail view.
- Per-row repo names in Overview and Failing Checks are clickable links (via `LinkColumn` or markdown links) that set the query param.
- Per-category mini-cards (pass-fail-N/A counts, 30-day sparkline if history available) precede the per-check expanders.
- A "Compare with..." control adds a second repo for side-by-side rendering. Both repos visible in URL (`?repo=A&compare=B`).
- Compare mode is read-only; no edits, no actions invoked from compare view.

#### 3.1.4 Deep links and shareable state

Every meaningful filter state is encoded in URL query parameters. Where the state maps cleanly onto a single widget, **Streamlit's widget `bind=`** (available from 1.55) auto-syncs widget state to a named query parameter. For compound or derived state, `dashboard/lib/linking.py` provides explicit serialize/deserialize helpers.

Acceptance criteria:

- Supported params: `tab`, `repo`, `compare`, `category`, `view`, `search`, `archived`, `tier`.
- Simple, 1:1 widget params (`search`, `archived`, `view`) use widget `bind=`.
- Compound/derived params (`repo`+`compare`, `tab`+`category`) are centralized in `linking.py`.
- A "Copy link to this view" button on every tab serializes current state and copies to clipboard.
- The dashboard URL parses cleanly with no required params; defaults are documented in `linking.py` docstrings and `docs/ARCHITECTURE.md`.
- A redirect map handles renamed params so old shared links remain valid through two minor versions.

#### 3.1.5 Filter-aware exports

CSV and JSON download buttons honor the currently-applied filters.

Acceptance criteria:

- `st.download_button` with a generated filename containing the filter description, for example `openedx-health-active-2026-05-15.csv`.
- JSON export includes a top-level `metadata` block with snapshot timestamp, filter description, scoring config version, dashboard version, and `data_source_url`.
- CSV export matches the column subset visible in the current view.
- Both exports are UTF-8, newline-LF, and BOM-free.

#### 3.1.6 Remediation snippets

Each failing check, where applicable, shows a copy-pasteable fix snippet anchored to a canonical Open edX source.

Acceptance criteria:

- `dashboard/config/openedx/remediation.yaml` maps check name to a remediation entry containing `title`, `description`, `snippet` (optional code block), `source_url` (link to canonical doc or template), `applies_to_tiers` (list, optional), `chaoss_metric` (optional), `scorecard_check` (optional).
- On Repo Detail, failing checks render a "Show remediation" expander when an entry exists.
- A "Copy snippet" button copies the code block to clipboard.
- Checks without a remediation entry render only their pass/fail status; absence is not an error and surfaces in the Glossary as a "documentation gap" marker.
- The remediation entry schema is documented in `dashboard/config/README.md` and validated by JSON Schema (§6.3).

#### 3.1.7 Issue-filing deep links

For each failing check on Repo Detail, a "File issue on this repo" button generates a GitHub `/issues/new` URL with pre-filled content.

Acceptance criteria:

- `dashboard/lib/linking.py` exposes `github_issue_url(repo: str, check: str, body_template: str, labels: list[str] | None, assignees: list[str] | None) -> str`.
- Supported query parameters: `title`, `body`, `template`, `labels`, `assignees`, `projects`, `milestone`, `type`. `labels` / `assignees` / `projects` are silently dropped server-side if the visitor lacks permission — this is GitHub's behaviour and is documented in the Glossary.
- Body template is configurable per-check in `remediation.yaml`, with a generic fallback.
- Body includes a closing line: "Filed via the Open edX Repository Health Dashboard (dashboard URL) — please review and edit before submitting."
- Buttons open GitHub in a new tab (`target="_blank" rel="noopener noreferrer"`).
- No GitHub API calls; pure URL construction.

#### 3.1.8 Trend dimension

The dashboard reads historical snapshots of `dashboard_main.csv` from `openedx/wg-maintenance` git log and surfaces deltas.

Acceptance criteria:

- `dashboard/lib/trends.py` exposes `load_history(days: int = 90) -> List[Snapshot]`, where `Snapshot` is a small dataclass with `timestamp` (parsed as a `date`) and `df`.
- History reading uses GitHub's REST API (`/repos/.../commits?path=...`) for commit list, then fetches individual blobs only as needed, **unauthenticated**. Rate-limit-safe: cached in `st.cache_data` with TTL of 24 hours.
- A new "What changed this week" tab shows newly-failing and newly-passing checks since the most recent snapshot at least 7 days old.
- Overview's "top movers" widget shows the 5 repos with biggest score improvement and biggest score regression over 30 days.
- Repo Detail shows a 30-day sparkline per category.
- A weekly bulletin export generates a markdown block ready to paste into Slack or discuss.openedx.org.
- Bulletin output includes a "Generated by Open edX Repository Health Dashboard" footer and the dashboard's commit SHA.

#### 3.1.9 9-metric scoring layer

Implement the 9-metric composite score from the original spec, computed in `dashboard/lib/scoring.py` from the columns currently available in `dashboard_main.csv`. Metric definitions cross-reference CHAOSS and OpenSSF Scorecard where applicable (see Appendix A).

Acceptance criteria:

- `dashboard/config/openedx/scoring.yaml` defines per-metric weights, thresholds, and column dependencies. See Appendix A for the canonical specification.
- For metrics whose required columns do not exist in the current CSV, the metric is marked `unavailable` in `scoring.yaml` and the composite is renormalized over available metrics. The dashboard surfaces this gap in the Glossary page.
- Composite score (0 to 100) and letter grade (A, B, C, D, F) are computed per repo, exposed as `score(repo: str) -> Score` (dataclass with `composite`, `letter`, `per_metric`, `unavailable_metrics`, `config_version`).
- All Repos table has a "Grade" column with colour coding and a colour-blind-safe palette (verified against Coblis simulator: Deuteranopia, Protanopia, Tritanopia).
- Overview shows a grade-distribution histogram.
- Repo Detail shows a per-metric radar chart (9 axes, normalized 0–100). Unavailable metrics render as a hatched outer ring rather than as zero.
- The cross-reference of which metrics are currently computable is in Appendix B and version-controlled with the PRD.
- The displayed grade on every page is accompanied by a small "config v1.0" badge linking to the `scoring.yaml` at the current git SHA.

#### 3.1.10 Discoverability: tooltips and glossary

Check names are opaque to outsiders. A glossary page and inline tooltips remove the onboarding tax.

Acceptance criteria:

- A "Glossary" page lists every check that appears in `dashboard_main.csv`, grouped by category, with: one-sentence description, link to check definition in `edx-repo-health`, link to remediation entry where applicable, and (where mapped) the CHAOSS metric name or OpenSSF Scorecard check ID.
- Glossary content is derived from `dashboard/config/openedx/check_descriptions.yaml`.
- On Repo Detail, each check row has an info-icon tooltip showing the short description.
- The glossary auto-flags checks present in the CSV but missing a description entry, prompting a config update via a "File config-gap issue" button.

#### 3.1.11 "Repos needing attention" view

A standing view that working group leads can open at the start of a meeting and use as the agenda.

Acceptance criteria:

- A dedicated page or Overview section titled "Needing attention" lists repos meeting any of: composite score dropped more than 10 points in 30 days; tier is `critical` and grade is D or F; no commits in 90 days; tier is `important` and 5 or more checks failing; legacy CI signal (`travis_ci.active = True` and `github_actions = False`).
- Each row links to Repo Detail.
- The criteria are configurable in `dashboard/config/openedx/attention_rules.yaml`.
- Tier classifications come from `dashboard/config/openedx/tiers.yaml`. A repo with no tier classification is treated as `standard`.
- The view is deep-linkable: `?tab=needing-attention&tier=critical` filters to critical repos only.

#### 3.1.12 PR template generator (whitelisted checks only)

For a small whitelist of checks where the fix is unambiguous, generate a GitHub PR compare URL with pre-filled title, branch suggestion, and body.

Acceptance criteria:

- `dashboard/config/openedx/pr_templates.yaml` whitelists check names where auto-PR generation is safe. Initial whitelist: `dependabot.exists`, `exists.openedx.yaml`, `github_actions` (basic CI scaffolding).
- For whitelisted failing checks on Repo Detail, an "Open PR with fix" button generates a GitHub `/compare/main...USER:branch?quick_pull=1&title=...&body=...` URL.
- The body explains the fix, links to the remediation entry, notes the dashboard as source, and includes a "Generated by dashboard — please review carefully" header.
- The PR body explicitly **does not** spoof authorship; the user remains the PR author when they click "Create pull request" on the GitHub compare page.
- Non-whitelisted failing checks show the remediation snippet only, no auto-PR button.
- The whitelist is reviewable in the Glossary so contributors know what is automated and what is not.

### 3.2 Phase 2 (deferred but documented)

These are designed for, not implemented in, this PRD. They have stub interfaces in `dashboard/lib/` where appropriate.

- **Badge endpoint (Option B)**. Pre-generation of `dashboards/badges/<repo>.svg` files in a workflow step in `openedx/wg-maintenance`. Served via `raw.githubusercontent.com`. Phase 2 trigger: WG approval to add the workflow step and one external repo adopting the badge in its README.
- **DuckDB SQL query page**. In-process, read-only, query-timeout-enforced, behind a feature flag (`config/feature_flags.yaml: enable_sql_page: false`). Phase 2 trigger: three or more working group members request ad-hoc SQL access.
- **Maintainer and working-group views**. The upstream CSV **already exposes** `ownership.theme`, `ownership.squad`, `ownership.priority`, and `org_name` columns, but as of 2026-05-15 they are populated with empty strings for all 181 rows. Phase 2 trigger: **upstream populates these columns** for a meaningful subset of repos (≥ 20%). No new check is required in `openedx/edx-repo-health`; only the upstream pipeline needs to start populating values from each repo's `openedx.yaml`.
- **"My repos" filter**. GitHub-handle text input; uses the populated `ownership.*` columns once available, or a separate user-to-repos config as a fallback.
- **Year-in-review and OpenGraph cards**. Generated as static HTML pages by a separate workflow step. Phase 2 trigger: requested by WG for annual recap or for forum-post unfurling.
- **Embeddable score cards**. Standalone HTML per-repo pages iframed into discuss.openedx.org. Phase 2 trigger: discuss.openedx.org or similar adopts iframe support and at least one post requests it.
- **OpenSSF Scorecard ingestion**. If a repo has a public Scorecard result, ingest its JSON from `https://api.securityscorecards.dev/projects/github.com/{OWNER}/{REPO}` and surface a parity panel on Repo Detail. Trigger: at least three tracked repos publish Scorecard results.
- **Hetzner self-host migration**. Phase 2 trigger: cold-start complaints from at least two working group members within a 30-day window, or badge endpoint is moved into the dashboard instead of `wg-maintenance`.

### 3.3 Phase 3+ (future, not designed)

- Multi-org tenancy: same codebase, swappable config directory per org. The CSV already has an `org_name` column reserved for this case.
- Contributor and developer data via Perceval-as-subprocess.
- Subscribe-to-this-repo: generated GitHub Actions workflow snippet for repo-side alerting.
- Bulk issue filing across multiple repos for the same check.
- Hosted commercial version with enterprise features (SSO, hosted SLA, alert integrations, audit logs).
- **AI/LLM-assisted remediation explanations**. Where a failing check has no curated remediation entry, an opt-in panel summarizes the check's intent and suggests a fix using a local or hosted LLM. Implemented as a Phase 3 feature flag; all output is clearly labelled as machine-generated and links back to the canonical check definition. Designed with prompt-injection and hallucination mitigations.
- **CHAOSS sub-project standardization**. Donate the open source version to the CHAOSS umbrella to provide governance scaffolding, mirroring GrimoireLab's path.
- **CHAOSS D&I and OSS-Sustainability badging integration**. CHAOSS's DEI Project Badging (Project Access, Inclusive Leadership, Communication Transparency, Newcomer Experience) and the OSS Sustainability toolkit (CHAOSScon 2025) offer org-curated badging frameworks the dashboard could integrate as a Phase 3 metric layer.

---

## 4. Non-Functional Requirements

### 4.1 Performance

- Cold load on Streamlit Community Cloud: under 30 seconds *(community-reported envelope; no official SLA published by Streamlit)*. Warm load: under 3 seconds.
- Snapshot CSV parse: under 2 seconds for current data volume (181 rows × 123 columns as of 2026-05-15; design ceiling is under 1000 rows).
- History load (last 90 daily snapshots): under 15 seconds on first call, cached for 24 hours.
- A single page render: under 1 second after data is cached.
- Largest Contentful Paint target (warm): under 2.5 seconds on a 4G connection (Lighthouse mobile profile).

### 4.2 Accessibility

- Conformance target: **WCAG 2.2 Level AA**, with explicit attention to the success criteria **new in 2.2 vs 2.1**:
  - **2.4.11 Focus Not Obscured (Minimum)** — focused elements must remain at least partially visible; focus outline contrast ≥ 3:1 against the adjacent background.
  - **2.5.7 Dragging Movements** — any drag-to-sort or drag-to-reorder UI must offer a single-pointer alternative (button or keyboard).
  - **2.5.8 Target Size (Minimum)** — interactive targets at least 24×24 CSS pixels; pill buttons, sort handles, and icon-only buttons are explicitly sized.
- All charts have text alternatives or accompanying tables behind the "Show as table" toggle. Every primary chart ships **side-by-side** with a `st.dataframe` tabular equivalent (toggleable).
- Colour choices pass WCAG AA contrast (≥ 4.5:1 for text, ≥ 3:1 for non-text) on the dashboard's brand palette (dark teal #00262B, teal #00B2A9, red #E22D2D). Greens for "pass" are darkened to #166534 (already in current CSS) to maintain contrast.
- The pass/fail palette is **colour-blind-safe**: verified against simulators for Deuteranopia, Protanopia, and Tritanopia. The fail colour uses a saturation/value distinct from pass so it is distinguishable in greyscale.
- Status pills use **both colour and text labels**, never colour alone.
- Keyboard navigation works for tab switching and primary buttons. Full keyboard shortcuts are Phase 2.
- `prefers-reduced-motion` is honoured: animated chart transitions are disabled when the user has the OS preference set.
- Lighthouse accessibility score ≥ 90 on the Overview and Repo Detail pages; axe-core CI step fails on critical violations; a monthly Pa11y CI run is captured in `docs/a11y-history.md`.

### 4.3 Browser support

Latest two major versions of Chrome, Firefox, Safari, Edge. Mobile rendering is functional but desktop is primary. Internet Explorer is unsupported.

### 4.4 Security

- No PII collected. No third-party analytics beyond what Streamlit Cloud provides by default (see §4.8).
- No GitHub API tokens stored or required at runtime; all data comes from public raw URLs and public git log.
- The PR template generator and issue-filing deep links produce URLs only, never API calls.
- The DuckDB SQL page (Phase 2) runs read-only with query timeouts and row caps.
- All third-party links open in new tabs with `rel="noopener noreferrer"`.
- Dependency vulnerability scanning via Dependabot on the dashboard repo itself.
- `bandit` (Python static analysis) runs in CI on `dashboard/`.
- Content Security Policy: Streamlit Cloud's default CSP is accepted; no inline `unsafe-eval` introduced by dashboard code. `unsafe_allow_html=True` is used only in `dashboard/ui/style.py` and `dashboard/ui/banners.py` for trusted, in-repo HTML; user-supplied data is never interpolated into HTML strings.

### 4.5 Internationalization

- English only in Phase 1.
- All user-facing strings live in `dashboard/config/openedx/strings.yaml` to make future translation a config swap.
- Strings are addressed by stable keys (`strings.t("overview.title")`), never inline.
- Date formats use ISO 8601 with explicit UTC suffix (e.g., `2026-05-15 (UTC)`); locale-aware formatting is Phase 2.
- RTL layout support is explicitly out of scope until a tracked org needs it.

### 4.6 Observability

- Streamlit Cloud provides basic uptime and logs.
- A `/healthz` route returns HTTP 200 with snapshot age in seconds, dashboard version, and config-version hash; for external uptime monitors. Implemented as a Streamlit page (`pages/99_healthz.py`) that returns plain text.
- Dashboard logs (stdout, JSON-structured where practical) capture: schema-assertion misses, missing remediation entries, config-load errors, history-fetch durations, cache hit/miss counts.
- A nightly CI job runs against the latest `dashboard_main.csv` and reports any schema drift (new or removed columns) as a GitHub issue auto-labelled `schema-drift`.

### 4.7 Data freshness, staleness, and disaster recovery

- **Freshness banner**: every page renders a banner showing the snapshot `TIMESTAMP` (`YYYY-MM-DD`). If the snapshot is older than 48 hours, the banner colour shifts to amber and reads "Data may be stale". Over 7 days: red and "Data is stale — upstream pipeline may be down" with a link to the `wg-maintenance` repo's workflow runs.
- **Fallback to last-known-good**: if the upstream CSV fetch fails (HTTP error, parse error), the dashboard reads the **previous successful snapshot** from the local `st.cache_data` store and renders with a prominent stale-data banner. The dashboard never renders an empty error page. **This is a new behaviour in PR 2; the current `streamlit_app.py` has no error handling on `requests.get`.**
- **Integrity checks**: schema-shape soft assertions (§6.3) detect malformed snapshots. If the snapshot fails minimum-viability checks (e.g., zero rows, missing `repo_name`, missing `TIMESTAMP`, sudden > 20% drop in row count), the dashboard falls back to the previous snapshot and logs the failure.
- **Disaster recovery runbook** (`docs/RUNBOOK.md`): documents how to manually pin a known-good snapshot URL via `data_source.yaml`, how to redeploy from a tag, and how to bypass the Streamlit Cloud cache.
- **Upstream outage handling**: if `wg-maintenance` is unreachable for 24 hours, the dashboard remains operational on the cached last-known-good snapshot and surfaces a banner directing users to the upstream status page.

### 4.8 Privacy, telemetry, and analytics

- The dashboard collects **no PII** and stores **no user state** server-side.
- Streamlit Community Cloud sets a small number of platform cookies for session management; the dashboard adds none.
- No third-party analytics (Google Analytics, Mixpanel, Plausible) are included in Phase 1.
- The `README.md` and a `docs/PRIVACY.md` make this explicit. `PRIVACY.md` is linked from the footer of every page.
- Streamlit's built-in usage statistics (`gatherUsageStats`) are **disabled** in `.streamlit/config.toml` (`[browser] gatherUsageStats = false`).
- If telemetry is ever added (Phase 2+), it is opt-in, documented, and reflected in `PRIVACY.md`.
- The AGPL-3.0-or-later licensing **requires the operator to publish source for the running version**; the page footer carries a "Source code (AGPL-3.0-or-later)" link to the repository at the deployed commit SHA.

### 4.9 Service-level objectives

These are aspirational targets for an unpaid community deployment, not contractual SLAs. Streamlit Community Cloud's exact resource limits (memory cap, idle-sleep behaviour) are not publicly documented; the numbers below reflect what is plausible on the free tier in mid-2026 based on community reports.

| Objective | Target | Measurement |
|---|---|---|
| Availability (warm path) | 99% over rolling 30 days | External uptime monitor pinging `/healthz` every 5 minutes. |
| Snapshot freshness | Snapshot under 24 hours old at any given time | Banner state distribution across health-check pings. |
| Warm page render (P95) | Under 3 seconds | Lighthouse weekly run. |
| Cold-start (P95) | Under 60 seconds (community-reported envelope) | Triggers Hetzner migration when violated for two consecutive weeks. |

### 4.10 Release management

- **SemVer**: dashboard versions follow `MAJOR.MINOR.PATCH`. Phase 1 ship is `1.0.0`.
- **`CHANGELOG.md`** at repo root, "Keep a Changelog" format.
- Tagged releases on `main` via `git tag` + GitHub Release. Each release ships a `dashboard_version` injected into the `/healthz` payload and footer.
- **Config-version** is independent of dashboard version. `scoring.yaml`'s `version` field bumps when weights, thresholds, or metric definitions change; the grade display links to the exact `scoring.yaml` at that version.
- Backwards-compatibility rule: URL query params follow a deprecation path of two minor versions before removal.

### 4.11 Localization-readiness audit

A Phase 1 gating check: a script (`scripts/check_i18n_readiness.py`) greps `dashboard/`, `pages/`, and `streamlit_app.py` for hardcoded user-facing strings and fails CI if any are found outside `strings.yaml`. Strings inside Python that are dynamic (constructed from check names or repo names) are exempt but must use `strings.t(key).format(...)` rather than f-strings of literals.

---

## 5. Repository Boundaries

### 5.1 `UsamaSadiq/org-health-dashboard`

All Phase 1 work lands here. Includes the LICENSE change to AGPL-3.0-or-later, the CLA workflow via cla-assistant.io, all new modules under `dashboard/`, all config under `dashboard/config/openedx/`, the test suite, the CI workflow that runs tests on PR.

License migration note: the existing code is currently under no explicit license. The first PR of Phase 1 adds `LICENSE` (AGPL-3.0-or-later), `NOTICE`, `CLA.md`, and the cla-assistant configuration. All current code is Usama's, so the relicensing is unilateral and clean. Any future contributor must sign the CLA before merge (with a DCO fast path for trivial contributions, defined in §10.5).

### 5.2 `openedx/wg-maintenance`

No changes in Phase 1.

Documented Phase 2 change: addition of a `generate_badges` step to the existing daily workflow that writes SVGs to `dashboards/badges/<repo>.svg` after `dashboard_main.csv` is committed. This change requires Maintenance Working Group approval and is filed as a separate WG issue when the Phase 2 trigger fires.

Documented Phase 2 data dependency: the upstream pipeline already exposes `ownership.theme`, `ownership.squad`, `ownership.priority`, and `org_name` columns but populates them with empty strings. The maintainer-view and "My repos" features require this data to be populated. The Phase 2 trigger reflects the pipeline change, not a check change.

### 5.3 `openedx/edx-repo-health`

No changes in this PRD.

Documented future dependency: the Phase 1 9-metric scoring formula has four metrics currently marked `unavailable` (PR response time, PR closure ratio, release frequency, contributor absence factor) because the underlying columns are not in `dashboard_main.csv`. If/when Phase 2 work requires them, separate issues are filed against `openedx/edx-repo-health` proposing new checks. That work follows normal Open edX contribution flow and is not part of this PRD's deliverables.

---

## 6. Configuration Schema

### 6.1 Directory structure

```
dashboard/config/
├── README.md                            # schema documentation (auto-generated from JSON Schemas)
├── feature_flags.yaml                   # global feature toggles
├── schemas/                             # JSON Schemas for every config file
└── openedx/                             # org-specific config (replaceable)
    ├── data_source.yaml                 # where to read dashboard_main.csv
    ├── check_groups.yaml                # category groupings for display
    ├── check_descriptions.yaml          # glossary text per check
    ├── remediation.yaml                 # fix snippets per check
    ├── pr_templates.yaml                # auto-PR whitelist
    ├── scoring.yaml                     # 9-metric weights and thresholds
    ├── tiers.yaml                       # repo tier classifications
    ├── attention_rules.yaml             # "needs attention" criteria
    ├── strings.yaml                     # i18n-ready UI strings
    └── org_branding.yaml                # logo, colors, tagline
```

### 6.2 Schemas (excerpt)

**`data_source.yaml`**

```yaml
csv_url: "https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_main.csv"
history_repo: "openedx/wg-maintenance"
history_path: "dashboards/dashboard_main.csv"
history_days: 90
cache_ttl_seconds: 300
fallback_to_last_known_good: true
stale_threshold_hours: 48
critically_stale_threshold_hours: 168
expected_min_rows: 100         # below this triggers integrity fallback
expected_min_columns: 100      # below this triggers integrity fallback
```

**`check_groups.yaml`**

```yaml
groups:
  - name: "File Existence"
    pattern: "exists\\..*"
    explicit: ["exists.README", "exists.openedx.yaml", ...]
  - name: "CI / Tooling"
    pattern: "^(github_actions|renovate\\..*|dependabot\\..*|makefile\\..*)$"
  ...
```

`pattern` and `explicit` are alternatives; if both present, `explicit` wins.

**`remediation.yaml`**

```yaml
checks:
  dependabot.exists:
    title: "Add Dependabot configuration"
    description: "Dependabot keeps dependencies updated and surfaces security advisories."
    source_url: "https://github.com/openedx/.github/blob/main/dependabot.yml"
    snippet: |
      version: 2
      updates:
        - package-ecosystem: "pip"
          directory: "/"
          schedule:
            interval: "weekly"
    applies_to_tiers: ["critical", "important", "standard"]
    chaoss_metric: "Maintained"
    scorecard_check: "Dependency-Update-Tool"
  exists.openedx.yaml:
    title: "Add openedx.yaml"
    description: "..."
    source_url: "..."
    snippet: "..."
```

**`scoring.yaml`** (excerpt — full canonical spec in Appendix A)

```yaml
version: "1.0"
letter_grades:
  A: [80, 100]
  B: [60, 79]
  C: [40, 59]
  D: [20, 39]
  F: [0, 19]
metrics:
  commit_recency:
    weight: 0.15
    column: "github.last_push"
    type: "days_ago"
    parse_format: "%Y-%m-%d %H:%M:%S"     # naive, treated as UTC
    thresholds: [{days: 7, score: 100}, {days: 30, score: 80}, {days: 90, score: 50}, {days: 365, score: 20}]
    default_when_missing: 50
    status: "computable"
    chaoss_metric: "Code Changes"
  pr_response_time:
    weight: 0.15
    column: "github.median_pr_response_seconds"
    status: "unavailable"   # not yet in upstream CSV
    chaoss_metric: "Issue Response Time"
    scorecard_check: null
  contributor_absence_factor:
    weight: 0.10
    column: "github.contributor_count_90d"
    status: "unavailable"
    chaoss_metric: "Contributor Absence Factor"
    aliases: ["Bus Factor", "Elephant Factor"]
    scorecard_check: "Contributors"
```

**`feature_flags.yaml`**

```yaml
enable_sql_page: false
enable_badge_links: false           # set true when Phase 2 badge endpoint is live
enable_compare_mode: true
enable_pr_template_generator: true
enable_weekly_bulletin_export: true
enable_scorecard_panel: false       # Phase 2
enable_llm_remediation: false       # Phase 3
```

### 6.3 Schema validation strategy

- Each YAML config file has an accompanying **JSON Schema** in `dashboard/config/schemas/<name>.schema.json`.
- `dashboard/lib/schema.py` validates every config file on load. Validation errors **fail loud** in CI but are downgraded to logged warnings at runtime (the dashboard stays up with the last-known-good config).
- CI runs `pytest tests/test_config_schemas.py` on every PR.
- `dashboard/config/README.md` is the single source of truth for schema conventions and is regenerated from the JSON Schemas via a `make docs-config` target.

---

## 7. File Structure (target)

```
org-health-dashboard/
├── LICENSE                              # AGPL-3.0-or-later
├── NOTICE
├── CLA.md
├── CHANGELOG.md
├── README.md                            # rewritten, portfolio-quality
├── streamlit_app.py                     # < 100 lines, orchestrator only
├── requirements.txt                     # all pinned
├── requirements-dev.txt
├── runtime.txt                          # python-3.12
├── pyproject.toml                       # ruff, mypy, pytest config
├── Makefile
├── .streamlit/
│   └── config.toml                      # gatherUsageStats = false; theme
├── .github/
│   └── workflows/
│       ├── ci.yml                       # tests, lint, type-check, axe-core, bandit
│       ├── cla-assistant.yml            # CLA enforcement
│       ├── schema-drift.yml             # nightly upstream CSV check
│       └── release.yml                  # tag + changelog automation
├── pages/
│   ├── 01_overview.py
│   ├── 02_repo_detail.py
│   ├── 03_failing_checks.py
│   ├── 04_needing_attention.py
│   ├── 05_what_changed.py
│   ├── 06_glossary.py
│   └── 99_healthz.py
├── dashboard/
│   ├── __init__.py
│   ├── data.py                          # load_snapshot, load_history, load_config
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── kpi.py
│   │   ├── tables.py
│   │   ├── charts.py
│   │   ├── banners.py                   # freshness/stale-data banner
│   │   └── style.py                     # CSS + brand colors
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── scoring.py
│   │   ├── trends.py
│   │   ├── remediation.py
│   │   ├── linking.py
│   │   ├── badge.py                     # stub for Phase 2
│   │   ├── bulletin.py
│   │   └── schema.py                    # canonical constants: REPO_COL, TIMESTAMP_COL, LAST_PUSH_COL, parse_format hints
│   └── config/
│       ├── README.md
│       ├── feature_flags.yaml
│       ├── schemas/                     # JSON Schemas for all configs
│       └── openedx/
│           ├── data_source.yaml
│           ├── check_groups.yaml
│           ├── check_descriptions.yaml
│           ├── remediation.yaml
│           ├── pr_templates.yaml
│           ├── scoring.yaml
│           ├── tiers.yaml
│           ├── attention_rules.yaml
│           ├── strings.yaml
│           └── org_branding.yaml
├── scripts/
│   └── check_i18n_readiness.py
├── tests/
│   ├── test_scoring.py
│   ├── test_trends.py
│   ├── test_linking.py
│   ├── test_schema.py
│   ├── test_remediation.py
│   ├── test_config_schemas.py
│   └── fixtures/
│       └── dashboard_main_sample.csv
├── docs/
│   ├── PRD.md                           # v1, retained for history
│   ├── PRD_v2.md                        # retained for history
│   ├── PRD_v3.md                        # this document
│   ├── ARCHITECTURE.md
│   ├── CONTRIBUTING.md
│   ├── DEPLOYMENT.md
│   ├── GOVERNANCE.md
│   ├── PRIVACY.md
│   ├── RUNBOOK.md
│   └── SCORING.md                       # human-readable scoring methodology
└── assets/
    └── style.css                        # extracted from inline CSS
```

---

## 8. Implementation Plan

### 8.1 PR sequencing

| PR | Title | Scope | Estimated effort |
|---|---|---|---|
| 1 | Licensing and CLA | Add `LICENSE` (AGPL-3.0-or-later), `NOTICE`, `CLA.md`, configure cla-assistant.io, add `CONTRIBUTING.md`, `GOVERNANCE.md`, `PRIVACY.md`. No code changes. | 0.5 day |
| 2 | Architectural refactor + resilience | Split into `dashboard/lib/`, `dashboard/ui/`, `pages/`, move config to YAML, add `tests/`, JSON Schemas, freshness banner, fallback-to-last-known-good, **error handling on the CSV fetch (currently absent in shipped code)**. No UX behaviour changes beyond banner. | 4 to 6 days |
| 3 | Visualizations-first + URL state | Overview gets charts, Repo Detail becomes URL-first and search-first, all filter state moves to query params (using Streamlit 1.55+ widget `bind=` for simple state, explicit serialize/deserialize in `linking.py` for compound state). Compare mode shipped. `st.column_config.LinkColumn` adopted. | 4 to 6 days |
| 4 | Trend dimension | History reading, "What changed this week" tab, sparklines, weekly bulletin export. | 4 to 5 days |
| 5 | Scoring + discoverability + action loops | 9-metric scoring, grade column, radar chart, glossary, tooltips, remediation snippets, issue-filing links, PR template generator, "needing attention" view. | 5 to 7 days |

Total estimated effort: 17.5 to 24.5 days of part-time engineering, plus review cycles. Calendar duration of four to six weeks assuming the project is one of several active commitments.

### 8.2 Migration safety

- Each PR is independently deployable. After every PR, the live dashboard at `share.streamlit.io` continues to render.
- PR 2 (refactor) is the riskiest because it touches everything. Acceptance criteria include a screenshot diff: the pre-refactor and post-refactor dashboards must render visually identically *after* the new freshness banner is accepted as a single intentional visual change.
- PR 3 changes the URL parameter scheme. Old shared links remain valid through a redirect map in `linking.py` for two minor versions.
- Feature flags in `feature_flags.yaml` allow disabling any new surface if a regression ships to production.
- Every PR ships behind at least one feature flag where user-visible. Feature flags default to "on" only after the PR has soaked on `main` for at least 24 hours without a rollback.

### 8.3 Definition of Done

Every PR must satisfy the following before merge:

- [ ] CI green: unit tests, schema-validation tests, `ruff`, `mypy` (on `dashboard/lib/`), `bandit`, `axe-core` (where pages render).
- [ ] Coverage delta on `dashboard/lib/` is non-negative.
- [ ] Manual smoke pass: dashboard renders Overview, Repo Detail (with `?repo=edx-platform`), Failing Checks, Glossary without console errors.
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`.
- [ ] Any new user-facing string is in `strings.yaml`.
- [ ] Any new config file has a JSON Schema and a section in `dashboard/config/README.md`.
- [ ] Any new external link opens with `rel="noopener noreferrer"`.
- [ ] PR description names which feature flag (if any) gates the change.

---

## 9. Acceptance Criteria

Cross-cutting, in addition to the per-feature criteria in Section 3:

- [ ] CI passes: tests, lint (`ruff`), type-check (`mypy` on `dashboard/lib/`), `bandit`, `axe-core`.
- [ ] CLA bot is configured and gating merges on `main` (DCO fast path for trivial contributions, per §10.5).
- [ ] All Open-edX-specific strings live in `dashboard/config/openedx/`.
- [ ] A `grep -ri "openedx" dashboard/lib/ dashboard/ui/ pages/ streamlit_app.py` returns zero matches (the only `openedx` references are in `config/openedx/`, the README, and the documentation).
- [ ] The `tests/` suite covers `lib/` modules to at least 80 percent line coverage.
- [ ] The dashboard renders without a crash when given a CSV missing 20 percent of expected columns (schema-shape soft assertion).
- [ ] The dashboard renders the last-known-good snapshot with a stale-data banner when the upstream CSV is unreachable.
- [ ] No tab's default view is a wide data grid.
- [ ] Every primary view is deep-linkable via URL params.
- [ ] Lighthouse accessibility score ≥ 90 on Overview and Repo Detail.
- [ ] WCAG 2.2 AA criteria 2.4.11, 2.5.7, 2.5.8 verified by manual keyboard and visual audit, documented in `docs/a11y-history.md`.
- [ ] `PRIVACY.md` is linked from the page footer.
- [ ] AGPL source-code link in page footer points at the deployed commit SHA.
- [ ] `gatherUsageStats = false` is set in `.streamlit/config.toml`.
- [ ] At least one community announcement is drafted, ready to post to discuss.openedx.org once Phase 1 is live.

---

## 10. Risk Register

Risks are ordered by composite likelihood and impact. Each entry includes a mitigation and an owner.

### 10.1 Upstream check schema drift

**Risk**: `openedx/edx-repo-health` renames or removes a check, breaking dashboard references like `dependabot.exists`.

**Likelihood**: medium. Check names have been stable historically, but renames have happened.

**Impact**: medium. A renamed check disappears from the dashboard silently, or causes a hardcoded reference (KPI strip, scoring formula) to break.

**Mitigation**:
- `dashboard/lib/schema.py` performs a soft schema assertion at load time and logs every expected column that is missing.
- Prefix-based group iteration (`exists.*`, `dependabot.*`) handles additions and removals gracefully.
- KPIs that depend on specific columns degrade to "N/A" rather than crashing.
- Scoring metrics whose required columns disappear are marked `unavailable` and the composite renormalizes over the remaining metrics.
- A nightly CI job runs against the latest `dashboard_main.csv` and reports any schema misses to a GitHub issue auto-labelled `schema-drift`.

**Owner**: dashboard maintainer.

### 10.2 CSV size growth degrading performance

**Risk**: As `openedx/edx-repo-health` adds more checks and the org adds more tracked repos, `dashboard_main.csv` grows. At some point, fetching and parsing it on every cache miss becomes too slow.

**Likelihood**: low to medium over a multi-year horizon. The live CSV is currently 181 rows × 123 columns; design ceiling is roughly 1000 rows × 300 columns before a Parquet migration is warranted.

**Impact**: medium. Slow cold-start, possible Streamlit Cloud memory limits (memory cap is not publicly documented).

**Mitigation**:
- `st.cache_data(ttl=300)` keeps repeated parses cheap.
- If the CSV exceeds 5MB or 5000 rows, switch the upstream pipeline (a `wg-maintenance` change, out of this PRD's scope) to also publish Parquet, which the dashboard reads preferentially.
- DuckDB (Phase 2) reads Parquet natively and would absorb this growth.

**Owner**: dashboard maintainer, with escalation to `wg-maintenance` for upstream Parquet emission.

### 10.3 Git history reading performance and rate limits

**Risk**: Reading the git log of `dashboards/dashboard_main.csv` via GitHub's REST API on every history-cache miss is slow and consumes GitHub API rate limits (60 requests/hour unauthenticated).

**Likelihood**: high if implemented naively.

**Impact**: medium. Slow first-load of trend tabs; possible 403 from GitHub for anonymous traffic during refresh storms.

**Mitigation**:
- History is cached for 24 hours via `st.cache_data(ttl=86400)`.
- Use the unauthenticated REST API (`https://api.github.com/repos/.../commits?path=...`) for commit list, then fetch individual blobs only as needed.
- Cap history to the last 90 days; older snapshots are accessible only via direct GitHub browsing.
- Phase 2 alternative: pre-compute a `dashboards/history.json` file in `openedx/wg-maintenance` as a separate workflow step, and the dashboard reads that file in a single request. Out of Phase 1 scope but documented.

**Owner**: dashboard maintainer.

### 10.4 Streamlit Cloud cold starts and undocumented limits

**Risk**: Streamlit Community Cloud sleeps after idle. First user after sleep waits (community-reported) 15 to 30 seconds. Memory limits are also undocumented.

**Likelihood**: high for sporadically-used dashboards.

**Impact**: low to medium. Annoying but not blocking.

**Mitigation**:
- Treat cold-start and memory figures as community-reported envelopes, not contractual.
- Documented Phase 2 trigger: move to Hetzner CX22 when cold starts become a recurring complaint (≥ 2 WG members in 30 days) or when the dashboard hits an undocumented memory limit.
- An optional GitHub Actions workflow that pings the dashboard URL every six hours keeps the app warm. Implemented as a documented opt-in, not enabled by default to avoid burning Streamlit Cloud's free-tier budget.
- If Streamlit's Open-Source / nonprofit allowance is available, request a quota bump citing Open edX status.

**Owner**: dashboard maintainer.

### 10.5 CLA friction with community contributors (and the DCO debate)

**Risk**: Some open source contributors refuse to sign a CLA on principle. OpenStack notably **replaced its CLA with a DCO effective 2025-07-01**, citing exactly this friction. The dashboard could lose contributions that would otherwise come in.

**Likelihood**: medium.

**Impact**: medium. A few high-value contributions might be lost.

**Mitigation**:
- The CLA is plain, modeled on Apache ICLA, e-signable via GitHub auth in under one minute.
- `CONTRIBUTING.md` explains the dual-license rationale plainly, **including a short explanation of why this project's situation (single-owner relicensing flexibility for a future commercial path) differs from OpenStack's (where productization was not on the table)**.
- Trivial contributions (typo fixes, documentation patches under a defined threshold) are accepted under the DCO instead of the CLA. The threshold is explicit in `CONTRIBUTING.md`: documentation-only changes, single-file changes under 50 modified lines that do not touch `dashboard/lib/`, and translation strings.
- The CLA assignment is to a named project entity, not to a commercial company.
- The CLA-vs-DCO decision is revisited if Phase 2 lands and the maintainer pool grows beyond two people, or if Axim/Open edX governance issues a project-wide guidance.

**Owner**: dashboard maintainer.

### 10.6 Repository namespace and ownership tension

**Risk**: The repository is in `UsamaSadiq/org-health-dashboard`, a personal namespace. Open edX governance may expect official tooling to live in `openedx/`.

**Likelihood**: medium.

**Impact**: medium to high. Decisions here are hard to reverse.

**Mitigation**:
- Phase 1 stays in `UsamaSadiq/` to retain control during the foundational period.
- Once Phase 1 ships and the dashboard has demonstrable community value, propose creating an `openedx-community-tools/` organization.
- Transfer terms: AGPL retained, CLA retained (subject to §10.5), governance documented, productization path explicitly preserved.

**Owner**: project owner (Usama).

### 10.7 Productization conflict with Open edX community expectations

**Risk**: A community observer realizes that the open source dashboard is also positioned for a future commercial product, and feels misled.

**Likelihood**: medium over a multi-year horizon.

**Impact**: medium to high. Community trust is hard to rebuild.

**Mitigation**:
- Be explicit from day one in `README.md`, `CONTRIBUTING.md`, `LICENSE`, and `GOVERNANCE.md`.
- The open source version is, and remains, fully functional and self-hostable.
- Any commercial features are additive on top of the open source baseline (Grafana-style "open core"), not BSL-style "use restrictions".
- The 2024–2026 record of failed re-licensing attempts (Redis → Valkey, HashiCorp → OpenTofu) is a cautionary tale; the AGPL-plus-CLA model avoids those traps by keeping the OSI-approved license intact.

**Owner**: project owner.

### 10.8 Bus factor of one

**Risk**: The dashboard depends on a single maintainer. Vacations, job changes, or burnout cause stagnation. (Note: CHAOSS now calls this *Contributor Absence Factor*; the colloquial name is retained here.)

**Likelihood**: certain in the long run.

**Impact**: medium to high.

**Mitigation**:
- All operational knowledge in `docs/DEPLOYMENT.md` and `docs/RUNBOOK.md`.
- Phase 2 trigger: actively recruit a second maintainer when the dashboard has been live for six months and has at least one PR from a non-Usama contributor.
- Eventual transfer to a multi-maintainer organization (see 10.6).

**Owner**: project owner.

### 10.9 PR template generator producing low-quality PRs

**Risk**: The auto-PR generator creates PRs that fail tests, lack context, or get rejected by repo maintainers, eroding trust.

**Likelihood**: medium.

**Impact**: medium.

**Mitigation**:
- Whitelist starts at three checks where the fix is mechanical and unambiguous.
- The PR body explicitly labels the PR as "Dashboard-generated, please review carefully" and links to the dashboard.
- The dashboard opens GitHub's compare view with `quick_pull=1`; the user must click "Create pull request" — the dashboard is not autonomous and never acts as the PR author.
- The whitelist is reviewed monthly. Checks added only after manual validation against three or more real repos.

**Owner**: dashboard maintainer.

### 10.10 Scoring formula contested by community

**Risk**: The 9-metric weights are opinionated. A working group member disagrees with, say, the 15 percent weight on commit recency.

**Likelihood**: medium.

**Impact**: low.

**Mitigation**:
- The scoring formula is fully in `dashboard/config/openedx/scoring.yaml`. Disagreement leads to a PR, not a code change.
- The glossary page documents every weight and threshold and cross-references CHAOSS (current names) and OpenSSF Scorecard where applicable.
- An "Alternative scoring" config could be added in Phase 2.
- The dashboard surfaces the scoring config version next to every grade.

**Owner**: dashboard maintainer, with WG input on weights.

### 10.11 Plotly bundle size and rendering performance

**Risk**: Plotly is approximately 3MB compressed. First-load time on slow connections is meaningful.

**Likelihood**: low.

**Impact**: low.

**Mitigation**:
- Accept for Phase 1.
- If complaints arise, evaluate Altair or `streamlit-echarts`. Phase 2 only.

**Owner**: dashboard maintainer.

### 10.12 DuckDB SQL page abuse (Phase 2 risk)

**Risk**: An open SQL textarea on a public dashboard could be used to DoS the server with expensive queries.

**Likelihood**: medium if exposed naively.

**Impact**: medium.

**Mitigation**:
- Hard query timeout (5 seconds) via DuckDB pragmas.
- Row cap on result set (10000).
- Memory cap on DuckDB connection.
- Feature-flagged behind `enable_sql_page` (false by default).
- Phase 2 only; not implemented in this PRD.

**Owner**: dashboard maintainer at Phase 2 implementation time.

### 10.13 Time zone handling

**Risk**: Snapshot timestamps and weekly-bulletin dates can be confusing across time zones. `github.last_push` in the upstream CSV is a naive `YYYY-MM-DD HH:MM:SS` string with no timezone marker.

**Likelihood**: medium.

**Impact**: low.

**Mitigation**:
- `dashboard/lib/schema.py` documents the canonical parser: `github.last_push` is parsed as naive and **treated as UTC**.
- All internal timestamps in UTC.
- User-facing timestamps formatted in UTC with explicit "(UTC)" suffix.
- Week boundaries for "what changed this week" are Monday 00:00 UTC.

**Owner**: dashboard maintainer.

### 10.14 Mobile rendering

**Risk**: Streamlit's mobile layout is functional but not polished.

**Likelihood**: high for occasional mobile usage.

**Impact**: low.

**Mitigation**:
- CSS adjustments in `assets/style.css` for narrow viewports.
- Tables are horizontally scrollable on mobile.
- Heavy charts collapse to tabular fallback below 768px viewport width.
- Mobile is explicitly secondary; desktop remains the design target.
- WCAG 2.2 **Target Size 24×24** (§4.2) constrains the mobile UI in the right direction.

**Owner**: dashboard maintainer.

### 10.15 Config schema drift

**Risk**: The YAML config files accumulate inconsistencies over time.

**Likelihood**: medium.

**Impact**: low to medium.

**Mitigation**:
- JSON Schema for each config file, validated at load time and in CI (see §6.3).
- `dashboard/config/README.md` is the single source of truth and is regenerated from the schemas.

**Owner**: dashboard maintainer.

### 10.16 Upstream CSV silent corruption

**Risk**: `dashboard_main.csv` is committed by an automated workflow. A bug in the workflow could publish a corrupted snapshot (zero rows, truncated content, malformed quoting, an empty `repo_name` column) without any human noticing.

**Likelihood**: low but non-zero.

**Impact**: high. The dashboard becomes the most visible symptom of the upstream failure.

**Mitigation**:
- Minimum-viability checks at load time: `repo_name` column present and non-empty for ≥ 95% of rows, `TIMESTAMP` column present, at least `expected_min_rows` (default 100) rows, at least `expected_min_columns` (default 100) columns.
- On failure, fall back to the previous successful snapshot (cached in `st.cache_data`) and surface a red banner linking to the `wg-maintenance` workflow runs page.
- Nightly CI cross-checks the upstream CSV against the last 7 snapshots; significant row-count deltas (more than 20% drop) raise a `schema-drift` issue.

**Owner**: dashboard maintainer; escalation to `wg-maintenance` owners.

### 10.17 Accessibility regression

**Risk**: A future PR introduces a colour-only status indicator, a chart without a tabular fallback, a Streamlit component with poor keyboard support, or a non-conforming target size.

**Likelihood**: medium over multi-year horizon.

**Impact**: medium.

**Mitigation**:
- CI step: `axe-core` runs against Overview and Repo Detail pages on every PR; critical violations fail the build.
- Monthly Pa11y CI run, archived in `docs/a11y-history.md`.
- WCAG 2.2 AA conformance (including 2.4.11, 2.5.7, 2.5.8) is a release gate, not a nice-to-have.

**Owner**: dashboard maintainer.

### 10.18 Streamlit / Plotly upstream API breakage

**Risk**: Streamlit's release cadence is high. A `1.58.x` or `1.60.x` release could remove an API the dashboard depends on (`st.fragment`, `st.dialog`, widget `bind=`, `on_select`). v3 already absorbs one such change cycle (the 2026 removal of `st.experimental_get_query_params`).

**Likelihood**: medium over a 12-month window.

**Impact**: low to medium.

**Mitigation**:
- Pin Streamlit to a specific minor (`==1.57.*` or similar) in `requirements.txt`; bump only after CI runs against the new version against `tests/fixtures/dashboard_main_sample.csv` and the dashboard renders cleanly.
- A `tests/test_streamlit_apis.py` smoke test imports each used API and asserts the symbol exists; this fails fast on upstream removal.
- `CHANGELOG.md` calls out the Streamlit pin bump every time it changes.

**Owner**: dashboard maintainer.

---

## 11. Open Questions

Unresolved decisions deferred to implementation or explicitly punted.

1. **Whether to add a `dashboards/history.json` file to `openedx/wg-maintenance`** as a pre-computed history artefact. Decision: stays in Phase 1 as live git-log reading; revisit if performance is unacceptable.
2. **Tier classifications source**. Decision: ships as `dashboard/config/openedx/tiers.yaml`, hand-maintained for now. May be replaced by the `ownership.priority` column once upstream populates it.
3. **"Working group" attribution per repo**. Decision: out of Phase 1; revisit when `ownership.theme` / `ownership.squad` are populated upstream (the columns exist; values are empty).
4. **Whether to publish to PyPI**. Decision: not in Phase 1; consider in Phase 3.
5. **Custom domain**. `repo-health.openedx.org` would be ideal but requires Axim subdomain provisioning. Decision: ask Axim once Phase 1 ships and has been live for one month.
6. **Slack-bot integration**. Decision: Phase 3.
7. **Telemetry on dashboard usage**. Decision: rely on Streamlit Cloud's built-in metrics only; no third-party analytics in Phase 1. Streamlit's own `gatherUsageStats` is disabled (§4.8).
8. **OpenSSF Scorecard JSON ingestion**. If/when a meaningful subset of tracked repos publishes a Scorecard result, would we ingest the JSON via `https://api.securityscorecards.dev` and surface a parity panel? Decision: Phase 2 trigger.
9. **AI/LLM remediation**. The technology and cost model are evolving rapidly. Decision: Phase 3, feature-flagged, opt-in only.
10. **Snapshot retention policy**. The `wg-maintenance` repo keeps full history in git. Should the dashboard cap the displayed window to 90 days, or expose deeper history? Decision: 90 days in Phase 1; deeper history is a Phase 2 enhancement once DuckDB is in.
11. **CLA vs DCO project-wide**. v3 retains CLA with a DCO fast path for trivial contributions. Revisited if (a) project moves into the `openedx/` org, (b) maintainer pool grows beyond two, or (c) Open edX governance issues a default position.

---

## 12. Future Work (Phase 3+)

Items captured for traceability, not designed in detail.

- **Multi-tenant hosted version**. Same codebase, managed control plane, per-org config in a database. The `org_name` column reserved upstream supports this.
- **Enterprise commercial features**. SSO via SAML/OIDC, hosted SLAs, alert integrations (PagerDuty, Opsgenie), audit logs, branded white-labeling.
- **Contributor and developer data via Perceval-as-subprocess**. JSON read by the dashboard, license boundary clean.
- **GitHub App version** that can run inside org admin tooling, with write access to file PRs and tag issues directly. Requires careful threat modeling.
- **AI/LLM-assisted remediation explanations**. Local/hosted LLM summarizes failing checks. Opt-in feature flag; clearly labelled as machine-generated; prompt-injection mitigations documented.
- **CHAOSS DEI Project Badging integration**. Map the four CHAOSS DEI badges (Project Access, Inclusive Leadership, Communication Transparency, Newcomer Experience) into the dashboard as an additional org-curated metric layer.
- **CHAOSS OSS Sustainability toolkit** (CHAOSScon 2025) integration.
- **Standardize as a CHAOSS sub-project**. The Linux Foundation CHAOSS umbrella is a natural governance home.
- **OpenSSF Scorecard integration**. Ingest Scorecard JSON and surface a parity panel.

---

## Appendix A: 9-Metric Scoring Specification

The composite health score is a weighted average of nine normalized metrics, each scored 0 to 100, with weights summing to 1.0. Metrics whose required columns are not present in `dashboard_main.csv` are marked `unavailable` and the composite is renormalized over the remaining metrics.

| # | Metric | Weight | Source column(s) | CHAOSS / Scorecard cross-reference | Computation |
|---|---|---|---|---|---|
| 1 | Commit recency | 0.15 | `github.last_push` | CHAOSS *Code Changes* | Days since last push. 100 if under 7, 80 if under 30, 50 if under 90, 20 if under 365, 0 otherwise. Parser hint: `%Y-%m-%d %H:%M:%S`, naive, treated as UTC. |
| 2 | PR response time | 0.15 | `github.median_pr_response_seconds` (currently unavailable) | CHAOSS *Issue Response Time* | Median time to first comment on PRs in last 90 days. 100 if under 1d, 80 if under 3d, 50 if under 7d, 20 if under 30d, 0 otherwise. |
| 3 | PR closure ratio | 0.15 | `github.pr_closure_ratio_90d` (currently unavailable) | CHAOSS *Change Request Closure Ratio* | Ratio of merged or closed PRs to opened PRs in last 90 days. 100 if above 0.8, 80 if above 0.6, 50 if above 0.4, 20 if above 0.2, 0 otherwise. |
| 4 | Release frequency | 0.10 | `github.release_count_12mo` (currently unavailable) | CHAOSS *Release Frequency*; OpenSSF *Signed-Releases* (partial) | 100 if monthly or better, 80 if quarterly, 50 if semi-annual, 20 if annual, 0 if none in last 12 months. |
| 5 | Contributor Absence Factor (formerly Bus Factor) | 0.10 | `github.contributor_count_90d` (currently unavailable) | CHAOSS *Contributor Absence Factor*; OpenSSF *Contributors* | Distinct contributors in last 90 days. 100 if above 5, 80 if above 3, 50 if above 2, 20 if exactly 2, 0 if 1 or fewer. |
| 6 | README quality | 0.10 | `readme.*` columns | — | 100 if all `readme.*` checks pass, deduct 10 points per failing check, floor at 0. |
| 7 | CI status | 0.10 | `github_actions` | OpenSSF *CI-Tests* | 100 if true, 0 if false, 50 if unknown. |
| 8 | `openedx.yaml` compliance | 0.10 | `exists.openedx.yaml` plus future schema-check column | — (org-specific) | 100 if exists and valid, 50 if exists, 0 if missing. |
| 9 | Dependency freshness | 0.05 | `dependabot.*`, `renovate.configured`, optionally `renovate.oldest_open_pr_date` | OpenSSF *Dependency-Update-Tool*, *Pinned-Dependencies*, *Vulnerabilities* | 100 if Dependabot or Renovate configured and active across all relevant ecosystems; scaled down by gaps and by age of oldest open Renovate PR. |

**Missing data default**: 50 (not 0) for any individual metric whose column exists but is null on a specific repo.

**Letter grade thresholds**: A=80–100, B=60–79, C=40–59, D=20–39, F=0–19.

**Renormalization rule**: if metrics with combined weight W are unavailable, the remaining weights are scaled by 1/(1-W).

**Phase 1 effective composite**: metrics 1, 6, 7, 8, 9 are computable from the live CSV (combined nominal weight 0.50, renormalized to 1.0). Metrics 2, 3, 4, 5 are tracked as `unavailable` until upstream surfaces the columns.

The full CHAOSS metric definitions live at https://chaoss.community/kb-metrics-and-metrics-models/. OpenSSF Scorecard check definitions live at https://github.com/ossf/scorecard/blob/main/docs/checks.md.

---

## Appendix B: Column Dependency Matrix (revised against the live CSV)

This matrix records which columns in `dashboard_main.csv` are used by the dashboard, as of the 2026-05-08 snapshot (181 rows × 123 columns). The reference is the live URL https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_main.csv.

### B.1 Columns used in Phase 1

| Column | Type | Phase 1 use |
|---|---|---|
| `repo_name` | string | **Canonical repo identifier.** Constant: `dashboard.lib.schema.REPO_COL`. Includes the `owner/` prefix in shipped data (e.g., `openedx/edx-when`). |
| `TIMESTAMP` | `YYYY-MM-DD` date string | **Snapshot date.** Constant: `dashboard.lib.schema.TIMESTAMP_COL`. Parser: `datetime.date.fromisoformat`. |
| `github.description` | string | Overview display, search index. |
| `github.last_push` | `YYYY-MM-DD HH:MM:SS` naive string | Metric 1 (commit recency). Parsed as UTC. |
| `github.pulls_count` | int | Repo Detail metadata. |
| `github.fork_count` | int | Repo Detail metadata. |
| `github.is_archived` | bool | Active/archived filter. |
| `github.license` | string | Repo Detail metadata. |
| `github_actions` | bool | Metric 7 (CI status). |
| `exists.*` (multiple) | bool | Metric 8 (openedx.yaml), various checks in Failing Checks tab. |
| `dependabot.*` (multiple) | bool | Metric 9 (dependency freshness), Failing Checks. |
| `readme.*` (`readme.getting-help`, `readme.security`, `readme.bad_links`, `readme.good_links`, `readme.irc-missing`, `readme.mailing-list-missing`) | bool | Metric 6 (README quality), computed over present columns. |
| `renovate.configured` | bool | Glossary; alt-CI signal; feeds into Metric 9. |
| `pinned_python_dependencies` | bool | Glossary; quality signal. |
| `readthedocs_config.exists`, `docs.build_badge` | bool | Docs category. |
| `makefile.*` (multiple) | bool | CI/tooling category. |

### B.2 Columns reserved for Phase 2 (present, currently empty)

| Column | Type | Phase 2 use |
|---|---|---|
| `ownership.theme` | string (empty for all 181 rows on 2026-05-08) | Maintainer / theme view. Phase 2 trigger: upstream populates. |
| `ownership.squad` | string (empty) | Maintainer / squad view. |
| `ownership.priority` | string (empty) | May replace `tiers.yaml` as the source of truth for tier. |
| `org_name` | string (only `openedx` currently observed; presently identical for all rows) | Multi-org future (Phase 3). |

### B.3 Columns catalogued but not currently consumed

These columns are in the CSV and represent opportunity for future enrichment without requiring upstream changes. Listed here so future PRs can pick them up:

| Column(s) | Possible future use |
|---|---|
| `language_bytes.*` (python, javascript, html, css, dockerfile, makefile, shell) | Language-aware grouping; flagging repos where the primary language has zero matching CI checks. |
| `dependencies.count`, `dependencies.pypi.count`, `dependencies.pypi_all.count`, `dependencies.js.count`, `dependencies.js.all.count`, `dependencies.js.dev.count`, `dependencies.github.count` | Dependency volume signal; Phase 2 metric. |
| `dependencies.pypi.list`, `dependencies.pypi_all.list`, `dependencies.js.list`, `dependencies.js.all.list`, `dependencies.js.dev.list`, `dependencies.github.list` | Vulnerability cross-reference with deps.dev and similar dependency intelligence sources (Phase 2/3). |
| `django_packages.django_42.count`, `django_packages.django_42.list`, `django_packages.total.count`, `django_packages.total.list`, `django_packages.upgraded.count`, `django_packages.upgraded.list` | Django version drift / upgrade readiness; org-specific value. |
| `requires.django`, `requires.pytest`, `requires.nose`, `requires.boto` | Test framework / cloud-SDK presence signal. |
| `renovate.last_pr`, `renovate.total_open_prs`, `renovate.oldest_open_pr_date` | Renovate *health*, not just presence; useful refinement of Metric 9. |
| `setup_py.python_versions`, `setup_py.py38_classifiers`, `setup_py.pypi_name`, `setup_py.repo_url`, `setup_py.project_urls` | Python version drift detection. |
| `travis_ci.active`, `travis_ci.active_on_com`, `travis_ci.active_on_org`, `travis_yml.parsable`, `travis_yml.py38_tests`, `travis_yml.python_versions` | Legacy-CI detection (informs the "modernize CI" attention rule in §3.1.11). |
| `tox_ini.has_section.testenv`, `tox_ini.has_section.testenv:quality`, `tox_tox_section`, `tox_ini.uses_whitelist_externals` | Tox configuration completeness. |
| `npm_package` | JavaScript-package registry presence. |
| `ubuntu_packages.apt_get_packages`, `ubuntu_packages.docker_packages`, `ubuntu_packages.yml_files` | System dependency surface. |
| `github.allows_merge_commit`, `github.allows_rebase_merge`, `github.allows_squash_merge`, `github.branch_count`, `github.build_details`, `github.code_of_conduct`, `github.created_at`, `github.default_branch`, `github.disk_usage_kb`, `github.has_issues`, `github.has_wiki`, `github.is_disabled`, `github.is_fork`, `github.is_locked`, `github.is_private` | GitHub metadata (Repo Detail metadata; some may inform additional checks). |

### B.4 Metric availability vs live CSV

| Metric | Required column(s) | Present in CSV? | Action |
|---|---|---|---|
| Commit recency | `github.last_push` | Yes | Compute in Phase 1. |
| PR response time | `github.median_pr_response_seconds` | No | Mark `unavailable`. File issue on `edx-repo-health` for Phase 2 consideration. |
| PR closure ratio | `github.pr_closure_ratio_90d` | No | Mark `unavailable`. File issue. |
| Release frequency | `github.release_count_12mo` | No | Mark `unavailable`. File issue. |
| Contributor Absence Factor | `github.contributor_count_90d` | No | Mark `unavailable`. File issue. |
| README quality | `readme.getting-help`, `readme.security` (+others) | Yes (partial) | Compute over present columns. |
| CI status | `github_actions` | Yes | Compute in Phase 1. |
| `openedx.yaml` compliance | `exists.openedx.yaml` | Yes | Compute in Phase 1 (binary; full schema validation pending upstream). |
| Dependency freshness | `dependabot.*`, `renovate.configured`, `renovate.oldest_open_pr_date` | Yes | Compute in Phase 1; renovate-age refinement is a stretch goal. |

**Phase 1 effective composite**: weighted average of metrics 1, 6, 7, 8, 9 (combined nominal weight 0.50, renormalized to 1.0).

**Phase 2 expansion path**: file separate issues against `openedx/edx-repo-health` to add the missing columns. Once available, mark each metric as `computable` in `scoring.yaml` and rebuild the composite.

This matrix is version-controlled with the PRD and is updated by the same PR that updates `dashboard/config/openedx/scoring.yaml` whenever the upstream CSV schema changes.

---

## Appendix C: License Rationale (Extended)

### C.1 The constraint

The project has two requirements usually in tension:

1. Be a community open source project, with all the community trust, contribution flow, and governance expectations that come with that.
2. Preserve the option to build a commercial product on the same codebase later.

### C.2 Rejected alternatives

**MIT or Apache-2.0 without a CLA**: maximally permissive, but offers no protection against a commercial competitor forking the codebase, hosting it as a SaaS, and out-pricing or out-marketing the eventual commercial version.

**MIT or Apache-2.0 with a CLA**: same problem.

**GPLv3 without AGPL's network clause**: SaaS hosting does not trigger source disclosure obligations under GPLv3.

**AGPL-3.0 without a CLA**: the moment the first external contributor merges a non-trivial PR, the project owner loses the legal right to relicense the combined codebase for a closed-source commercial version.

**BSL or Elastic License v2 (original)**: not OSI-approved. The 2024–2026 record is illuminating: HashiCorp's BSL choice fragmented its community (OpenTofu fork; IBM acquisition in Feb 2025), and Redis's SSPL/RSAL move drove a similarly visible fork (Valkey, hosted by the Linux Foundation) within 30 days; Redis ultimately **re-added AGPLv3** by May 2025. Elastic re-added AGPLv3 alongside SSPL/Elastic v2 in August 2024. The 2026 consensus among OSS-pragmatist projects is that AGPL is the strongest OSI-approved protection against SaaS competitors.

**Dual MIT + proprietary** with no CLA: without a CLA, contributions come in under MIT only.

### C.3 Why AGPL-3.0 plus CLA

AGPL-3.0 prevents SaaS competitors from forking and hosting the dashboard while keeping their improvements private. CLA preserves the project owner's right to offer a commercial closed-source version. Same combination used historically by Grafana, Sentry, MongoDB, and Elastic. The 2024–2026 record validates AGPL as the OSI-approved choice for the "SaaS-protection while staying open source" niche.

### C.4 Operational details

- CLA enforcement via cla-assistant.io.
- The CLA text is modeled on the Apache ICLA.
- Trivial contributions accepted under DCO instead of CLA (§10.5 spells out the threshold).
- The `NOTICE` file lists all CLA-signed contributors.
- The AGPL **source-code obligation** is met by linking from the page footer to the deployed commit SHA in the repository.

### C.5 The OpenStack DCO precedent and why it doesn't change the decision

OpenStack replaced its CLA with a DCO effective 2025-07-01, citing contributor friction. The decision was endorsed by the OpenStack Technical Committee in May 2025 (resolution 20250520-replace-the-cla-with-dco-for-all-contributions).

This project's situation differs in two material ways:

1. **OpenStack has no productization path.** OpenStack is a foundation-governed multi-vendor project; no single entity has the right or the interest to offer a closed-source commercial version. This project explicitly preserves that right (see §2.4 and §10.7).
2. **OpenStack has hundreds of contributors.** This project has one contributor today and is realistically planning for "two to five" through the Phase 2 horizon. The relicensing-friction problem the DCO solves at OpenStack scale is not the bottleneck at this scale.

The DCO trend is real and may eventually re-trigger this decision (see §10.5 and §11 open question 11). For Phase 1, CLA is retained with a DCO fast path for trivial contributions.

### C.6 Future flexibility

If at any point the project's strategic direction changes, the CLA's existence makes a license transition possible without per-contributor consent.

---

## Appendix D: Glossary

| Term | Definition |
|---|---|
| `dashboard_main.csv` | The canonical health-check output, committed daily to `openedx/wg-maintenance/main:dashboards/` by the routine repo health job. |
| `repo_name` | The canonical repo identifier column in `dashboard_main.csv`. Includes the `owner/` prefix in shipped data. |
| `TIMESTAMP` | The snapshot date column in `dashboard_main.csv`, formatted `YYYY-MM-DD`. |
| `github.last_push` | The repo last-push column, formatted `YYYY-MM-DD HH:MM:SS` (naive, treated as UTC). |
| `pytest-repo-health` | The pytest plugin that runs health checks against repositories. |
| `edx-repo-health` | The Open edX repository containing health-check definitions consumed by `pytest-repo-health`. |
| Composite score | Weighted average of nine normalized metrics, scored 0 to 100. See Appendix A. |
| Letter grade | A through F derived from the composite score. See Appendix A. |
| Tier | Repo classification: `critical`, `important`, or `standard`. Defined in `dashboard/config/openedx/tiers.yaml`. May migrate to `ownership.priority` upstream column when populated. |
| CLA | Contributor License Agreement. Signed once per contributor via cla-assistant.io. |
| DCO | Developer Certificate of Origin. Lightweight contribution sign-off used for trivial contributions. |
| Deep link | A URL containing query parameters that fully specifies a dashboard view. |
| Sparkline | A small inline trend chart, used per-category on Repo Detail. |
| Snapshot | A single dated version of `dashboard_main.csv`, read from git history. |
| Last-known-good snapshot | The most recent successfully-validated `dashboard_main.csv` retained in cache for fallback rendering. |
| WG | Working Group. Open edX has several, including the Maintenance WG, Build-Test-Release WG, DevOps WG, Frontend WG, Data WG. |
| CHAOSS | Community Health Analytics for Open Source Software, a Linux Foundation working group publishing metric definitions. |
| Contributor Absence Factor (CAF) | The current canonical CHAOSS name for what was historically called "Bus Factor" or "Elephant Factor". |
| OpenSSF Scorecard | Open Source Security Foundation tool that assigns 0–10 security scores to repos along 20 named checks. |

---

## Appendix E: Comparable Projects and Prior Art

| Project | What it does | Why it doesn't replace this dashboard |
|---|---|---|
| **OpenSSF Scorecard** | 0–10 security-posture score, 20 checks (Binary-Artifacts, Branch-Protection, CI-Tests, CII-Best-Practices, Code-Review, Contributors, Dangerous-Workflow, Dependency-Update-Tool, Fuzzing, License, Maintained, Packaging, Pinned-Dependencies, SAST, SBOM, Security-Policy, Signed-Releases, Token-Permissions, Vulnerabilities, Webhooks), GitHub repo-by-repo, public REST API at `api.securityscorecards.dev`. | Single-repo focus; security-only; no org-curated view; no remediation snippets; no openedx-specific checks. Complementary, not a substitute. |
| **CHAOSS Cauldron** | Hosted dashboard built on GrimoireLab/Perceval. | Heavy infra footprint; GPL stack; configuration outside git; aging Kibiter UI; multi-tenant SaaS model with cost. |
| **GrimoireLab** | Self-hostable Bitergia-style stack. | 4–16GB RAM; GPLv3 forecloses productization; operational complexity. |
| **libraries.io** | Per-package health surface with sourcerank. | Package-centric, not repo-centric; not openedx-curated; declining maintenance. |
| **Snyk Advisor** | Per-package health and security score. | Commercial; package-centric; no org-curated view. |
| **GitHub Insights / repo health files** | GitHub-native, per-repo, community-profile checklist. | Single-repo, no org rollup, no scoring, no trend dimension, no remediation snippets. |
| **OSSF Allstar** | Org-level policy enforcement bot. | Enforces, doesn't surface. No visualization. Complementary if the org adopts it. |
| **deps.dev** | Google's package dependency graph. | Package-centric, not repo-centric. |
| **Bitergia Analytics (historical)** | Open edX's previous dashboard, shut down March 2026. | The thing this project replaces. |

The dashboard's distinct positioning: **org-curated, openedx-aware, scoring-transparent, deep-linkable, action-loop-enabled, zero-infrastructure**.

---

## Appendix F: Definition-of-Done Checklist (consolidated)

A printable, per-PR checklist consolidating the cross-cutting acceptance criteria.

**Code & tests**
- [ ] CI green: `pytest`, `ruff`, `mypy` (on `dashboard/lib/`), `bandit`, `axe-core` (where pages render).
- [ ] Coverage delta on `dashboard/lib/` ≥ 0.
- [ ] No new Streamlit import in `dashboard/lib/`.
- [ ] No new hardcoded user-facing string outside `strings.yaml` (CI gate via `check_i18n_readiness.py`).
- [ ] No new dependency on `streamlit-plotly-events` or `st.experimental_*` query-param APIs.

**Configuration**
- [ ] Any new config key documented in `dashboard/config/README.md`.
- [ ] Any new config file has a JSON Schema in `dashboard/config/schemas/`.
- [ ] `scoring.yaml.version` bumped if scoring semantics changed.

**UX & accessibility**
- [ ] No new wide-table-only default view.
- [ ] Any new status indicator uses both colour and text.
- [ ] Any new chart has a tabular fallback or text alternative.
- [ ] Any new external link uses `rel="noopener noreferrer"`.
- [ ] Any new interactive target meets WCAG 2.2 2.5.8 (24×24 CSS px).
- [ ] Animated transitions respect `prefers-reduced-motion`.
- [ ] Lighthouse accessibility score ≥ 90 on touched pages.

**Documentation**
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`.
- [ ] PR description names the feature flag (if any) gating the change.
- [ ] If user-facing: a one-line entry in `docs/CONTRIBUTING.md` "Visible changes" log.

**Release safety**
- [ ] PR is independently deployable; reverting it does not break `main`.
- [ ] If schema-touching: a sample CSV missing the new columns is in `tests/fixtures/` and the dashboard renders against it.

---

## Appendix G: External Tools

Quick references for tools named in this PRD.

| Tool | URL | Used for |
|---|---|---|
| Streamlit | https://docs.streamlit.io | Visualization framework (≥ 1.56). |
| Streamlit release notes (2026) | https://docs.streamlit.io/develop/quick-reference/release-notes/2026 | API stability reference. |
| Plotly | https://plotly.com/python/ | Charting. |
| rapidfuzz | https://github.com/rapidfuzz/rapidfuzz | Fuzzy search (permissive license). |
| DuckDB | https://duckdb.org | Phase 2 SQL layer. |
| GitHub REST API (commits/blobs, unauthenticated) | https://docs.github.com/en/rest/commits/commits | History reads from `wg-maintenance`. |
| cla-assistant.io | https://cla-assistant.io | CLA enforcement via GitHub OAuth. |
| OpenSSF Scorecard | https://github.com/ossf/scorecard | Cross-reference for security checks. |
| OpenSSF Scorecard public API | https://api.securityscorecards.dev | Phase 2 ingestion. |
| CHAOSS metrics | https://chaoss.community/kb-metrics-and-metrics-models/ | Cross-reference for community-health metrics. |
| Perceval | https://github.com/chaoss/grimoirelab-perceval | Phase 3 contributor data via subprocess. |
| ruff | https://docs.astral.sh/ruff/ | Python linter. |
| mypy | https://mypy.readthedocs.io | Static type checker. |
| bandit | https://bandit.readthedocs.io | Python security linter. |
| axe-core | https://www.deque.com/axe/ | Accessibility CI. |
| Pa11y | https://pa11y.org | Accessibility CI (monthly). |
| Lighthouse | https://developer.chrome.com/docs/lighthouse/ | Accessibility/performance audit. |
| GitHub URL-query reference (PR pre-fill) | https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/using-query-parameters-to-create-a-pull-request | Confirmed PR-template query params. |
| GitHub URL-query reference (Issue pre-fill) | https://docs.github.com/en/issues/tracking-your-work-with-issues/creating-an-issue#creating-an-issue-from-a-url-query | Confirmed Issue-template query params. |

---
