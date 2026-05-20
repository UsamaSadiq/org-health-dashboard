# Privacy

The dashboard does not collect personal data and does not store user-specific state server-side.

## Data sources

- Public upstream CSV published from the Open edX maintenance pipeline.
- Public GitHub metadata from repository history endpoints.

## Telemetry

- Streamlit usage stats are disabled via [.streamlit/config.toml](../.streamlit/config.toml).
- No third-party analytics SDK is included.

## Cookies

Any cookies are platform-level Streamlit session cookies. The dashboard does not set custom tracking cookies.
