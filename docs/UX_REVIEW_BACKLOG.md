# UX / UI Review Backlog

Deep review of the Phase 1 dashboard for discussion. **Nothing here is decided** —
this is the full candidate list, including items we will probably reject.

**How this was produced:** read all app source (`streamlit_app.py`, `pages/*`,
`dashboard/ui/*`, `dashboard/lib/*`), ran the app locally against the live
upstream CSV, captured full-scroll screenshots of every page at 1440px and at
390px (mobile), ran an axe-core 4.10 accessibility scan on four pages, and
reviewed the runtime log and the actual snapshot column list.

Items marked **[VERIFIED]** are reproduced defects, not opinions. Items marked
**[IDEA]** are proposals with no defect behind them.

Priority key: **P0** credibility/broken · **P1** high user value · **P2** polish ·
**P3** speculative.

---

## A. Broken things a user will hit today

| # | Finding | Pri |
|---|---|---|
| A0 | **Deep links bypass the entry script entirely, so the dashboard renders unstyled AND feature flags stop applying.** [VERIFIED] Streamlit's automatic `pages/` directory discovery takes precedence on a direct load of any non-root URL, before `streamlit_app.py` runs. Since that file holds *both* `apply_base_style()` and the whole `st.navigation()` flag-gated nav config, a first visit to any sub-page gets: no base CSS (no Inter, no card surfaces, no grade-pill colours, no sidebar gradient, status chips as plain heading text), the raw filename-derived nav, and **every flag-disabled page reachable**. Confirmed against a cold server: base CSS absent after 45s and never recovers (a rerun does not fix it; only visiting `/` does), while `/` itself styles in 0.9s. Also confirmed `GET /sql` renders the working Ad-hoc SQL page — textarea and Run query button present — despite `enable_sql_page: false`; same for `/badges`, `/cards`, `/healthz`. **Every share link the dashboard generates points at a non-root page**, and Streamlit Community Cloud sleeps idle apps, so the recipient of a pasted link is the visitor most likely to hit this. Found by the WP-1 harness on its first run. | **P0** |
| A0b | **Feature flags provide no access control, only nav shaping.** [VERIFIED] Corollary of A0 and a governance issue in its own right: `feature_flags.yaml` is consulted only in `streamlit_app.py` when building `st.navigation`, never inside the pages themselves. Any file in `pages/` is reachable by its derived URL regardless of its flag. Bounded impact — the SQL page is read-only, sanitised (`sanitize_readonly_query`) and row-capped, over a snapshot that is already public — so this is "a disabled feature is live in production" rather than a data breach. Reframes **C11**: the flag-off pages are not actually hidden today. | **P0** |
| A1 | **Dark-mode toggle does nothing.** [VERIFIED] `apply_base_style()` sets `data-theme` via a `<script>` inside `st.markdown`. Browsers do not execute scripts injected as innerHTML, so `data-theme` is never set (confirmed: attribute is `null` before and after toggling). The entire `[data-theme="dark"]` CSS block in `theme.py` is dead code, and `.streamlit/config.toml` pins `base = "light"` so the system preference is ignored too. The toggle visibly flips to "on" and nothing happens. | P0 |
| A2 | **Sidebar Tier filter is a no-op.** [VERIFIED] `FilterState.apply()` filters on a `repo_tier` column. No code creates that column and the upstream CSV does not have it (checked: 111 columns, no `repo_tier`). Selecting Tier = `critical` on Overview silently returns all 171 repos. | P0 |
| A3 | **History file 404s upstream.** [VERIFIED] `https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_history.csv` returns 404 on every load. Locally it falls back to `.cache/dashboard_data/history.csv`, which does not exist on Streamlit Cloud — so in production every trend feature (KPI deltas, org sparkline, per-category sparklines, movers, What Changed) is dead, silently. No user-facing message explains it. | P0 |
| A4 | **Local history is stale and looks real.** [VERIFIED] The cached history renders sparklines labelled *May 10 – May 31 2026* while the snapshot is *2026-07-24*. A viewer cannot tell that trend lines are two months old. | P0 |
| A5 | **Radar chart scores missing metrics as 100.** [VERIFIED] `_metric_radar` uses `per_metric.get(label, 100.0 if label in unavailable else 0.0)`. Four uncollectable metrics are drawn at full radius, so a repo with 5/9 metrics looks near-perfect. Actively misleading. | P0 |
| A6 | **"Biggest losers" can show gains.** [VERIFIED] `_top_movers` sorts descending then takes `.tail(5)`. If every repo improved, the five smallest improvements are labelled losers. | P1 |
| A7 | **"What Changed This Week" is not a week.** [VERIFIED] It diffs `history[-1]` vs `history[-2]` — two consecutive snapshots, 6 hours apart on the intended cadence. Title, page name, and bulletin all say "week". | P1 |
| A8 | **Raw dataframe index leaks on Failing Checks.** [VERIFIED] `hide_index=True` is missing, so an unlabelled column of internal row numbers (65, 62, 83…) is the first thing in the table. Axe also flags it as an empty table header. | P2 |
| A9 | **Gauge axis labels are clipped.** [VERIFIED] `0` renders as a sliver and `100` renders as `1` at the bottom corners of the gauge. | P2 |
| A10 | **Y-axis title clipped on the grade histogram.** [VERIFIED] "Repositories" renders as "positories" — `margin.l = 12` is too tight for the rotated title. | P2 |
| A11 | **Long repo names collide with grade pills.** [VERIFIED] In Bottom 5, `openedx/openedx-app-firebase-analytics-ios` runs straight into its `D` pill. The pill list is a flex row with no `min-width: 0` / truncation. | P2 |
| A12 | **`exists..coveragerc` double-dot artifact** shown verbatim in the Checks Catalog and Repo Detail. Should display as `.coveragerc`. | P2 |
| A14 | **Radar axis labels permute on every server start.** [VERIFIED] `pages/02_repo_detail.py:99-100` builds `unavailable = set(...)` then iterates it into `labels`, so set ordering (hash-seed dependent) changes the axis order between restarts — identical polygon, shuffled labels. A user reloading gets metrics in different positions. Fix is `sorted(...)`. Found while pinning `PYTHONHASHSEED` for the WP-1 harness. | P1 |
| A13 | **`Commit: local` leaks into the weekly bulletin** when `GITHUB_SHA` is unset. Anyone copying the bulletin from a local run pastes dev metadata into Slack. | P2 |

---

## B. Score credibility and transparency

This is, in my read, the highest-leverage cluster. The dashboard's stated value
prop is "scoring-transparent", and right now the numbers do not survive scrutiny.

| # | Finding | Pri |
|---|---|---|
| B1 | **Half the composite score is fabricated.** [VERIFIED] The snapshot has none of `github.median_pr_response_seconds`, `github.pr_closure_ratio_90d`, `github.release_count_12mo`, `github.contributor_count_90d`. Those four metrics carry 0.15+0.15+0.10+0.10 = **50% of total weight** and every repo gets `default_when_missing: 50`. That is why "Score coverage" reads exactly 50%. So "Org Health 70.3 · Grade B" is 50% real signal and 50% a constant. The gauge presents it with no caveat. | P0 |
| B2 | **"Score coverage 50%" is a fourth-position KPI tile.** The most important caveat on the page is the least prominent number on it. Consider putting coverage *on* the gauge (e.g. a hatched/ghosted arc segment for the uncomputable half) or a persistent banner. | P0 |
| B3 | **"Activity 100.0" on Repo Detail is meaningless.** All five activity metrics but one are unavailable, so Activity is dominated by defaults. Showing a hard `100.0` in a KPI tile next to a real `Structural 90.5` implies equal confidence. Suggest greying/annotating any sub-score whose coverage is below a threshold. | P0 |
| B4 | **Only 3 of 76 collected checks feed the score.** [VERIFIED] The Checks Catalog states this plainly as a metric tile ("Checks collected 76 / Feeding the score 3"). Users will reasonably ask what the other 73 are for. Either the framing needs work ("informational vs scored") or the scoring needs to widen. | P0 |
| B5 | **63 of 76 checks have no description.** [VERIFIED] Displayed as a "Missing descriptions 63" tile — an internal QA counter shipped to the public. Fill the descriptions, or move the counter to a maintainer-only view. | P1 |
| B6 | **No "how is this scored" explainer anywhere in-app.** There is a Checks Catalog but no page that shows the 9 metrics, their weights, the letter-grade bands, and the `default_when_missing: 50` policy. A "Scoring" page (or a modal from the gauge) would answer the first question every new viewer has. | P1 |
| B7 | **`default_when_missing: 50` is invisible.** A repo scoring 50 on a metric because the data is absent is indistinguishable from one that genuinely scored 50. Suggest a distinct visual state ("no data") everywhere a metric is rendered. | P1 |
| B8 | **Thresholds are marked "provisional (pending maintainer sign-off)" in `scoring.yaml`** but presented in the UI as settled fact. Consider surfacing that provisional status, at least for the four activity metrics. | P1 |
| B9 | **Ties are invisible.** [VERIFIED] All five "Top 5" repos score exactly 96.7. There are almost certainly more at 96.7 that didn't make the cut. Show "5 of 23 repos tied at 96.7" or switch to a percentile framing. | P2 |
| B10 | **Score has no confidence interval or "n metrics" badge in list contexts.** The `5/9 metrics (50% weight)` chip exists on Repo Detail but nowhere in tables or the Top/Bottom lists, so rankings mix well-measured and poorly-measured repos without distinction. | P2 |
| B11 | **Grade bands are never shown next to a grade.** A viewer seeing "Grade B" has no idea B = 60–79 without leaving the page. Cheap fix: tooltip on every grade pill. | P2 |
| B12 | **"Scoring config 2.0" occupies a prime KPI tile** on Repo Detail. That is provenance metadata, not a metric. Move it to a footer or the share/export block and reclaim the tile. | P2 |

---

## C. Information architecture and navigation

| # | Finding | Pri |
|---|---|---|
| C1 | **Sidebar order is inverted.** [VERIFIED] Navigation renders first; the "Open edX Health" wordmark and the data-freshness chip render *below* it, mid-sidebar. Brand and freshness are the two things that should be at the top. Streamlit renders `st.navigation` above `st.sidebar` content — needs a different composition (e.g. logo via `st.logo()`). | P1 |
| C2 | **The freshness chip is buried and under-weighted.** [VERIFIED] The snapshot is 3 days old and past the 48h stale threshold, yet the only signal is a small amber dot on a translucent chip halfway down a dark sidebar. Stale data deserves a main-content banner. | P1 |
| C3 | **"Showing 171 of 172 repos" sits at the very bottom of the sidebar**, several controls away from the filters that produce it, and contradicts the page header's "171 repos". Move it directly under the filter group. | P2 |
| C4 | **Ownership is a top-level nav *section* containing one dead page.** [VERIFIED] Coverage is 0.0%; the required `ownership.owner` / `ownership.owner_name` columns do not exist in the snapshot at all (only empty `theme`/`squad`/`priority`). Shipping an empty section costs more trust than hiding it. **Attempted in WP-6 and reverted** [VERIFIED]: omitting a page from `st.navigation()` also stops its URL resolving, so `/ownership_views` answered with a "Page not found" modal and fell back to Overview — breaking every previously shared link to it. WP-6 improved the page's own empty state instead (see D53). Genuinely hiding it requires moving the file out of `pages/` so Streamlit's routing never sees it, which needs a decision on whether the URL should keep working. `has_ownership_data()` exists and is tested, ready for whichever way that goes. | P1 |
| C5 | **Failing Checks and Overview's "Top failing checks" tab overlap almost entirely.** Two entry points, different visual treatments, neither complete. Consider merging, or making Overview's tab a teaser that links into the full page. | P1 |
| C6 | **Overview's "Biggest gainers/losers (30d)" belongs on What Changed.** Score movement is the What Changed page's whole job, and it currently has no score movers at all. Split-brain IA. | P1 |
| C7 | **Nav labels don't match page titles.** "Ownership" → "Maintainer and Working Group Views"; "Checks Catalog" → matches; "Repo Detail" → "Repository Detail". Pick one vocabulary. | P2 |
| C8 | **No global search / command palette.** Finding a specific repo requires navigating to Repo Detail and using two stacked controls. A single "jump to repo" affordance in the sidebar, available from every page, would be the highest-frequency action. | P1 |
| C9 | **No footer.** `org_branding.yaml` defines `footer.source_url` and `footer.privacy_url` and **nothing reads that file** [VERIFIED]. There is no link to the source repo, the privacy doc, the data source CSV, the pipeline, or a way to report a problem. For a community tool this is a significant omission. | P1 |
| C10 | **`strings.yaml` is entirely unused** [VERIFIED] — every label is hardcoded in the page modules, so the i18n scaffolding (and `scripts/check_i18n_readiness.py`) is inert. Either wire it up or drop the pretence. | P2 |
| C11 | **Three built pages are flag-off and invisible** (SQL, Badges, Cards). They exist, work, and are labelled "Phase 2 feature" in their own captions. Decide: ship behind a "Labs" section, or delete from the nav wiring. | P2 |
| C12 | **No breadcrumbs or back-affordance** when arriving via a deep link (e.g. a `?repo=` link from Slack). The user lands on Repo Detail with no sense of the surrounding org. | P2 |
| C13 | **Page ordering is not task-ordered.** For the #1 persona (WG lead running a weekly meeting), the sequence should be What Changed → Needing Attention → Overview. It is currently Overview → Repo Detail → Failing Checks → Needing Attention → What Changed. | P2 |

---

## D. Page-by-page

### D.1 Overview

| # | Finding | Pri |
|---|---|---|
| D1 | **Grade mix ribbon and Grade distribution tab show the same data twice**, stacked vertically, ~20px apart. Pick one. | P1 |
| D2 | **The F segment of the ribbon is unlabelled** (3 repos, below the 3% label threshold) — the most alarming grade is the one you cannot see. Consider a minimum label or a legend. | P2 |
| D3 | **Movers tables use raw column names** (`repo_name`, `delta`), no units, inconsistent decimals (`44` vs `-18.34`), no grade context, no links to Repo Detail — right below two beautifully-formatted linked pill lists. Jarring inconsistency. | P1 |
| D4 | **Mover deltas look implausible** (+44, +35 in 30d; five separate repos at exactly −15). Worth validating before shipping; if the baseline is a partial snapshot, these are artifacts. | P1 |
| D5 | **The org sparkline is unlabelled and unbounded** — no y-axis, no start/end values, no hover. "Org-average composite · last 5 snapshots" is the only context, and 5 snapshots is too few to read as a trend. | P2 |
| D6 | **The header caption duplicates the KPI caption** ("Snapshot 2026-07-24" appears twice within 400px). | P2 |
| D7 | **"drill in via the sidebar nav" is instructional filler** in the page subtitle. Replace with something informative (repo count, coverage, or the org tagline that `org_branding.yaml` already defines). | P2 |
| D8 | **Grade A tile shows no delta while Grade F and Stale do** — because `_delta_str` suppresses deltas below a threshold. Reads as a rendering bug, not as "no change". Consider an explicit "—" or "no change". | P2 |
| D9 | **"Stale repos 171"** means *every* repo is stale, which makes the metric useless as a signal at the current threshold. Either the threshold is wrong for this org or the metric needs rethinking. | P1 |
| D10 | **Share & export is collapsed at the very bottom** of a 2000px page. For a tool whose vision is "URLs pasted into Slack", the share affordance should be a persistent one-click button in the header. | P1 |
| D11 | **The full 171-repo table is behind a collapsed expander with no sort/filter/pagination controls** beyond Streamlit's defaults, and no grade pills. This is the workhorse view for anyone doing real triage. | P1 |
| D12 | [IDEA] Add a **"what to look at first"** block — 3 concrete callouts (worst critical repo, biggest regression, most-failed check) with direct links. Turns a dashboard into a to-do list. | P1 |

### D.2 Repo Detail

| # | Finding | Pri |
|---|---|---|
| D13 | **Two stacked search controls.** [VERIFIED] A "Find repository" text input feeds a fuzzy filter into a "Repository" selectbox. Streamlit selectboxes already type-to-search. Two controls, one job, and the text input silently caps results at 30. | P1 |
| D14 | **No link to the actual GitHub repository.** [VERIFIED] The page has "File issue" and "Open PR" buttons per failing check but no plain "View on GitHub". | P1 |
| D15 | **The radar chart is ~600px tall, pushes everything below the fold, has a single-series legend, and its radial tick labels (0–100) overprint the plot and the `commit_recency` axis label.** Combined with A5 (missing = 100) it is the weakest element on the page. Consider a horizontal bar chart of per-metric scores with explicit "no data" bars. | P1 |
| D16 | **Category sparklines are near-useless at that size** — 160px charts inside 3-across cards, drawn as flat lines with a 0–100 axis and 4 date ticks, mostly showing no variation. Either shrink to a true sparkline (no axes, ~28px) or drop them. | P2 |
| D17 | **The copy-link block is a full-width `st.code` above the fold**, consuming a prime content slot to display a URL. Should be an icon button with clipboard copy. | P2 |
| D18 | **43 check expanders in a flat alphabetical list**, keyed by raw column name (`dependabot.has_ecosystem.npm`), with no pass/fail indicator in the *collapsed* header. You must open each one to learn its status. Put the status chip and human title in the header. | P1 |
| D19 | **Filter labels are inconsistent**: "Failing only" / "All" / "Passing" / "Unknown". Also the default is "Failing only" while the count caption says "15 of 43 checks shown" — reads like data is missing. | P2 |
| D20 | **`st.code(f"value = {value!r}", language="python")`** exposes a Python repr to end users. Format the value for humans. | P2 |
| D21 | **111 columns of rich context are unused.** `github.description`, `license`, `fork_count`, `created_at`, `pulls_count`, `default_branch`, `language_bytes.*`, `renovate.total_open_prs`, `renovate.oldest_open_pr_date`, `setup_py.repo_url`, `readthedocs_config.*`. A repo header card with description, language mix, license, and age would cost little and add real orientation. | P1 |
| D22 | **The `5/9 metrics (50% weight)` chip fails colour contrast** [VERIFIED by axe] and is cryptic copy. | P2 |
| D23 | **Landing with no `?repo=` param silently selects the alphabetically-first repo** (`openedx/DoneXBlock`) rather than prompting or defaulting to something meaningful. | P2 |
| D24 | [IDEA] **Compare mode** — pick 2–3 repos and show metrics side by side. High value for maintainers of related repos. | P2 |
| D25 | [IDEA] **Per-repo score history chart** (not just per-category pass rate) with annotations for grade transitions. | P2 |

### D.3 Failing Checks

| # | Finding | Pri |
|---|---|---|
| D26 | **The chart is unreadable.** [VERIFIED] ~40 bars, one colour each, vertically-rotated overlapping labels, and a legend that lists only 6 of the 40 series and gets cut off. It also bypasses the design system (`px.bar(color=...)` instead of the themed lollipop used on Overview, which is genuinely good). | P0 |
| D27 | **Click-to-filter is undiscoverable.** [VERIFIED] `on_select="rerun"` is wired up but nothing tells the user bars are clickable, and precise clicking on a 12px bar is hard. Add an explicit selectbox alongside it. | P1 |
| D28 | **Raw column headers** (`repo_name`, `score_composite`, `score_letter`) and **full URLs as link text**, truncated mid-string. | P1 |
| D29 | **The default table lists all 171 repos sorted by score** — on a page called "Failing Checks", with no column showing *which* checks fail. Not actionable until you click a bar. | P1 |
| D30 | **Triple-nested title**: "Failing Checks" (page) → "Failing checks distribution" (h3) → "Failing checks by count" (plotly title). Also an axe heading-order violation. | P2 |
| D31 | [IDEA] **Invert the page**: lead with a ranked list of checks (check name, human title, N repos failing, one-line remediation, "fix all" links), each expanding to the repo list. That is the shape of the actual task. | P1 |

### D.4 Needing Attention

| # | Finding | Pri |
|---|---|---|
| D32 | **The rules barely fire.** [VERIFIED] 9 rows out of 171 repos, and 8 of the 9 have the identical reason "no commits in 90+ days". Meanwhile `openedx/edx-platform` (tier critical) is absent and grade-F repos with recent commits are never flagged, because `critical_low_grade` only applies to the 2 configured critical repos. The page under-delivers on its name. | P0 |
| D33 | **A grade-B repo (62.67) appears in the attention list** while grade-F repos do not. No severity ordering, no explanation of why one reason outranks another. | P1 |
| D34 | **`tiers.yaml` covers 4 repos out of 171** (2 critical, 2 important, 0 standard). Everything else defaults to "standard", so tier-based rules are effectively off. This is a content problem, not a code problem, but it determines whether the page is useful. | P0 |
| D35 | **Raw column headers, truncated URLs, no grade pills, no tier badges, no reason icons.** Same table-formatting debt as C/D28. | P1 |
| D36 | **No explanation of tiers** or link to the rules that produced each row. The "reasons" strings are the only clue, and they're truncated when a repo has multiple. | P1 |
| D37 | **Tier filter options are lowercase raw values** (`all`, `critical`…) with no per-tier counts. | P2 |
| D38 | **Download button is below the share block** and unstyled, inverting the visual hierarchy of "act on this list" vs "link to this list". | P2 |
| D39 | [IDEA] **Assignment / triage state** — "acknowledged", "issue filed", "won't fix" with a link to the tracking issue. Even read-only (driven off GitHub issue labels) this turns a report into a workflow. | P2 |

### D.5 What Changed

| # | Finding | Pri |
|---|---|---|
| D40 | **Both sections are empty, and the empty state reads as good news.** [VERIFIED] "No newly failing checks" (green) + "No newly passing checks" (blue). The real cause is comparing two near-identical snapshots. A returning user concludes nothing ever changes and stops visiting. | P0 |
| D41 | **No period selector.** Add 24h / 7d / 30d, defaulting to something that actually produces rows. | P1 |
| D42 | **The bulletin renders even when there is nothing to report**, producing a markdown block full of "None". Suppress it, or make it say something useful. | P1 |
| D43 | **The bulletin is shown as syntax-highlighted markdown source** — headers render in red monospace. It looks like an error. Show the rendered bulletin with a "copy source" toggle. | P2 |
| D44 | **No score/grade change reporting** — only check-level flips. No "repos that changed grade", no "repos that dropped a tier", no org-average delta. This is the page WG leads open first. | P1 |
| D45 | [IDEA] **Narrative summary** — 2–3 auto-written sentences ("Org average fell 1.2 points. 3 repos dropped to D or below. `readme.security` regressed across 14 repos.") Copy-pasteable into a meeting agenda. | P1 |

### D.6 Checks Catalog

| # | Finding | Pri |
|---|---|---|
| D46 | **76 collapsed expanders in a flat 5900px scroll with no search or filter.** [VERIFIED] Finding a specific check means Ctrl-F. | P1 |
| D47 | **Titles duplicate the raw key** — `exists..coveragerc · exists..coveragerc` — when no human title exists in config, which is the case for 63 of 76. | P2 |
| D48 | **No cross-link from a check to the repos failing it.** The catalog knows the org pass rate for each check but doesn't link to Failing Checks. Dead end. | P1 |
| D49 | **Scored vs informational checks are not separated.** The 3 scored checks are buried among 73 informational ones with only an inline "Feeds score" line to distinguish them. | P1 |
| D50 | **"Suggested candidate checks" (proposed / phase-2) mixes roadmap into a reference doc.** Fine for maintainers, confusing for a viewer looking up what a check means. | P2 |

### D.7 Ownership

| # | Finding | Pri |
|---|---|---|
| D51 | **The page is entirely non-functional and says so.** [VERIFIED] 0.0% coverage, "No owner data found", and the required columns don't exist upstream. | P0 |
| D52 | **A 0.0% value gets a full-width hero metric card** — maximum visual weight for a null. | P2 |
| D53 | **"below the PRD trigger threshold (20%)" is internal jargon** in a user-facing warning. Nobody outside the project knows what a PRD trigger threshold is. | P1 |
| D54 | **"My Repos" requires manually typing a GitHub handle**, with no autocomplete, matching against ownership columns that are empty — so it always returns nothing. | P1 |
| D55 | [IDEA] Until `catalog-info.yaml` adoption lands, derive a **proxy owner** from `CODEOWNERS` or recent commit authors so the page has something to show. | P2 |

---

## E. Visual design and design-system consistency

The design system in `dashboard/ui/theme.py` is genuinely good — tokens, a Plotly
template, tabular numerals, grade pills, a reduced-motion block. The problem is
that it is applied unevenly.

| # | Finding | Pri |
|---|---|---|
| E1 | **Two chart idioms coexist.** Overview uses hand-built themed `go.Figure` charts with summary annotations and hover templates. Failing Checks and the sparklines use raw `px.bar`/`px.line` with default colours and titles. | P1 |
| E2 | **Two table idioms coexist.** Overview's Top/Bottom lists are custom HTML with pills and links; every other table is a bare `st.dataframe` with raw column names. Standardise on one `render_repo_table()` helper with `column_config` labels, grade pills, and compact links. | P1 |
| E3 | **`st.dataframe` `column_config` is barely used.** Only `LinkColumn` appears, and never with a display label — hence full URLs as link text. `NumberColumn(format=...)`, `TextColumn(label=...)`, and `ProgressColumn` for scores would fix most table complaints at once. | P1 |
| E4 | **`ui/tables.py` is 7 lines.** The intended shared-table abstraction was never built; each page reinvents it. | P1 |
| E5 | **Google Fonts is loaded via `@import` inside injected CSS** — a render-blocking third-party request, and it will fail behind restrictive CSPs, silently reverting typography to system sans. Consider self-hosting or dropping to a system stack. | P2 |
| E6 | **Heading levels skip.** [VERIFIED by axe] `st.markdown("##### Grade mix")` emits an `h5` directly under the `h1`; Failing Checks emits an `h3`. Use `st.subheader` consistently. | P2 |
| E7 | **Card shadows are heavy for a data-dense page.** Every metric, container, and dataframe gets `--shadow-card`, so nothing stands out because everything does. Consider borders-only for tables and reserving shadow for true cards. | P3 |
| E8 | **The dark teal sidebar with white text plus custom input styling is high-maintenance** — `theme.py` already carries three defensive comments about Streamlit's emotion classes fighting the overrides, and one about Material icons rendering as literal ligature text. Every Streamlit upgrade risks breaking it. Worth discussing whether the custom sidebar is worth the fragility. | P2 |
| E9 | **`card()` context manager is exported but unused** in every page. Dead abstraction. | P3 |
| E10 | **`render_freshness_banner()` is exported but never called** — the (better) main-content freshness banner exists in code and isn't wired up. See C2. | P1 |
| E11 | **Grade colour ramp is green-green-amber-orange-red** (A `#15803D`, B `#16A34A`). A and B are nearly indistinguishable at pill size. | P2 |
| E12 | **No favicon / page icon** — `st.set_page_config` sets `page_title` but no `page_icon`, so browser tabs show the default Streamlit mark. | P2 |
| E13 | **The Streamlit "Deploy" button and hamburger menu are visible** in the top-right of every page. For a public dashboard these should be hidden (`toolbarMode = "minimal"`). | P2 |

---

## F. Accessibility

Axe-core 4.10 scan of Overview, Repo Detail, Failing Checks, Needing Attention.

| # | Finding | Pri |
|---|---|---|
| F1 | **`.status-chip.status-warn` fails AA contrast.** [VERIFIED, serious] `#D97706` on a 12%-alpha tint of itself. `status-fail` and `status-pass` are likely borderline too. `theme.py`'s header comment claims "WCAG AA against Surface" — the claim does not hold for the chip tints. | P1 |
| F2 | **Sidebar input placeholder fails contrast.** [VERIFIED, serious] `rgba(255,255,255,0.10)` background with a default placeholder colour. | P1 |
| F3 | **`st.metric` delta text fails contrast** on the white card. [VERIFIED, serious] Streamlit's default green on `#FFFFFF`. Overridable via CSS. | P2 |
| F4 | **Heading-order violations** on Overview and Failing Checks. [VERIFIED, moderate] See E6. | P2 |
| F5 | **44 elements outside landmark regions** on Overview. [VERIFIED, moderate] Mostly Streamlit-internal, but we can add `role="main"`-scoped structure and skip-links. | P2 |
| F6 | **Colour is the sole signal in several places** — the freshness dot, the grade ribbon segments below the label threshold, the mover deltas' sign colour. `status_chip()` does this correctly (text + colour); these do not. | P1 |
| F7 | **Charts have no text alternative.** Plotly figures are canvas/SVG with no `aria-label` or adjacent data table. A screen-reader user gets nothing from the gauge, ribbon, histogram, or radar. Consider a "view as table" toggle per chart. | P1 |
| F8 | **`aria-label="Grade B"` on grade pills is good** — worth extending that pattern to the freshness chip and status chips. | P2 |
| F9 | **Focus-visible outline is defined** (`2px solid accent`) — but the accent teal on the dark sidebar and on white cards should both be contrast-checked. | P2 |
| F10 | **No documented keyboard path** through the 43 check expanders on Repo Detail or the 76 on the Catalog. Tab-through is technically possible but punishing. Search (D46) would fix this too. | P2 |
| F11 | **`unsafe_allow_html` is used ~15 times.** `render_repo_pill_list` escapes correctly; verify every other site does. Repo names come from upstream CSV, which is a (low) injection surface. | P2 |
| F12 | [IDEA] Publish an **accessibility statement**, given the audience includes public-sector Open edX operators with procurement requirements. | P3 |
| F13 | **`share_link_block()` produces a keyboard-inaccessible scroll region.** [VERIFIED, serious] `dashboard/ui/theme.py:532` renders the share URL via `st.code(url, language="text")`. At 390px the resulting `<pre>` overflows horizontally with no `tabindex`, so a keyboard-only user cannot scroll it and cannot read the URL. axe rule `scrollable-region-focusable`. Fires on exactly the four pages whose share URL carries query params (`repo_detail?repo=`, `needing_attention?tier=`, `what_changed`, `ownership_views?coverage=`) and not on `failing_checks`, whose URL is short enough not to overflow — content-length dependent, which confirms the call site. Ours to fix; D17 already replaces this widget, so fold it in there. **Only surfaced because the audit scans mobile** — a desktop-only scan misses it entirely. | P1 |

---

## G. Responsive / mobile

| # | Finding | Pri |
|---|---|---|
| G1 | **No mobile layout at all.** [VERIFIED at 390px] The title wraps to three lines, the gauge fills the entire first viewport, and the four KPI tiles stack one per row — roughly four full screens of scrolling before any content. | P1 |
| G2 | **`st.columns` never collapses responsively** — the 5-across KPI row on Repo Detail and the 3-across category cards get squeezed rather than reflowed. | P1 |
| G3 | **Charts don't reflow.** Fixed heights (`280`, `64`, `160`, `max(280, 32n+80)`) and horizontal label sets designed for 1400px. | P2 |
| G4 | **Wide tables have no horizontal-scroll affordance** on narrow viewports; content is simply cut. | P2 |
| G5 | **The sidebar collapses to a hamburger on mobile** (good) — but that hides the filters, the freshness chip, *and* the brand, leaving an unlabelled page. | P2 |
| G6 | [IDEA] A mobile-first "**glance view**": org grade, three deltas, top 3 attention items. Realistically how someone checks this from a phone during a meeting. | P2 |

---

## H. Performance and perceived speed

| # | Finding | Pri |
|---|---|---|
| H1 | **Overview loads history twice per render.** `_baseline_frame()` and `_top_movers()` each call `load_history()` and `calculate_scores()` independently. `_load_org_avg_history()` in `kpi.py` makes it three, and it re-scores *every* snapshot. | P1 |
| H2 | **`calculate_scores()` is called on every page, uncached**, over 171 rows × 111 columns with per-row Python loops. Wrap in `@st.cache_data`. | P1 |
| H3 | **No spinners or skeletons.** `@st.cache_data(ttl=300)` means every 5 minutes one unlucky user waits on a cold fetch + full rescore with no feedback. `show_spinner=False` is explicitly set on `_history_for_repo`. | P1 |
| H4 | **Repo Detail renders 43 expanders, 5 category cards, 5 sparkline charts, and a radar on every interaction** — including on each keystroke in the search box. | P1 |
| H5 | **Snapshot cache TTL is 300s but history TTL is 86400s.** After a pipeline run, KPI values and their deltas disagree for up to 24 hours. | P2 |
| H6 | **`_history_for_repo` is cached per repo**, so browsing 20 repos holds 20 copies of the 30-day history in cache. | P2 |
| H7 | **No `st.fragment` usage.** Filter changes and tab switches re-run the entire page. | P2 |
| H8 | **`expected_min_columns: 100` against an actual 111.** [VERIFIED] A modest upstream schema change trips validation and silently swaps in last-known-good with no user-visible notice. | P2 |

---

## I. Copy, microcopy, and onboarding

| # | Finding | Pri |
|---|---|---|
| I1 | **No first-run orientation.** A new visitor sees a gauge reading 70.3 with no explanation of what is measured, who measures it, how often, or what to do about it. | P1 |
| I2 | **Internal vocabulary leaks throughout**: "PRD trigger threshold", "Scoring config 2.0", "score coverage", "structural / activity", "N/A", raw check keys, `value = 'False'`. | P1 |
| I3 | **Empty states say what is absent, not what to do.** "Not enough historical snapshots to compute weekly deltas" — why? for how long? is that expected? | P1 |
| I4 | **`render_empty_state()` exists and is used once** (Overview, no-snapshot). Every other empty path uses a bare `st.info`/`st.warning`/`st.error`. Six different empty-state treatments across seven pages. | P2 |
| I5 | **Success and info colours are used interchangeably** for the same semantic ("nothing here"): green for no new failures, blue for no new passes, green for "No failing checks detected". | P2 |
| I6 | **The tagline in `org_branding.yaml`** ("Visualization-first health insights for Open edX repositories") is never displayed. | P2 |
| I7 | **No "how to fix this data" path** for the two biggest gaps — missing activity metrics and missing ownership. Both need upstream pipeline or repo-config changes; the dashboard could tell people exactly what to do. | P1 |
| I8 | **No timezone on displayed dates.** The freshness banner says "(UTC)"; the header caption and mover tables don't. | P2 |
| I9 | **"Repos Needing Attention" vs nav "Needing Attention" vs "attention rules" vs "attention list"** — four names for one concept. | P2 |
| I10 | [IDEA] **Contextual "why does this matter" text per check** — one sentence on the consequence of failing it, not just what it checks. This is what converts a report into behaviour change. | P1 |

---

## J. The action loop (the stated value proposition)

The PRD says "failing checks have one-click paths to remediation" and "easy
enough that fixing it has low effort cost". Right now the loop is thin.

| # | Finding | Pri |
|---|---|---|
| J1 | **Remediation is buried three levels deep**: Repo Detail → expand a check → scroll past status, description, and a Python repr → "File issue" / "Open PR". | P1 |
| J2 | **`enable_pr_template_generator` is on but the whitelist gates it** — worth checking how many of the 40 failing checks actually offer a PR button, and stating the count somewhere. | P1 |
| J3 | **No bulk action.** `readme.security` fails on ~150 repos. The only path is 150 individual visits. A "file issues across N repos" flow (even generating a checklist or a `gh` command) would be transformative. | P1 |
| J4 | **No "fix once, benefits many" surfacing.** The data supports ranking checks by (repos failing × ease of fix). That ranking is the most valuable artifact the dataset can produce and it isn't shown. | P1 |
| J5 | **No feedback that an action was taken.** File an issue and the dashboard looks identical on return; the next snapshot is up to 6 hours away. Consider linking to open issues that reference the dashboard. | P2 |
| J6 | **Remediation coverage is unstated.** `missing_remediation_checks()` exists and is used only to print a "config gap" caption in the Catalog. Users can't tell which failures are actionable before clicking. | P1 |
| J7 | [IDEA] **"Fix-it Friday" view** — filter to checks that are mechanically fixable, sorted by blast radius, with copy-paste snippets. A concrete, recurring community ritual the dashboard could anchor. | P2 |

---

## K. Community and social features

| # | Finding | Pri |
|---|---|---|
| K1 | **Share links are the core distribution mechanism and they are second-class** — collapsed expanders, `st.code` blocks requiring manual selection, no OG/Twitter card metadata, so a pasted link in Slack renders as a bare URL. | P1 |
| K2 | **No embed path.** The Badges and Cards pages are built and flag-off. Badges in repo READMEs are the single highest-leverage distribution channel for this kind of tool. | P1 |
| K3 | **No RSS/webhook/email digest.** The weekly bulletin exists as a downloadable markdown file that someone must remember to download. | P2 |
| K4 | **No "contribute a check" or "report a problem" path.** No issue-tracker link anywhere in the UI. | P1 |
| K5 | [IDEA] **Leaderboard framing is risky** — "Bottom 5" naming and shaming repos by name may land badly in a volunteer community. Worth an explicit discussion: "Bottom 5" vs "Most opportunity" and whether to show it publicly at all. | P1 |
| K6 | [IDEA] **Celebrate improvements** — "biggest gainers" exists but is styled identically to losers. Recognition is cheaper than shame and works better in volunteer contexts. | P2 |

---

## L. Bigger bets (post-Phase-1, for the record)

| # | Idea |
|---|---|
| L1 | **Fill the four missing activity metrics** — this is the single change that would most improve every other number in the app. Blocked on the upstream pipeline, not on the dashboard. |
| L2 | **Per-repo permalink pages with static OG images** so a shared link previews as a score card. |
| L3 | **Time-machine slider** — view the whole dashboard as of any snapshot date. |
| L4 | **Cohort comparison** — XBlocks vs frontends vs services vs libraries, using `language_bytes.*` and naming conventions as a proxy. |
| L5 | **Anomaly detection** — flag statistically unusual drops rather than fixed thresholds. |
| L6 | **Public API** (static JSON per snapshot) so others can build on the data. Cheap given the pre-compute architecture. |
| L7 | **"Health budget"** — let a WG set a target ("80% of critical repos at B or better by Q4") and track against it. |
| L8 | **Onboarding checklist for new repos** — the same checks, framed as a setup wizard for repo creators. |
| L9 | Reconsider **Streamlit** for the public read-only surface. Almost everything here is static per snapshot; a pre-rendered static site would be faster, fully accessible, styleable without fighting emotion CSS, and free to host. Keep Streamlit for the interactive/SQL/maintainer views. Large decision, worth naming explicitly. |

---

## Order of precedence

All 168 items, sorted into ten waves. Every ID appears exactly once. Waves are
ordered by *dependency first, then credibility-damage-per-unit-effort* — not by
the priority tags above, which rate items in isolation and can't express "this
must come after that".

> **Amended after the WP-1 harness ran.** A0, A0b, A14 and F13 were found by the
> audit harness on its first execution and did not exist in the original 164.
> A0/A0b jump to the front of Wave 1: until deep links render the real app, every
> screenshot baseline and every accessibility measurement is potentially of an
> unstyled page, which makes the rest of the plan unverifiable.

Three ordering rules drove this:

1. **Lead time before dev time.** Anything that depends on another person, an
   upstream pipeline change, or content authoring starts in Wave 0 regardless of
   its priority, because those items burn calendar, not sprint capacity.
2. **Stop asserting false things before improving true ones.** A dashboard that
   is wrong is worse than a dashboard that is ugly. Wave 1 is entirely
   disclosure and removal — almost no new UI.
3. **Primitives before pages.** Wave 3 builds the shared table / empty-state /
   chart helpers. Wave 4 rewrites seven pages *using* them. Reversing these two
   waves roughly doubles Wave 4.

---

### Wave 0 — Start immediately, finishes on someone else's clock

Not dashboard work. Every item is a request, a decision, or a content grind with
multi-week lead time, and each one gates a later wave. Kick all six off before
writing any code.

| Items | Why first | Gates |
|---|---|---|
| **L1** Collect the 4 missing activity metrics upstream | The single highest-value change in the whole document. Fixes half the composite score at the source. Pipeline work, not dashboard work. | B1, B3, A5, D9, D15 |
| **A3** Publish `dashboard_history.csv` upstream (currently 404) | Until this exists, every trend feature is dead in production no matter what we build. | A4, D5, D16, D25, D40–D45, all KPI deltas |
| **D34** Populate `tiers.yaml` beyond 4 of 171 repos | Curation decision for the WG. Needing Attention cannot work without it. | D32, D33, D37, A2 |
| **B5** Write the 63 missing check descriptions | Pure authoring grind, parallelisable, blocks four separate UI improvements. | D18, D47, D49, I10 |
| **B4** Decide: widen scoring beyond 3 of 76 checks, or reframe "informational vs scored" | Architectural decision with a config consequence. Cheap to decide, expensive to defer. | D49, B6 |
| **B8** Get maintainer sign-off on the provisional activity thresholds | Currently shipped as fact. Needs a human yes. | B1, B6 |
| **K5** Decide the "Bottom 5" naming-and-shaming framing | Community-political, not technical. Gates how Overview highlights and What Changed are worded. | D3, D12, K6 |

---

### Wave 1 — Stop the dashboard from asserting things that aren't true

The cheapest wave and the highest return. Mostly deletion, disclosure, and
greying-out — very little new UI. Should land as one release.

| Items | Change |
|---|---|
| **A0, A0b** | **First, ahead of everything.** Apply the base style from a shared per-page init helper so it survives a direct deep-link load, and enforce feature flags *inside* each gated page rather than only in the nav wiring. Until this lands, deep links render unstyled with the wrong nav, `/sql` `/badges` `/cards` `/healthz` are publicly reachable, and no visual or a11y measurement can be trusted. |
| **A14** | `sorted()` the unavailable-metrics set so radar axis order stops permuting between server starts. Lands with A0 because non-deterministic rendering also poisons the screenshot baselines. |
| **A5** | Radar must not plot unavailable metrics at radius 100. Draw them as an explicit "no data" band. |
| **B1, B2** | Put coverage *on* the gauge (ghosted arc for the uncomputable half) instead of in a fourth-position tile. |
| **B3** | Grey/annotate any sub-score whose coverage is below threshold, so `Activity 100.0` stops implying confidence. |
| **B7** | One distinct visual state for "scored 50 because data is absent" vs "genuinely scored 50", used everywhere. |
| **A1** | Dark mode: fix via Streamlit's native theming, or delete the toggle. Do not ship a control that does nothing. |
| **A2** | Tier filter: wire to a real `repo_tier` column, or remove from the sidebar. |
| **A4** | Label trend charts with their actual date range and warn when history is older than the snapshot. |
| **A6** | "Biggest losers" must not be able to show gains. |
| **A7** | Rename What Changed to match the comparison window it actually performs. |
| **A13** | Suppress `Commit: local` in the bulletin when `GITHUB_SHA` is unset. |
| **C4, D51** | Hide the Ownership section when coverage is 0 rather than shipping a dead nav section. |
| **D53** | Remove "PRD trigger threshold" and equivalent internal jargon from user-facing warnings. |

---

### Wave 2 — Visible-defect sweep

Independent one-liners and token fixes. No dependencies, no design decisions.
Batchable into a single afternoon each; good parallel work while Wave 0 runs.

**A8** hide index · **A9** gauge tick clipping · **A10** y-axis title clipping ·
**A11** pill/name collision · **A12** `exists..coveragerc` double-dot ·
**F1** `status-warn` contrast · **F2** sidebar placeholder contrast ·
**F3** metric-delta contrast · **F4 / E6** heading order ·
**E12** favicon · **E13** hide Deploy button and menu ·
**D6** duplicate snapshot caption · **D7** filler subtitle ·
**D8** explicit "no change" instead of a blank delta ·
**D17 + F13** copy-link → icon button (also removes the keyboard-inaccessible
`<pre>` scroll region) · **D19** filter label consistency ·
**D20** stop showing a Python repr · **B12** move "Scoring config" out of a KPI slot ·
**C3** move "Showing X of Y" under the filters · **I8** timezone on all dates

---

### Wave 3 — Build the primitives (must precede Wave 4)

Force multipliers. Each one collapses many Wave 4 findings into configuration.
`ui/tables.py` being 7 lines is why every page reinvented its own table.

| Items | Primitive |
|---|---|
| **E4, E2, E3** | One `render_repo_table()` — `column_config` labels, `NumberColumn` formats, grade pills, compact links. Closes ~12 findings across five pages. |
| **E1** | Route every chart through the themed helpers. Delete the raw `px.bar` / `px.line` path. |
| **I4, I5** | One empty-state component with consistent success/info/warning semantics. Seven pages currently use six treatments. |
| **E10, C2** | Wire up the already-written `render_freshness_banner()` in main content. Stale data stops being an amber dot in a dark sidebar. |
| **H2** | Cache `calculate_scores()`. Called uncached on every page. |
| **H1** | Load history once per render, not three times. |
| **H3** | Spinners / skeletons on the cold-cache path. |

---

### Wave 4 — Make each page do its job

The largest wave. Ordered *within* the wave by persona priority from PRD §1.2 —
WG lead first, maintainer second, browser third — so value lands early even if
the wave slips.

| Page | Items | Persona |
|---|---|---|
| **What Changed** | D40 empty-state, D41 period selector, D42 suppress empty bulletin, D43 render vs source, D44 score/grade change reporting, D45 narrative summary | 1 |
| **Needing Attention** | D32 rules that actually fire, D33 severity ordering, D35 table formatting, D36 explain tiers + link rules, D37 tier option labels + counts, D38 action/share hierarchy | 1 |
| **Failing Checks** | D31 invert into a check-first work queue, D26 readable chart, D27 discoverable filter, D28 headers and links, D29 actionable default view, D30 collapse triple title | 1–2 |
| **Repo Detail** | D18 status + human title in collapsed headers, D13 single search control, D14 link to GitHub, D15 replace the radar, D21 use the unused 111 columns, D22 chip copy, D23 sane default repo, D16 shrink or drop sparklines | 2 |
| **Overview** | D1 de-duplicate ribbon vs histogram, D3 format the mover tables, D4 validate implausible deltas, D9 rethink "Stale repos = 171", D11 make the full table workable, D12 "what to look at first", D2 label the F segment, D5 label the sparkline | 1–4 |
| **Checks Catalog** | D46 search/filter, D48 cross-link to failing repos, D49 separate scored from informational, D47 title fallback, D50 split roadmap from reference | 2–3 |
| **IA dedupe** | C5 merge Failing Checks with the Overview tab, C6 move movers to What Changed | all |

*C5 and C6 come last in this wave deliberately — deduplicating pages only makes
sense once you know what each page has become.*

---

### Wave 5 — Adoption, orientation, distribution

Wave 4 makes the dashboard good; Wave 5 makes people find it, understand it, and
paste it into Slack. Small work, direct effect on whether the tool gets used.

**C9** footer with source / data / privacy / feedback links ·
**K1** share links as first-class + OG metadata so pasted links preview ·
**D10** persistent share button in the header ·
**K4** report-a-problem / contribute-a-check path ·
**K2** flip the badges flag — highest-leverage distribution channel ·
**C8** global "jump to repo" from every page ·
**C1** sidebar order: brand and freshness above nav ·
**B6** a Scoring page: 9 metrics, weights, bands, the `default_when_missing` policy ·
**B11** grade-band tooltip on every pill · **B9** surface ties ·
**B10** n-metrics badge in table contexts ·
**I1** first-run orientation · **I2** de-jargon pass · **I3** actionable empty states ·
**I7** tell people how to fix the data gaps · **I6** use the unused tagline ·
**C7 / I9** one vocabulary for each concept · **C13** task-order the nav ·
**C12** breadcrumbs for deep-link arrivals

---

### Wave 6 — Close the action loop

This is the PRD's stated value proposition ("one-click paths to remediation") and
it comes *after* Wave 4 because it needs the reshaped Failing Checks page as its
surface.

**J6** state which failures are actionable before the user clicks ·
**J1** promote remediation out of three-levels-deep ·
**J4** rank checks by blast radius × ease — the most valuable artifact the dataset can produce ·
**J3** bulk action for the ~150-repo checks ·
**J2** state PR-template coverage ·
**I10** one "why this matters" sentence per check ·
**J7** Fix-it-Friday view · **J5** feedback that an action was taken

---

### Wave 7 — Accessibility and mobile, structurally

Token-level contrast fixes already landed in Wave 2. This wave is the structural
work, which is genuinely large. **Move this wave ahead of 5 and 6 if any
consumer has a procurement or compliance requirement** — several Open edX
operators are public-sector.

**F6** colour is never the sole signal · **F7** text alternatives for every chart ·
**F5** landmarks and skip-links · **F8** extend `aria-label` to all chips ·
**F9** contrast-check focus ring on both surfaces · **F10** keyboard path through long expander lists ·
**F11** audit all 15 `unsafe_allow_html` sites · **E11** distinguish grade A from B ·
**G1** a real mobile layout · **G2** responsive column collapse ·
**G3** reflowing charts · **G4** horizontal-scroll affordance · **G5** don't hide brand behind the hamburger ·
**G6** mobile glance view

---

### Wave 8 — Performance and robustness

Deferred deliberately: at 171 repos none of this is user-visible pain today. It
becomes urgent if the repo count grows or the app gets real traffic.

**H4** fragments on Repo Detail (currently re-renders everything per keystroke) ·
**H5** align snapshot and history TTLs · **H6** bound the per-repo history cache ·
**H7** `st.fragment` for filters and tabs · **H8** revisit `expected_min_columns: 100` vs actual 111 ·
**E5** self-host or drop the Google Fonts `@import`

---

### Wave 9 — Decide: do, defer, or drop

Not "later" so much as "unresolved". Each needs a yes/no before it earns a wave.
Several are reject candidates and that's a fine outcome.

**Cleanup decisions:** C10 wire up `strings.yaml` or delete it · C11 flag-off
pages (SQL/Badges/Cards) → Labs section or delete · E9 delete the unused `card()`
· E7 lighten the shadow treatment · E8 **is the custom dark sidebar worth its
fragility?** — `theme.py` already carries four defensive comments about fighting
Streamlit's emotion CSS

**Moot if C4 hides Ownership:** D52, D54, D55

**Feature proposals:** D24 compare mode · D25 per-repo score history ·
D39 triage state · K3 RSS/digest · K6 celebrate improvements ·
F12 publish an accessibility statement

**Bigger bets:** L2 static OG score cards · L3 time-machine slider ·
L4 cohort comparison · L5 anomaly detection · L6 public JSON API (cheap given
the pre-compute architecture) · L7 health budgets · L8 new-repo onboarding wizard

**Park explicitly:** **L9** — moving the public read-only surface off Streamlit.
Almost everything here is static per snapshot, so the case is real, but this
should not be decided in the same pass as a UX backlog.

---

### If only ten things get done

In this order: **A0 + A0b** (deep links render the real app; flags actually gate) ·
**L1** (fix the score at source) · **A3** (publish history) ·
**A5 + B1 + B2** (stop overstating the score) · **A1 + A2** (delete the two dead
controls) · **E2/E3/E4** (one table component) · **D31** (Failing Checks becomes
a work queue) · **D32** (Needing Attention actually fires) · **D40/D41** (What
Changed stops looking like nothing ever changes) · **C9 + K1** (footer and
shareable links) · **G1** (a mobile layout).

A0 leads because it is the only item that makes the *rest* of the list
measurable, and because it is currently shipping a disabled feature to the public.

That sequence addresses every P0, roughly two-thirds of the P1s by knock-on
effect, and touches all five personas.
