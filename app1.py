import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import asyncio
import nest_asyncio
import time

nest_asyncio.apply()

st.set_page_config(page_title="Quotex OTC Signals", layout="wide")
st.title("🚀 Quotex OTC Signals - 1 & 5 Min (Live)")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("Login (Use DEMO Account)")
    email = st.text_input("Quotex Email")
    password = st.text_input("Quotex Password", type="password")
    timeframe = st.selectbox("Timeframe", ["1 Minute", "5 Minutes"])
    assets = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD", "EURJPY", "GBPJPY"]
    asset = st.selectbox("OTC Pair (auto OTC fallback)", assets)
    refresh_interval = st.slider("Auto Refresh (seconds)", 5, 30, 10)

# ====================== PURE PANDAS INDICATORS ======================
def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def calculate_stoch_k(high, low, close, period=14):
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()
    return 100 * (close - lowest_low) / (highest_high - lowest_low)

def calculate_ema(close, period=50):
    return close.ewm(span=period, adjust=False).mean()

def generate_signal(df):
    if len(df) < 50:
        return "NOT ENOUGH DATA", 0
    
    df['rsi'] = calculate_rsi(df['close'])
    df['macd'], df['macd_signal'] = calculate_macd(df['close'])
    df['stoch_k'] = calculate_stoch_k(df['high'], df['low'], df['close'])
    df['ema50'] = calculate_ema(df['close'])
    
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
    put_count = signals.count("PUT")
    
    if call_count >= 3:
        return "CALL (BUY) 🔥", round((call_count / 4) * 100)
    elif put_count >= 3:
        return "PUT (SELL) 🔥", round((put_count / 4) * 100)
    return "NEUTRAL / WAIT", 0

# ====================== QUOTEX FETCH ======================
async def fetch_candles(email, password, asset, tf):
    try:
        from quotexpy import Quotex
        from quotexpy.utils import asset_parse
        from quotexpy.utils.account_type import AccountType
        from quotexpy.utils.candles_period import CandlesPeriod
        
        client = Quotex(email=email, password=password, headless=True)
        status = await client.connect()
        
        if not status:
            return None, "Login failed - check credentials"
        
        client.change_account(AccountType.PRACTICE)
        
        # Auto OTC fallback
        asset_name = asset_parse(asset)
        asset_info = client.check_asset(asset_name)
        if not asset_info or not asset_info[2]:
            asset = f"{asset}_OTC" if not asset.endswith("_OTC") else asset
            asset_name = asset_parse(asset)
        
        period = CandlesPeriod.ONE_MINUTE if tf == "1 Minute" else CandlesPeriod.FIVE_MINUTES
        candles = await client.get_candle_v2(asset_name, period)
        client.close()
        
        if not candles or len(candles) < 50:
            return None, "Not enough candles"
        
        df = pd.DataFrame(candles)
        df = df[['time', 'open', 'high', 'low', 'close']].copy()
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.sort_values('time').reset_index(drop=True)
        return df, None
    except Exception as e:
        return None, f"Error: {str(e)}"

# ====================== MAIN APP ======================
if email and password:
    if st.button("🔄 Get Live Signal Now", type="primary"):
        with st.spinner("Connecting to Quotex & fetching candles..."):
            df, error = asyncio.run(fetch_candles(email, password, asset, timeframe))
            
            if error:
                st.error(error)
            else:
                signal, confidence = generate_signal(df)
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"{asset} — {timeframe}")
                    fig = go.Figure(data=[go.Candlestick(
                        x=df['time'], open=df['open'], high=df['high'],
                        low=df['low'], close=df['close']
                    )])
                    fig.update_layout(height=650)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.metric("CURRENT SIGNAL", signal, f"{confidence}% Confidence")
                    if "CALL" in signal:
                        st.success("✅ STRONG BUY")
                    elif "PUT" in signal:
                        st.error("✅ STRONG SELL")
                    else:
                        st.warning("⏳ WAIT")
                
                st.dataframe(df.tail(10)[['time','open','high','low','close']], hide_index=True)
                st.success(f"✅ Updated at {time.strftime('%H:%M:%S')} (OTC auto-selected)")

else:
    st.info("👆 Enter your Quotex DEMO credentials above")

st.caption("Use DEMO account only. No signal is 100% — test thoroughly.")
