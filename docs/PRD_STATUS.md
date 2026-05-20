# PRD Status

Generated from prd_tasks_phase1.yaml

## Phase 01

- done: 12
- partial: 0
- todo: 0

- [x] 3.1.1 Architectural refactor
  - Modularized app into dashboard/lib, dashboard/ui, pages, config, and tests.
- [x] 3.1.2 Visualizations-first UX
  - Overview starts with KPI/charts; table is toggle-based; failing checks chart uses Plotly selection.
- [x] 3.1.3 Repo Detail URL/search/compare
  - Fuzzy search, deep link, compare mode, mini-cards, and category sparkline support implemented.
- [x] 3.1.4 Deep links and shareable state
  - State serialize/normalize helpers and per-page share-link controls implemented.
- [x] 3.1.5 Filter-aware exports
  - CSV and JSON exports include filter metadata and snapshot context.
- [x] 3.1.6 Remediation snippets
  - Config-driven remediation entries with snippet rendering/copy surface.
- [x] 3.1.7 Issue-filing deep links
  - GitHub issue URL generation with prefilled title/body and optional metadata.
- [x] 3.1.8 Trend dimension
  - History loading, weekly delta tab, and bulletin export implemented.
- [x] 3.1.9 9-metric scoring layer
  - Config-based scoring with unavailable metric handling and grade outputs implemented.
- [x] 3.1.10 Discoverability: tooltips and glossary
  - Glossary page, check descriptions, and inline check guidance implemented.
- [x] 3.1.11 Repos needing attention view
  - Rule-driven attention page with tier filtering and exports.
- [x] 3.1.12 PR template generator
  - Whitelist and compare-link PR generation for safe checks implemented.
