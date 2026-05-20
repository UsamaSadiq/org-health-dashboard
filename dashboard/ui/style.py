from __future__ import annotations

import streamlit as st


def apply_base_style() -> None:
    st.markdown(
        """
        <style>
          .small-muted { color: #4b5563; font-size: 0.9rem; }
          .grade-pill { padding: 2px 8px; border-radius: 999px; font-weight: 600; }
          .grade-a { background: #166534; color: white; }
          .grade-b { background: #15803d; color: white; }
          .grade-c { background: #ca8a04; color: #111827; }
          .grade-d { background: #ea580c; color: white; }
          .grade-f { background: #dc2626; color: white; }
        </style>
        """,
        unsafe_allow_html=True,
    )
