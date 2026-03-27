import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pandas_ta as ta
import time
import asyncio
import nest_asyncio

nest_asyncio.apply()

st.set_page_config(page_title="Quotex OTC Signals", layout="wide")
st.title("🚀 Quotex OTC Signals - 1 & 5 Min")

with st.sidebar:
    st.header("Settings")
    email = st.text_input("Quotex Email")
    password = st.text_input("Quotex Password", type="password")
    timeframe = st.selectbox("Timeframe", ["1 Minute", "5 Minutes"])
    assets = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD", "EURJPY", "GBPJPY"]
    asset = st.selectbox("Pair (OTC auto)", assets)
    refresh = st.slider("Refresh every (sec)", 5, 30, 10)

def generate_signal(df):
    if len(df) < 50:
        return "NOT ENOUGH DATA", 0
    df['rsi'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['macd_signal'] = macd['MACDs_12_26_9']
    stoch = ta.stoch(df['high'], df['low'], df['close'])
    df['stoch_k'] = stoch['STOCHk_14_3_3']
    df['ema50'] = ta.ema(df['close'], length=50)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    signals = []
    if latest['rsi'] < 30: signals.append("CALL")
    elif latest['rsi'] > 70: signals.append("PUT")
    
    if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
        signals.append("CALL")
    elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
        signals.append("PUT")
    
    if latest['stoch_k'] < 20: signals.append("CALL")
    elif latest['stoch_k'] > 80: signals.append("PUT")
    
    if latest['close'] > latest['ema50']: signals.append("CALL")
    else: signals.append("PUT")
    
    call_count = signals.count("CALL")
    if call_count >= 3:
        return "CALL (BUY) 🔥", round((call_count / 4) * 100)
    elif signals.count("PUT") >= 3:
        return "PUT (SELL) 🔥", round((signals.count("PUT") / 4) * 100)
    return "NEUTRAL / WAIT", 0

# Note: quotexpy connection moved to try-except for better debugging
if email and password and st.button("🔄 Get Live Signal", type="primary"):
    with st.spinner("Connecting to Quotex..."):
        try:
            from quotexpy import Quotex
            from quotexpy.utils import asset_parse
            from quotexpy.utils.account_type import AccountType
            from quotexpy.utils.candles_period import CandlesPeriod
            
            client = Quotex(email=email, password=password, headless=True)
            connected, message = asyncio.run(client.connect())
            
            if not connected:
                st.error(f"Login failed: {message}")
            else:
                client.change_account(AccountType.PRACTICE)
                asset_name = asset_parse(asset)
                # Try OTC if needed
                if not client.check_asset(asset_name)[2]:
                    asset = f"{asset}_OTC"
                    asset_name = asset_parse(asset)
                
                period = CandlesPeriod.ONE_MINUTE if timeframe == "1 Minute" else CandlesPeriod.FIVE_MINUTES
                candles = asyncio.run(client.get_candle_v2(asset_name, period))
                client.close()
                
                if candles and len(candles) > 50:
                    df = pd.DataFrame(candles)
                    df = df[['time', 'open', 'high', 'low', 'close']].copy()
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df = df.sort_values('time')
                    
                    signal, conf = generate_signal(df)
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        fig = go.Figure(data=[go.Candlestick(x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
                        fig.update_layout(height=650, title=f"{asset} - {timeframe}")
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.metric("SIGNAL", signal, f"{conf}% Confidence")
                        if "CALL" in signal:
                            st.success("STRONG BUY")
                        elif "PUT" in signal:
                            st.error("STRONG SELL")
                        else:
                            st.warning("WAIT")
                    
                    st.dataframe(df.tail(10), hide_index=True)
                else:
                    st.error("Failed to fetch enough candles. Try again.")
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Try using a DEMO account or check your credentials.")

st.caption("Use DEMO account first. Markets are risky — no signal is 100%.")
