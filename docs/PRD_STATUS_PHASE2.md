# PRD Status

Generated from prd_tasks_phase2.yaml

## Phase 02

- done: 6
- partial: 1
- todo: 1

- [-] 3.2.1 Badge endpoint (Option B)
  - Implemented badge SVG generation script and badge UI. Upstream wg-maintenance workflow wiring remains pending WG approval.
- [x] 3.2.2 DuckDB SQL query page
  - Implemented read-only SQL page with query sanitization, single-statement guard, and row cap enforcement.
- [x] 3.2.3 Maintainer and working-group views
  - Implemented ownership page with theme/squad summaries and ownership coverage indicator against 20% trigger.
- [x] 3.2.4 My repos filter
  - Implemented handle-based My Repos filter using ownership columns in ownership view page.
- [x] 3.2.5 Year-in-review and OpenGraph cards
  - Implemented static year-in-review HTML generation with OpenGraph metadata and card browser page.
- [x] 3.2.6 Embeddable score cards
  - Implemented per-repo embeddable HTML card generation and artifact listing page.
- [x] 3.2.7 OpenSSF Scorecard ingestion
  - Implemented Scorecard API client and parity panel in Repo Detail behind feature flag.
- [ ] 3.2.8 Hetzner self-host migration
  - Deferred. Trigger: repeated cold-start complaints or badge endpoint moved into dashboard.
