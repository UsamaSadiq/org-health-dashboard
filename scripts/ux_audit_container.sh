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
# The image is pinned by digest, not by tag. A tag is a mutable pointer, and this
# one is rebuilt for OS security patches — a freetype or fontconfig change moves
# text rasterisation. CI pulls fresh on every job while Docker here reuses an
# already-present tag, so the two would silently drift apart and reintroduce the
# cross-machine font failure this script exists to prevent. The digest must stay
# in step with the `container:` image in .github/workflows/ux-audit.yml and with
# the playwright pin in requirements-dev.txt.
set -euo pipefail

IMAGE="mcr.microsoft.com/playwright/python:v1.60.0-noble@sha256:8ff591d613b01c884cc488339ed4318b4513eaf0c57a164a878ba49e70e3f384"
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

# Run as the invoking user on Linux, where the bind mount shares the host's uid
# namespace: as root, everything the run *creates* — .ux-audit/current/,
# .ux-audit/diff/ — lands root-owned on the host. The next plain
# `python scripts/ux_audit.py` then fails, and confusingly: ux_audit.py clears
# .ux-audit/current with `ignore_errors=True`, so the denied removal is silent
# and the run dies later on a PermissionError writing into it. Recovery needs
# sudo, for what looked like a harness bug.
#
# Docker Desktop (macOS, Windows) already maps ownership back to the invoking
# user, and passing -u there would instead break the image's own paths, so this
# is Linux-only. Non-root means the install cannot write to system site-packages,
# hence --user and PYTHONUSERBASE below.
USER_FLAG=()
PIP_TARGET_FLAG="--break-system-packages"
if [ "$(uname -s)" = "Linux" ]; then
  USER_FLAG=(-u "$(id -u):$(id -g)")
  PIP_TARGET_FLAG="--user"
fi

exec docker run --rm "${TTY_FLAG[@]}" "${USER_FLAG[@]}" \
  -v "$REPO_ROOT":/work \
  -v "$PIP_CACHE_VOLUME":/pip-cache \
  -w /work \
  -e HOME=/tmp \
  -e PIP_CACHE_DIR=/pip-cache \
  -e PYTHONUSERBASE=/tmp/pybase \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e PIP_TARGET_FLAG="$PIP_TARGET_FLAG" \
  "$IMAGE" \
  bash -euc '
    # The same install the workflow runs. The image is externally managed, so
    # --break-system-packages is what puts these alongside its preinstalled
    # playwright — the same flag, into the same interpreter, as CI. The
    # non-root Linux path uses --user instead, which resolves to the same
    # interpreter and the same pinned versions.
    export PATH="/tmp/pybase/bin:$PATH"
    pip install --quiet "$PIP_TARGET_FLAG" -r requirements.txt -r requirements-dev.txt
    exec python scripts/ux_audit.py "$@"
  ' bash "$@"
