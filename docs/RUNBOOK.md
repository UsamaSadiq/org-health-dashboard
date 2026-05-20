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
