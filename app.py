import streamlit as st
import asyncio
import pandas as pd
import plotly.graph_objects as go
from quotexpy import Quotex
from quotexpy.utils import asset_parse, asrun
from quotexpy.utils.account_type import AccountType
from quotexpy.utils.candles_period import CandlesPeriod
import pandas_ta as ta
import time
import nest_asyncio

nest_asyncio.apply()

st.set_page_config(page_title="Quotex OTC Signals", layout="wide")
st.title("🚀 Quotex OTC Signals - 1 & 5 Min (Live)")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("Login (Demo Account Recommended)")
    email = st.text_input("Quotex Email")
    password = st.text_input("Quotex Password", type="password")
    timeframe = st.selectbox("Timeframe", ["1 Minute", "5 Minutes"])
    asset_list = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD", "EURJPY", "GBPJPY"]
    asset = st.selectbox("OTC Pair (auto switches to OTC if needed)", asset_list)
    refresh_interval = st.slider("Auto Refresh (seconds)", 5, 30, 10)

# ====================== STRATEGY (High-Accuracy Filter) ======================
def generate_signal(df):
    # Indicators
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
    # RSI
    if latest['rsi'] < 30: signals.append("CALL")
    elif latest['rsi'] > 70: signals.append("PUT")
    
    # MACD
    if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
        signals.append("CALL")
    elif latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
        signals.append("PUT")
    
    # Stochastic
    if latest['stoch_k'] < 20: signals.append("CALL")
    elif latest['stoch_k'] > 80: signals.append("PUT")
    
    # EMA Trend
    if latest['close'] > latest['ema50']: signals.append("CALL")
    else: signals.append("PUT")
    
    # Final decision (majority + confidence)
    call_count = signals.count("CALL")
    put_count = signals.count("PUT")
    
    if call_count >= 3:
        return "CALL (BUY) 🔥", round((call_count/4)*100)
    elif put_count >= 3:
        return "PUT (SELL) 🔥", round((put_count/4)*100)
    else:
        return "NEUTRAL / WAIT", 0

# ====================== ASYNC QUOTEX DATA ======================
async def fetch_candles(email, password, asset, tf):
    client = Quotex(email=email, password=password, headless=True)
    connected = await client.connect()
    if not connected:
        return None, "Login failed"
    
    client.change_account(AccountType.PRACTICE)
    
    # Auto OTC fallback
    asset_query = asset_parse(asset)
    asset_open = client.check_asset(asset_query)
    if not asset_open or not asset_open[2]:
        asset = f"{asset}_OTC" if not asset.endswith("_OTC") else asset
        asset_query = asset_parse(asset)
    
    period = CandlesPeriod.ONE_MINUTE if tf == "1 Minute" else CandlesPeriod.FIVE_MINUTES
    
    candles = await client.get_candle_v2(asset, period)
    client.close()
    
    if not candles or len(candles) < 50:
        return None, "Not enough data"
    
    # Convert to DataFrame
    df = pd.DataFrame(candles)
    df = df[['time', 'open', 'high', 'low', 'close']].copy()
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.sort_values('time')
    return df, None

# ====================== MAIN APP ======================
if email and password:
    if st.button("🔄 Refresh Signals Now", type="primary"):
        with st.spinner("Fetching live candles from Quotex..."):
            df, error = asyncio.run(fetch_candles(email, password, asset, timeframe))
            
            if error:
                st.error(error)
            else:
                signal, confidence = generate_signal(df)
                
                col1, col2, col3 = st.columns([2,1,1])
                with col1:
                    st.subheader(f"{asset} - {timeframe}")
                    fig = go.Figure(data=[go.Candlestick(
                        x=df['time'],
                        open=df['open'], high=df['high'],
                        low=df['low'], close=df['close']
                    )])
                    fig.update_layout(height=600)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.metric("CURRENT SIGNAL", signal, f"{confidence}% Confidence")
                    if "CALL" in signal:
                        st.success("✅ STRONG BUY SIGNAL")
                    elif "PUT" in signal:
                        st.error("✅ STRONG SELL SIGNAL")
                    else:
                        st.warning("⏳ WAIT FOR CLEAR SIGNAL")
                
                with col3:
                    st.subheader("Last 10 Candles")
                    st.dataframe(df.tail(10)[['time','open','high','low','close']], hide_index=True)
                
                st.success(f"✅ Signal generated at {time.strftime('%H:%M:%S')} (OTC pair auto-selected)")
else:
    st.info("👆 Enter your Quotex credentials (use DEMO account for safety)")

# Auto-refresh
if refresh_interval:
    time.sleep(refresh_interval)
    st.rerun()
