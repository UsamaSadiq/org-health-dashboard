# Open edX Repo Health Dashboard

Public dashboard for Open edX repository health checks.

- **Data source:** [openedx/wg-maintenance](https://github.com/openedx/wg-maintenance) (`dashboards/dashboard_main.csv`)
- **Refresh cadence:** Daily (data pipeline), 5-minute cache (dashboard)
- **Built with:** Streamlit Community Cloud

## Local Development

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (public)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with GitHub → **New app**
4. Select repo, branch `main`, main file `streamlit_app.py`
5. Click **Deploy** — public URL live within ~2 minutes

No secrets, environment variables, or paid tier required.
