# Vendored third-party assets

## `axe.min.js` — axe-core 4.10.2

| | |
|---|---|
| **Version** | 4.10.2 |
| **Source URL** | `https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js` |
| **Retrieved** | 2026-07-27 |
| **Size** | 553,290 bytes |
| **SHA-256** | `b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3` |
| **Licence** | Mozilla Public License 2.0 — © 2015–2024 Deque Systems, Inc. |
| **Consumed by** | `scripts/uxaudit/a11y.py` (`run_axe`, via `page.add_script_tag`) |

### Why this is committed rather than fetched

`scripts/ux_audit.py --mode a11y` is a **CI gate**. Fetching the scanner from a
CDN at scan time would make the gate:

- **network-dependent** — a jsdelivr outage or a locked-down runner turns a
  code-quality gate into a flaky one, and "the a11y job is red again" is how
  gates get disabled;
- **non-reproducible** — a floating fetch means the rule set can change without
  a commit in this repo. axe-core adds and retunes rules between patch
  releases, so an unpinned scanner can fail a PR that changed nothing. The
  allowlist in `a11y.py` is calibrated against *this* rule set;
- **unauditable** — nothing would record which scanner produced a given report.

600KB in the tree buys a gate that gives the same answer on a laptop with the
Wi-Fi off as it does on a runner. Injection reads this file from disk; there is
no network call on the a11y path.

### Upgrading

1. Download the new `axe.min.js`, replace this file, update the table above
   (version, URL, date, size, checksum).
2. Re-run `scripts/ux_audit.py --mode a11y` and diff the report against the
   previous run. A new axe version routinely surfaces new rules.
3. Triage every new rule explicitly into blocking or `KNOWN_ACCEPTED` in
   `scripts/uxaudit/a11y.py`. Do not widen the allowlist to make the gate green
   again — that is the failure mode the allowlist exists to prevent.

### Licence obligations

MPL-2.0 is a file-level copyleft. This is an unmodified redistribution, so the
obligations are satisfied by keeping the licence header that is already at the
top of `axe.min.js` intact and by pointing at the upstream source (above). Do
not reformat, re-minify, or strip comments from the file. If it ever needs
patching, the modified file must stay under MPL-2.0 and the change must be
described here.
