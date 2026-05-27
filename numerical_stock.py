import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.integrate import simpson

# ==========================================
# ⚙️ 系統初始化與快取設定
# ==========================================
st.set_page_config(page_title="台股價值防禦區雷達", layout="wide")

# 🎯 加入快取防護罩，避免被 Yahoo Finance 封鎖 IP
@st.cache_data(ttl=3600, show_spinner=False)
def load_data(ticker, period):
    return yf.Ticker(ticker).history(period=period)

# ==========================================
# 🎛️ 側邊欄 UI 設定
# ==========================================
st.sidebar.title("參數設定")
ticker = st.sidebar.text_input("股票代碼", "2330.TW")
period = st.sidebar.selectbox("分析天數", ["1mo", "3mo", "6mo", "1y"], index=2)
bins_count = st.sidebar.slider("積分區間切割數 (N)", min_value=20, max_value=100, value=50)
btn = st.sidebar.button("執行數值積分")

# ==========================================
# 📊 主畫面與核心邏輯
# ==========================================
st.title("🛡️ 數值分析期末專案 - 台股價值防禦區雷達")

# 這裡的縮排絕對精準，請放心服用
if btn:
    with st.spinner("正在執行辛普森積分與價值區間運算..."):
        
        # 1. 抓取資料 (使用快取)
        try:
            df = load_data(ticker, period)
        except Exception as e:
            st.error("⚠️ Yahoo Finance 伺服器目前連線擁擠，請稍後再試！")
            st.stop()
            
        # 2. 空包彈攔截：檢查有沒有抓到資料！
        if df.empty:
            st.error(f"⚠️ 找不到股票代碼【{ticker}】的資料！請確認代碼是否輸入正確（台股記得加 .TW）。")
            st.stop()

        # 3. 時區處理 (避免套件衝突)
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        prices = df['Close'].values
        volumes = df['Volume'].values

        # 防呆：資料太少無法積分
        if len(prices) < 2:
            st.error("⚠️ 資料筆數不足，無法進行數值積分！")
            st.stop()

        # ==========================================
        # 🧮 核心演算法：數值積分與 70% 尋寶
        # ==========================================
        min_p, max_p = np.min(prices), np.max(prices)

        # 建立等距價格網格
        price_bins = np.linspace(min_p, max_p, bins_count)
        dp = price_bins[1] - price_bins[0]

        # 分配成交量到對應的價格區間內
        vol_profile = np.zeros(bins_count)
        indices = np.digitize(prices, price_bins)
        for i in range(len(prices)):
            idx = min(indices[i] - 1, bins_count - 1)
            idx = max(0, idx) # 確保索引不為負數
            vol_profile[idx] += volumes[i]

        # 執行數值積分 (Simpson's Rule)
        total_integral = simpson(y=vol_profile, x=price_bins)

        # 尋找 POC (最高峰)
        poc_idx = np.argmax(vol_profile)
        poc_price = price_bins[poc_idx]

        # 貪婪擴展演算法尋找 70% 價值區
        lower_idx = poc_idx
        upper_idx = poc_idx
        current_integral = vol_profile[poc_idx] * dp
        target_integral = total_integral * 0.7

        while current_integral < target_integral:
            # 南亞科邊界防護牆：碰壁就停止
            if lower_idx == 0 and upper_idx == bins_count - 1:
                break
                
            vol_down = vol_profile[lower_idx - 1] if lower_idx > 0 else -1
            vol_up = vol_profile[upper_idx + 1] if upper_idx < bins_count - 1 else -1
            
            if vol_down > vol_up:
                lower_idx -= 1
                current_integral += vol_profile[lower_idx] * dp
            else:
                upper_idx += 1
                current_integral += vol_profile[upper_idx] * dp

        value_area_low = price_bins[lower_idx]
        value_area_high = price_bins[upper_idx]

        # ==========================================
        # 🎨 視覺化呈現 (Plotly)
        # ==========================================
        st.success("✅ 數值積分運算完成！")
        
        # 顯示三大核心數據
        col1, col2, col3 = st.columns(3)
        col1.metric("總籌碼積分面積", f"{total_integral:,.0f}")
        col2.metric("價值防禦區下緣", f"{value_area_low:.2f}")
        col3.metric("價值防禦區上緣", f"{value_area_high:.2f}")

        # 繪製圖表
        fig = make_subplots(rows=1, cols=2, column_widths=[0.75, 0.25], shared_yaxes=True,
                            subplot_titles=("股價 K 線圖與價值防禦區", "籌碼分佈積分 (Volume Profile)"))

        # 左圖：K線
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                     low=df['Low'], close=df['Close'], name="K線"),
                      row=1, col=1)

        # 左圖：畫出 70% 防禦區
        fig.add_hrect(y0=value_area_low, y1=value_area_high, line_width=0, fillcolor="blue", opacity=0.15,
                      annotation_text="70% 價值防禦區 (數值積分)", annotation_position="top left",
                      row=1, col=1)

        # 左圖：畫出 POC 線
        fig.add_hline(y=poc_price, line_dash="dash", line_color="red",
                      annotation_text="POC (最強共識價)", annotation_position="bottom left",
                      row=1, col=1)

        # 右圖：籌碼分佈 (長條圖)
        colors = ['#1f77b4' if lower_idx <= i <= upper_idx else '#d3d3d3' for i in range(bins_count)]
        fig.add_trace(go.Bar(x=vol_profile, y=price_bins, orientation='h', marker_color=colors, name="籌碼量"),
                      row=1, col=2)

        # 隱藏下方不需要的滑動條，讓版面更乾淨
        fig.update_layout(height=650, showlegend=False, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 請在左側設定您想分析的股票與參數，並點擊「執行數值積分」來啟動量化引擎。")
