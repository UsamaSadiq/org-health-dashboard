from __future__ import annotations

import streamlit as st

from dashboard.lib.data import load_config, load_snapshot
from dashboard.lib.remediation import missing_remediation_checks


def _is_check_col(name: str) -> bool:
    return "." in name and not name.startswith("github.") and not name.startswith("language_bytes.")


def render() -> None:
    st.title("Glossary")

    descriptions = load_config("check_descriptions").get("checks", {})
    groups = load_config("check_groups").get("groups", [])
    df = load_snapshot()
    check_columns = sorted([col for col in df.columns if _is_check_col(col)]) if not df.empty else []

    if not check_columns:
        st.warning("No check columns detected in snapshot.")
        return

    missing_descriptions = [check for check in check_columns if check not in descriptions]
    missing_remediation = missing_remediation_checks(check_columns)

    st.subheader("Coverage gaps")
    c1, c2 = st.columns(2)
    c1.metric("Checks missing description", len(missing_descriptions))
    c2.metric("Checks missing remediation", len(missing_remediation))

    for group in groups:
        group_name = group.get("name", "Ungrouped")
        explicit = set(group.get("explicit", []))
        pattern = group.get("pattern")

        grouped_checks = []
        for check in check_columns:
            in_explicit = check in explicit
            in_pattern = bool(pattern and __import__("re").match(pattern, check))
            if in_explicit or in_pattern:
                grouped_checks.append(check)

        if not grouped_checks:
            continue

        st.subheader(group_name)
        for check in grouped_checks:
            info = descriptions.get(check, {})
            desc = info.get("description", "Missing description entry.")
            st.markdown(f"**{check}**")
            st.write(desc)
            meta_parts = []
            if info.get("chaoss_metric"):
                meta_parts.append(f"CHAOSS: {info['chaoss_metric']}")
            if info.get("scorecard_check"):
                meta_parts.append(f"Scorecard: {info['scorecard_check']}")
            if info.get("source_url"):
                meta_parts.append(f"Source: {info['source_url']}")
            if meta_parts:
                st.caption(" | ".join(meta_parts))
            if check in missing_descriptions:
                st.warning("Config gap: missing check description entry.")
            if check in missing_remediation:
                st.info("Documentation gap: no remediation entry.")


render()
