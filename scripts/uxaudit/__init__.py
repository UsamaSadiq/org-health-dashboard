"""UX audit harness for the Open edX repo health dashboard.

The package exists so that the visual and accessibility acceptance criteria in
``docs/UX_REMEDIATION_PLAN.md`` are *provable* rather than eyeballed. Clipped
axes, colliding pills, and contrast failures are invisible to the unit tests in
``tests/``, so every work package that touches UI is verified here instead.

Layout, and who owns what:

  ``pages.py``      the page inventory (URL paths, per-page settle times) and
                    the viewport matrix. The single source of truth for "what
                    do we audit".
  ``app.py``        starts and reliably tears down a headless Streamlit server
                    so the whole harness is one command with no manual setup.
  ``capture.py``    Playwright screenshots, scroll-and-stitched because
                    Streamlit scrolls ``section[data-testid="stMain"]`` rather
                    than the document.
  ``a11y.py``       axe-core scan, partitioned into blocking vs accepted.
  ``imagediff.py``  pixel comparison of candidates against ``tests/baseline/``.

The CLI entrypoint is ``scripts/ux_audit.py``; nothing here is imported by the
dashboard itself.
"""
from __future__ import annotations
