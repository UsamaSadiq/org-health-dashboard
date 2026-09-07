#!/usr/bin/env bash
#
# Run scripts/ux_audit.py inside the same container CI uses.
#
#   scripts/ux_audit_container.sh --mode diff
#   scripts/ux_audit_container.sh --mode baseline
#   scripts/ux_audit_container.sh --mode a11y --pages overview
#
# Why this exists: the screenshot baselines in tests/baseline/ are byte-compared,
# and text rasterisation differs between operating systems. A baseline captured
# on macOS fails against a Linux runner on font rendering alone — measured at
# 1.2-10.6% of pixels changed, with page heights shifting 25px from line-wrap
# differences. Any tolerance loose enough to absorb that is far too loose to
# catch a clipped axis label, which is the whole point of the gate.
#
# So there is exactly one reference environment, this image, and everyone renders
# in it. Running ux_audit.py directly on macOS is still useful for --mode a11y
# and for eyeballing --mode screenshots; it is only --mode diff and --mode
# baseline that need the container.
#
# The image tag must stay in step with the playwright pin in requirements-dev.txt
# and with the `container:` image in .github/workflows/ux-audit.yml.
set -euo pipefail

IMAGE="mcr.microsoft.com/playwright/python:v1.60.0-noble"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker info >/dev/null 2>&1; then
  echo "error: Docker is not running. Start Docker Desktop (or your daemon) and retry." >&2
  echo "       Without it, baselines captured here will not match CI." >&2
  exit 1
fi

# A named volume for pip's download cache, so the dependency install is a local
# unpack (a few seconds) rather than a re-download on every invocation. Only a
# cache: the install itself still runs each time, which is what keeps this
# identical to the CI step rather than merely similar. Drop it with
# `docker volume rm org-health-dashboard-audit-pip` if it ever misbehaves.
PIP_CACHE_VOLUME="org-health-dashboard-audit-pip"

# -t only when stdout is a terminal, so CI and pipes still work.
TTY_FLAG=()
[ -t 1 ] && TTY_FLAG=(-t)

exec docker run --rm "${TTY_FLAG[@]}" \
  -v "$REPO_ROOT":/work \
  -v "$PIP_CACHE_VOLUME":/pip-cache \
  -w /work \
  -e HOME=/tmp \
  -e PIP_CACHE_DIR=/pip-cache \
  -e PYTHONDONTWRITEBYTECODE=1 \
  "$IMAGE" \
  bash -euc '
    # Exactly the install the workflow runs. The image is externally managed, so
    # --break-system-packages is what puts these alongside its preinstalled
    # playwright — the same flag, into the same interpreter, as CI.
    pip install --quiet --break-system-packages -r requirements.txt -r requirements-dev.txt
    exec python scripts/ux_audit.py "$@"
  ' bash "$@"
