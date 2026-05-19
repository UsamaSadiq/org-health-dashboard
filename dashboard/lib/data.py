import pandas as pd
import requests
import os
from io import StringIO
from dashboard.lib.config import get_config
from datetime import datetime

# Create cache directory if needed
cache_dir = ".cache/dashboard_data/"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

def load_snapshot():
    """Fetch and validate the latest repository health data"""
    config = get_config('data_source')

    try:
        response = requests.get(config['csv_url'])
        response.raise_for_status()
        
        # Load CSV and validate schema
        df = pd.read_csv(StringIO(response.text))
        
        # Cache current snapshot
        cache_file = os.path.join(cache_dir, f'snapshot_{datetime.now().isoformat()}.csv')
        df.to_csv(cache_file, index=False)
        
        return df
        
    except Exception:
        # Fallback to most recent historical snapshot
        if os.path.exists(history_dir := os.path.join(cache_dir, 'history')):
            files = [f for f in os.listdir(history_dir) if f.startswith('snapshot_')]
            if files:
                return pd.read_csv(os.path.join(history_dir, sorted(files)[-1]))

    return pd.DataFrame()  # Final fallback