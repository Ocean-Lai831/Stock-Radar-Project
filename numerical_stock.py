import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.integrate import simpson

st.set_page_config(page_title="數值積分 x 籌碼", layout="wide")
st.title("🛡️ 數值分析期末專案")
# 🎯 新增防護罩：Streamlit 專屬快取機制 (保留資料 1 小時，避免被 Yahoo 封鎖)
@st.cache_data(ttl=3600, show_spinner=False)
def load_data(stock_ticker, time_period):
    return yf.Ticker(stock_ticker).history(period=time_period)
with st.sidebar:
    st.header("參數設定")
    ticker = st.text_input("股票代碼", value="2330.TW")
    period = st.selectbox("分析天數", ["3mo", "6mo", "1y"], index=1)
    bins_count = st.slider("積分區間切割數 (N)", min_value=20, max_value=100, value=50, step=10)
    btn = st.button("執行數值積分")

if btn:
    with st.spinner("正在執行辛普森積分與價值區間運算..."):
        # 1. 抓取資料
        if btn:
    with st.spinner("正在執行辛普森積分與價值區間運算..."):
        
        # 1. 抓取資料 (改用快取函數)
        try:
            df = load_data(ticker, period)
        except Exception as e:
            st.error("⚠️ Yahoo Finance 伺服器目前連線擁擠，請稍後再試！")
            st.stop()
            
        # 🎯 檢查有沒有抓到資料！
        if df.empty:
            st.error(f"⚠️ 找不到股票代碼【{ticker}】的資料！請確認代碼是否輸入正確（台股記得加 .TW）。")
            st.stop()
        
        # 1. 抓取資料 (改用快取函數)
        try:
            df = load_data(ticker, period)
        except Exception as e:
            st.error("⚠️ Yahoo Finance 伺服器目前連線擁擠，請稍後再試！")
            st.stop()
            
        # 🎯 檢查有沒有抓到資料！
        if df.empty:
            st.error(f"⚠️ 找不到股票代碼【{ticker}】的資料！請確認代碼是否輸入正確（台股記得加 .TW）。")
            st.stop()
            
        # ... 下面維持原本的 df.index 時區處理邏輯 ...

        # 🎯 新增防護罩：檢查有沒有抓到資料！
        if df.empty:
            st.error(f"⚠️ 找不到股票代碼【{ticker}】的資料！請確認代碼是否輸入正確（台股記得加 .TW 或 .TWO）。")
            st.stop()  # 停止往下執行，保護後面的程式碼

        # 下面是你剛剛改好的時區處理
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        prices = df['Close'].values
        volumes = df['Volume'].values

        # ==========================================
        # 🎯 Ch4: 準備數值積分的離散函數 V(p)
        # ==========================================
        min_p, max_p = np.min(prices), np.max(prices)

        # 建立等距的價格節點 (網格)
        price_bins = np.linspace(min_p, max_p, bins_count)
        dp = price_bins[1] - price_bins[0]  # 步長

        # 將每一天的成交量，分配到對應的價格區間內
        vol_profile = np.zeros(bins_count)
        indices = np.digitize(prices, price_bins)
        for i in range(len(prices)):
            idx = min(indices[i] - 1, bins_count - 1)
            idx = max(idx, 0)
            vol_profile[idx] += volumes[i]

        # ==========================================
        # 🎯 Ch4: 執行數值積分 (Simpson's Rule)
        # ==========================================
        # 1. 計算總積分面積 (總成交量)
        total_integral = simpson(y=vol_profile, x=price_bins)

        # 2. 尋找 POC (Point of Control) - 也就是函數的極大值
        poc_idx = np.argmax(vol_profile)
        poc_price = price_bins[poc_idx]

        # 3. 尋找 70% 價值防禦區間 (Value Area)
        # 從 POC 開始，不斷向上下擴展，並計算累積積分面積
        target_integral = total_integral * 0.70
        current_integral = vol_profile[poc_idx] * dp
        lower_idx = poc_idx
        upper_idx = poc_idx

        while current_integral < target_integral:
            # 檢查是否已經碰到雙邊邊界 (整座山都吃完了)
            if lower_idx == 0 and upper_idx == bins_count - 1:
                break

            # 取得上下相鄰網格的成交量
            # 💡 關鍵修復：如果已經頂到天花板或地板，就把那一側的成交量設為 -1，逼程式往另一側走
            vol_down = vol_profile[lower_idx - 1] if lower_idx > 0 else -1
            vol_up = vol_profile[upper_idx + 1] if upper_idx < bins_count - 1 else -1

            # 比較哪邊大就往哪邊吃
            if vol_down > vol_up:
                lower_idx -= 1
                current_integral += vol_profile[lower_idx] * dp
            else:
                upper_idx += 1
                current_integral += vol_profile[upper_idx] * dp

        value_area_low = price_bins[lower_idx]
        value_area_high = price_bins[upper_idx]

        # 判斷目前股價位置
        latest_price = prices[-1]
        if latest_price > value_area_high:
            status = "🚀 突破防禦區：上方無沉重賣壓，適合做多"
            status_color = "success"
        elif latest_price < value_area_low:
            status = "⚠️ 跌破防禦區：上方全是套牢盤，壓力極大"
            status_color = "error"
        else:
            status = "🛡️ 處於防禦區內：籌碼換手中，具有強力支撐"
            status_color = "info"

        # ==========================================
        # 繪製儀表板
        # ==========================================
        st.subheader("📊 積分運算結果摘要")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新收盤價", f"{latest_price:.1f}")
        c2.metric("POC (最大成交量節點)", f"{poc_price:.1f}")
        c3.metric("價值防禦區 (底)", f"{value_area_low:.1f}")
        c4.metric("價值防禦區 (頂)", f"{value_area_high:.1f}")

        if status_color == "success":
            st.success(f"**戰情判定：** {status}")
        elif status_color == "error":
            st.error(f"**戰情判定：** {status}")
        else:
            st.info(f"**戰情判定：** {status}")

        st.markdown("---")

        # 建立圖表：左邊 K 線，右邊 Volume Profile
        fig = go.Figure()

        # 繪製真實 K 線
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name='真實K線',
            increasing_line_color='#E8231C', decreasing_line_color='#00A550'
        ))

        # 繪製 70% 價值區塊 (透明背景)
        fig.add_hrect(
            y0=value_area_low, y1=value_area_high,
            line_width=0, fillcolor="blue", opacity=0.15,
            annotation_text="70% 積分防禦區", annotation_position="top left"
        )

        # 繪製 POC 基準線
        fig.add_hline(
            y=poc_price, line_dash="dash", line_color="purple",
            annotation_text="POC (控制點)", annotation_position="bottom right"
        )

        fig.update_layout(
            height=600,
            title_text=f"股價趨勢與防禦區分析 ({ticker})",
            template="plotly_white",
            yaxis_title="價格",
            xaxis_title="時間",
            xaxis_rangeslider_visible=False
        )

        # 右側顯示獨立的直方圖 (代表積分函數形狀)
        st.plotly_chart(fig, use_container_width=True)

        st.write("### 🧮 函數 $V(p)$ 分佈圖 (數值積分對象)")
        fig_vp = go.Figure(go.Bar(
            x=price_bins, y=vol_profile, marker_color='darkblue', name='成交量'
        ))
        # 標示 70% 積分區間
        fig_vp.add_vrect(
            x0=value_area_low, x1=value_area_high,
            fillcolor="blue", opacity=0.2, line_width=0,
            annotation_text="$\int V(p) dp = 70\% I_{total}$"
        )
        fig_vp.update_layout(height=300, xaxis_title="價格 $p$", yaxis_title="成交量 $V(p)$", template="plotly_white")
        st.plotly_chart(fig_vp, use_container_width=True)

        with st.expander("查看數值推導明細"):
            st.write(f"- 價格切分數 (網格數量 $N$): {bins_count}")
            st.write(f"- 價格步長 ($\Delta p$): {dp:.2f}")
            st.write(f"- 辛普森法則總積分面積 ($I_{{total}}$): {total_integral:,.0f}")
            st.write(f"- 70% 目標積分面積: {target_integral:,.0f}")
