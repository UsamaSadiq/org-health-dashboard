import streamlit as st

from dashboard.lib.data import load_snapshot

def main():
    st.title('Open edX Repository Health Dashboard')
    df = load_snapshot()
    st.dataframe(df.head())

if __name__ == '__main__':
    main()