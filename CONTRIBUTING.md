# Contributing to Open edX Repository Health Dashboard

This project is AGPL-3.0-or-later licensed and follows the contributor license agreement (CLA) described in [CLA.md](CLA.md). We use cla-assistant to enforce CLA compliance.

## Getting Started
1. Fork this repository
2. Create a new branch for your changes
3. Make your changes following the [prD.md](docs/prD.md) requirements
4. Open a PR with detailed description
5. Sign CLA if prompted
6. Fix any test or lint failures

## prD Compliance
All changes must maintain compliance with prD v3 requirements:
- Follow the directory structure in PRD section 7.11
- Maintain config validation requirements
- Preserve all feature flags in config/openedx/feature_flags.yaml
- Keep UI strings in the centralization config

## Testing
1. Run `flake8 .` for linter checks
2. Run `mypy .` for typechecker
3. Check all visualizations in Streamlit app

## prD Reference
For detailed implementation roadmap see [prD.md](docs/prD.md)