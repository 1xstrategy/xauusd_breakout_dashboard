import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import plotly.graph_objs as go

# -----------------------------
# CONFIG
# -----------------------------
API_KEY = '38346b35aee9444ca0d51e14105f849f'
SYMBOL = 'XAU/USD'
INTERVAL = '1min'

# -----------------------------
# FUNCTIONS
# -----------------------------

def fetch_data(start_date, end_date):
    url = f"https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "start_date": start_date,
        "end_date": end_date,
        "apikey": API_KEY,
        "timezone": "GMT",
        "outputsize": 5000
    }
    response = requests.get(url, params=params).json()
    if "values" in response:
        df = pd.DataFrame(response["values"])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        df = df.sort_index()
        return df.astype(float)
    else:
        st.warning("API limit hit or data not available.")
        return pd.DataFrame()

def get_combined_data(days):
    all_data = []
    today = datetime.utcnow()
    for i in range(0, days, 3):
        end_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        start_date = (today - timedelta(days=i+3)).strftime('%Y-%m-%d')
        df = fetch_data(start_date, end_date)
        all_data.append(df)
    return pd.concat(all_data)

def analyze_breakouts(df, sl_pts):
    df['date'] = df.index.date
    first_candles = df.groupby('date').first().rename(columns={
        'open': 'open_x', 'high': 'high_x', 'low': 'low_x', 'close': 'close_x'
    })
    df = df.join(first_candles, on='date')
    df['above_x'] = df['close'] > df['high_x']
    df['below_x'] = df['close'] < df['low_x']
    df['breakout_flag'] = df['above_x'] | df['below_x']
    df['day_index'] = df.groupby('date').cumcount()
    first_breakouts = df[df['breakout_flag']].groupby('date').first()

    point_moves = []
    trades = []

    for date, row in first_breakouts.iterrows():
        direction = 'up' if row['above_x'] else 'down'
        breakout_price = row['close']
        rest_of_day = df[(df['date'] == date) & (df.index > row.name)]
        move = 0

        for _, bar in rest_of_day.iterrows():
            if direction == 'up':
                if bar['low'] <= breakout_price - sl_pts:
                    move = -sl_pts
                    break
                move = bar['high'] - breakout_price
            else:
                if bar['high'] >= breakout_price + sl_pts:
                    move = -sl_pts
                    break
                move = breakout_price - bar['low']
        point_moves.append(move)
        trades.append({"date": date, "direction": direction, "move": move})

    return pd.DataFrame(trades), np.mean(point_moves), point_moves

# -----------------------------
# STREAMLIT APP
# -----------------------------

st.set_page_config(page_title="XAU/USD Breakout Dashboard", layout="wide")
st.title("📈 XAU/USD Breakout Strategy Analyzer")

col1, col2 = st.columns(2)
with col1:
    days = st.slider("How many past days to fetch?", 5, 30, 10)
with col2:
    stop_loss_pts = st.number_input("Stop Loss in Points", value=0.75, step=0.05)

if st.button("Run Backtest"):
    with st.spinner("Fetching data and analyzing..."):
        df = get_combined_data(days)
        trades_df, avg_move, moves = analyze_breakouts(df, stop_loss_pts)

    st.subheader("📊 Strategy Summary")
    st.write(f"**Average Move:** {avg_move:.2f} points")
    st.write(f"**Total Trades:** {len(moves)}")
    st.write(f"**Win Rate:** {(np.sum(np.array(moves) > 0) / len(moves)) * 100:.2f}%")

    st.subheader("📉 Equity Curve")
    equity_curve = np.cumsum(moves)
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=equity_curve, mode='lines', name='Equity'))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Trade Details")
    st.dataframe(trades_df)

st.sidebar.info("Note: You can get your free API key from twelvedata.com")
