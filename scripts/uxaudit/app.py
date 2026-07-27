"""Start and reliably tear down a headless Streamlit server for the audit.

The harness owns the server rather than asking the operator to run
``streamlit run`` in another terminal. That makes every mode a single command,
and — more importantly — it makes the audited build unambiguous: whatever is on
disk right now is what gets screenshotted.

Three details are load-bearing:

  * **Readiness is polled, not slept for.** Streamlit's own
    ``/_stcore/health`` endpoint answers ``ok`` once the tornado server is
    accepting connections, which is the earliest moment Playwright can
    navigate. Per-page render waits are a separate concern; see
    ``pages.PageSpec.settle_seconds``.
  * **Output goes to a temp file, not a pipe.** Streamlit is chatty on stderr.
    A ``subprocess.PIPE`` nobody drains will eventually fill its buffer and
    wedge the server, so the log is spooled to a file we can read on failure.
  * **Teardown is unconditional and escalating.** The child gets its own
    session so a signal reaches the whole process group, ``SIGTERM`` first, and
    ``SIGKILL`` if it has not exited shortly after. An orphaned server holding
    a port is the classic way for a screenshot run to poison the next one.
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# scripts/uxaudit/app.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "streamlit_app.py"

_HEALTH_PATH = "/_stcore/health"
_POLL_INTERVAL = 0.25
_TERMINATE_GRACE = 5.0

# Deliberately not 8501: that is what a developer's own `streamlit run` takes,
# and the audit should never fight it for the port. See preferred_port() for
# why the audit wants a *stable* port at all.
DEFAULT_PORT = 8599


def find_free_port() -> int:
    """Return a port the OS reports as free.

    Binding to port 0 and reading back the assignment is inherently a
    time-of-check/time-of-use race, but it is the standard approach and the
    window is microseconds wide. Preferable to guessing 8501 and colliding with
    the developer's own ``streamlit run``.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _port_is_free(port: int) -> bool:
    """True if nothing is currently listening on ``port`` on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def preferred_port() -> int:
    """Return ``DEFAULT_PORT`` if it is free, otherwise any free port.

    Screenshot diffing needs the port to be *stable*, not merely free. The
    Repo Detail and Overview pages render a "Copy link to this view" box whose
    text comes from ``dashboard.lib.share.base_url()`` — i.e. it contains the
    live ``host:port``. Capture a baseline on port 58863 and a candidate on
    59468 and those pixels differ every single run, so ``--mode diff`` can never
    be green no matter how stable the UI is.

    Falling back to an ephemeral port keeps the harness runnable when 8599 is
    taken (two audits at once, or a stale server); the diff for those two pages
    is then expected to be noisy, which is the lesser evil versus refusing to
    run.
    """
    return DEFAULT_PORT if _port_is_free(DEFAULT_PORT) else find_free_port()


def _is_serving(base_url: str) -> bool:
    """True once Streamlit's health endpoint answers on ``base_url``."""
    try:
        with urllib.request.urlopen(base_url + _HEALTH_PATH, timeout=2) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _kill(process: subprocess.Popen[bytes]) -> None:
    """Terminate the server and everything it spawned, then reap it."""
    if process.poll() is not None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            # start_new_session=True made the child a group leader, so its pid
            # doubles as the group id.
            os.killpg(process.pid, sig)
        except (ProcessLookupError, PermissionError):
            try:
                process.kill()
            except ProcessLookupError:
                return
        try:
            process.wait(timeout=_TERMINATE_GRACE)
            return
        except subprocess.TimeoutExpired:
            continue


@contextmanager
def running_app(port: int | None = None, *, timeout: float = 60.0) -> Iterator[str]:
    """Run the dashboard headless for the duration of the ``with`` block.

    Args:
        port: Port to bind. Defaults to ``preferred_port()`` — the stable
            ``DEFAULT_PORT`` when available — so that screenshots stay
            comparable between runs.
        timeout: Seconds to wait for the server to start serving HTTP. The
            first start of a cold checkout has to import pandas, plotly and
            streamlit, so this is deliberately generous.

    Yields:
        The base URL of the running app, with no trailing slash, e.g.
        ``http://localhost:8599``.

    Raises:
        RuntimeError: If the server exits early or never becomes reachable
            within ``timeout``. The captured log is included in the message,
            because the interesting failure (a syntax error in a page, a
            missing dependency) is only visible there.
    """
    port = port or preferred_port()
    base_url = f"http://localhost:{port}"

    env = dict(os.environ)
    # The dashboard imports `dashboard.*` as a top-level package; the repo root
    # is only implicitly on sys.path when cwd happens to be it, so make it
    # explicit for the child.
    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{existing_path}" if existing_path else str(REPO_ROOT)
    # Suppress the first-run email prompt, which otherwise blocks on stdin.
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    # Pin the hash seed. Any page that iterates a set to build an ordered list
    # renders in a different order in every process, which shows up as a
    # screenshot diff on an unchanged checkout and makes the visual gate
    # useless. Repo Detail's radar chart does exactly this today. Pinning makes
    # the *harness* reproducible; it does not fix such ordering bugs, and those
    # are still worth fixing at the source with sorted().
    env["PYTHONHASHSEED"] = "0"

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ENTRYPOINT),
        "--server.port",
        str(port),
        "--server.address",
        "localhost",
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--browser.gatherUsageStats",
        "false",
    ]

    log_file = tempfile.NamedTemporaryFile(  # noqa: SIM115 — lifetime spans the block
        prefix="ux-audit-streamlit-", suffix=".log", delete=False
    )
    log_path = Path(log_file.name)
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        deadline = time.monotonic() + timeout
        while True:
            if _is_serving(base_url):
                break
            if process.poll() is not None:
                raise RuntimeError(
                    f"Streamlit exited with code {process.returncode} before serving "
                    f"{base_url}.\n--- server log ---\n{_read_log(log_path)}"
                )
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Streamlit did not serve {base_url} within {timeout:g}s.\n"
                    f"--- server log ---\n{_read_log(log_path)}"
                )
            time.sleep(_POLL_INTERVAL)

        yield base_url
    finally:
        if process is not None:
            _kill(process)
        log_file.close()
        log_path.unlink(missing_ok=True)


def _read_log(path: Path) -> str:
    """Best-effort read of the spooled server log, for error messages."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip() or "(empty)"
    except OSError as exc:
        return f"(could not read log: {exc})"
