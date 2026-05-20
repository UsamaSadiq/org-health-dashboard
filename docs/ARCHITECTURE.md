# Architecture

## Overview

This dashboard is a Streamlit application with a configuration-driven domain layer.

- UI orchestration: [streamlit_app.py](../streamlit_app.py)
- Pages: [pages](../pages)
- Domain logic: [dashboard/lib](../dashboard/lib)
- UI helpers: [dashboard/ui](../dashboard/ui)
- Configuration: [dashboard/config/openedx](../dashboard/config/openedx)

## Data flow

1. Snapshot is loaded from the upstream CSV URL in [dashboard/config/openedx/data_source.yaml](../dashboard/config/openedx/data_source.yaml).
2. Data integrity checks verify minimum shape and required columns.
3. On fetch failure, last-known-good cached snapshot is loaded.
4. Scoring is computed using [dashboard/config/openedx/scoring.yaml](../dashboard/config/openedx/scoring.yaml).
5. Pages render filtered views and export actions.

## Config validation

Config files are validated against JSON Schemas in [dashboard/config/schemas](../dashboard/config/schemas).
Runtime validation is non-fatal; strict validation should be used in CI.
