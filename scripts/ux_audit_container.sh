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

# A named volume for site-packages so the ~40s dependency install happens once
# rather than on every invocation. Delete it with
# `docker volume rm org-health-dashboard-audit-deps` after changing a pin.
DEPS_VOLUME="org-health-dashboard-audit-deps"

# -t only when stdout is a terminal, so CI and pipes still work.
TTY_FLAG=()
[ -t 1 ] && TTY_FLAG=(-t)

exec docker run --rm "${TTY_FLAG[@]}" \
  -v "$REPO_ROOT":/work \
  -v "$DEPS_VOLUME":/opt/audit-venv \
  -w /work \
  -e HOME=/tmp \
  -e PYTHONDONTWRITEBYTECODE=1 \
  "$IMAGE" \
  bash -euc '
    # Reuse the cached venv when its marker matches the current pins, so a
    # changed requirements file reinstalls instead of silently running stale
    # versions — which would produce baselines nobody else can reproduce.
    marker=/opt/audit-venv/.pins
    current=$(cat requirements.txt requirements-dev.txt | sha256sum | cut -d" " -f1)
    if [ ! -f "$marker" ] || [ "$(cat "$marker")" != "$current" ]; then
      python -m venv /opt/audit-venv
      /opt/audit-venv/bin/pip install --quiet --upgrade pip
      /opt/audit-venv/bin/pip install --quiet -r requirements.txt -r requirements-dev.txt
      printf %s "$current" > "$marker"
    fi
    exec /opt/audit-venv/bin/python scripts/ux_audit.py "$@"
  ' bash "$@"
