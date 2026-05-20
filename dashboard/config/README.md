# Dashboard Configuration

This directory contains configuration for repository-health dashboard behavior.

## Layout

- `feature_flags.yaml`: global feature toggles.
- `openedx/*.yaml`: Open edX org-specific configuration.
- `schemas/*.schema.json`: JSON Schemas used to validate config payloads at load time.

## Validation Behavior

- Runtime: non-fatal. Invalid config is logged and the dashboard continues running.
- Strict mode: CI/tests may enable strict validation and fail on invalid payloads.

## Schema Coverage

- `feature_flags.schema.json`
- `data_source.schema.json`
- `check_groups.schema.json`
- `check_descriptions.schema.json`
- `remediation.schema.json`
- `pr_templates.schema.json`
- `scoring.schema.json`
- `tiers.schema.json`
- `attention_rules.schema.json`
- `strings.schema.json`
- `org_branding.schema.json`
