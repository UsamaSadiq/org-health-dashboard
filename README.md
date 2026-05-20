# Open edX Repository Health Dashboard

![License](https://img.shields.io/badge/License-AGPL3.0-blue.svg) ![CLA](https://img.shields.io/badge/CLA-required-brightgreen.svg)

The Open edX Repository Health Dashboard is a community tool that provides visualization and analytical capabilities for Open edX repository health metrics. This implementation follows the [v3 PRD document](docs/PRD.md). The project is licensed under AGPL-3.0-or-later with CLA enforced via cla-assistant.

## Key Features
- 9-metric scoring system with CHAOSS and OpenSSF Scorecard integration
- Historical trend analysis and delta detection
- Deep linking and filter-preserving exports
- Configurable remediation snippets and auto-PR generation
- Org-specific configuration and visualization rules

## Contributing
Please review [CLA.md](CLA.md) before contributing.

## PRD Status Tracking
Phase 01 tracking source is [docs/prd_tasks_phase1.yaml](docs/prd_tasks_phase1.yaml).
Phase 02 tracking source is [docs/prd_tasks_phase2.yaml](docs/prd_tasks_phase2.yaml).
Regenerate status report with:

python scripts/update_prd_status.py --generate-only

Generate Phase 02 status report with:

python scripts/update_prd_status.py --task-file docs/prd_tasks_phase2.yaml --status-file docs/PRD_STATUS_PHASE2.md --generate-only

Update one task and regenerate in one step with:

python scripts/update_prd_status.py --set 3.1.8 done --notes "Implemented weekly deltas and bulletin export"

Update one Phase 02 task and regenerate in one step with:

python scripts/update_prd_status.py --task-file docs/prd_tasks_phase2.yaml --status-file docs/PRD_STATUS_PHASE2.md --set 3.2.2 done --notes "Enabled SQL page behind feature flag and added timeout controls"

Generated report: [docs/PRD_STATUS.md](docs/PRD_STATUS.md).
Generated Phase 02 report: [docs/PRD_STATUS_PHASE2.md](docs/PRD_STATUS_PHASE2.md).