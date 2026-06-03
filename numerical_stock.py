import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.integrate import simpson
import requests
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator

# ==========================================
# ⚙️ 系統與 API 設定
# ==========================================
st.set_page_config(page_title="台股三引擎戰情室", layout="wide")

# 總司令的專屬 API Key (FinMind)
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoieW95b3lvIiwiZW1haWwiOiJ5b3JrOTUwODMxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.EyJQi7mvpAH1XsR7Pafa0fKqsgFkDc_Za-h60NigwJU"

@st.cache_data(ttl=3600, show_spinner=False)
def load_data(ticker, period):
    return yf.Ticker(ticker).history(period=period)

@st.cache_data(ttl=3600, show_spinner=False)
def get_institutional_data(stock_id):
    """取得真實的三大法人買賣超資料"""
    clean_id = stock_id.replace(".TW", "").replace(".TWO", "")
    
    url = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": clean_id,
        "start_date": start_date,
        "token": API_TOKEN
    }
    
    try:
        res = requests.get(url, params=params)
        data = res.json()
        if data.get('msg') == 'success' and len(data.get('data', [])) > 0:
            df = pd.DataFrame(data['data'])
            # 🎯 修正：將「股」除以 1000 轉換為「張」
            df['net_buy'] = (df['buy'] - df['sell']) / 1000
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# ==========================================
# 🎛️ 側邊欄 UI 設定
# ==========================================
st.sidebar.title("參數設定")
ticker = st.sidebar.text_input("股票代碼", "2330.TW")
period = st.sidebar.selectbox("分析天數", ["1mo", "3mo", "6mo", "1y"], index=2)
bins_count = st.sidebar.slider("積分區間切割數 (N)", min_value=20, max_value=100, value=50)
btn = st.sidebar.button("執行三引擎雷達掃描")

# ==========================================
# 📊 主畫面與核心邏輯
# ==========================================
st.title("🛡️ 台股三引擎戰情室：籌碼雷達 x 財報白話文 x 真實主力追蹤")

if btn:
    with st.spinner("正在掃描全方位數據 (含真實法人籌碼)..."):
        
        # 1. 抓取 K 線資料
        try:
            df = load_data(ticker, period)
        except Exception as e:
            st.error("⚠️ Yahoo Finance 伺服器連線擁擠，請稍後再試！")
            st.stop()
            
        if df.empty:
            st.error(f"⚠️ 找不到股票代碼【{ticker}】的資料！請確認代碼。")
            st.stop()

        df = df.dropna(subset=['Close', 'Volume'])
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        prices = df['Close'].values
        volumes = df['Volume'].values

        if len(prices) < 2:
            st.error("⚠️ 乾淨的資料筆數不足，無法進行分析！")
            st.stop()

        # ==========================================
        # 🧮 核心演算法：數值積分與 70% 尋寶
        # ==========================================
        min_p, max_p = np.min(prices), np.max(prices)
        if min_p == max_p:
            st.warning("⚠️ 價格無波動，無法計算價值防禦區。")
            st.stop()

        price_bins = np.linspace(min_p, max_p, bins_count)
        dp = price_bins[1] - price_bins[0]
        
        vol_profile = np.zeros(bins_count)
        indices = np.digitize(prices, price_bins)
        for i in range(len(prices)):
            idx = min(max(indices[i] - 1, 0), bins_count - 1)
            vol_profile[idx] += volumes[i]

        total_integral = simpson(y=vol_profile, x=price_bins)
        poc_idx = np.argmax(vol_profile)
        poc_price = price_bins[poc_idx]

        lower_idx = poc_idx
        upper_idx = poc_idx
        current_integral = vol_profile[poc_idx] * dp
        target_integral = total_integral * 0.7

        while current_integral < target_integral:
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
        # 🎨 三核戰情室 UI
        # ==========================================
        st.success(f"✅ 【{ticker}】掃描完成！請切換下方標籤頁查看完整分析。")
        tab1, tab2, tab3 = st.tabs(["⚔️ 籌碼實戰戰情室", "🏥 財報題材自動掃描", "🕵️‍♂️ 真實三大法人追蹤"])

        # ------------------------------------------
        # 🛡️ 第一頁：籌碼實戰戰情室
        # ------------------------------------------
        with tab1:
            latest_price = prices[-1]
            dist_to_low = ((latest_price - value_area_low) / latest_price) * 100
            dist_to_high = ((value_area_high - latest_price) / latest_price) * 100
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📌 最新收盤價", f"{latest_price:.2f}")
            col2.metric("🛡️ 底部支撐 (防守線)", f"{value_area_low:.2f}", f"距離 {dist_to_low:.1f}%", delta_color="off")
            col3.metric("🎯 上方壓力 (突破線)", f"{value_area_high:.2f}", f"距離 {dist_to_high:.1f}%", delta_color="off")

            fig = make_subplots(rows=1, cols=2, column_widths=[0.75, 0.25], shared_yaxes=True,
                                subplot_titles=("股價 K 線圖與主力成本區", "籌碼分佈 (Volume Profile)"))

            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
                                         increasing_line_color='red', decreasing_line_color='green', name="K線"), row=1, col=1)
            fig.add_hrect(y0=value_area_low, y1=value_area_high, line_width=0, fillcolor="blue", opacity=0.15, row=1, col=1)
            fig.add_hline(y=poc_price, line_dash="dash", line_color="red", row=1, col=1)

            colors = ['#1f77b4' if lower_idx <= i <= upper_idx else '#d3d3d3' for i in range(bins_count)]
            fig.add_trace(go.Bar(x=vol_profile, y=price_bins, orientation='h', marker_color=colors, name="籌碼量"), row=1, col=2)

            fig.update_layout(height=500, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
            
            if latest_price > value_area_high:
                st.success(f"**📈 狀態：突破上方壓力。** 建議等待量縮回測 **{value_area_high:.2f}** 附近做多；跌破 **{value_area_low:.2f}** 嚴格停損。")
            elif latest_price < value_area_low:
                st.error(f"**📉 狀態：跌破底部支撐。** 上方套牢賣壓沉重，**切勿摸底**。有持股者建議反彈至 **{value_area_low:.2f}** 減碼逃命。")
            else:
                st.warning(f"**⚖️ 狀態：核心區間震盪。** 靠近支撐 **{value_area_low:.2f}** 低買，靠近壓力 **{value_area_high:.2f}** 高賣，跌破支撐停損。")

        # ------------------------------------------
        # 🏥 第二頁：公司基本面自動掃描 (自動翻譯版)
        # ------------------------------------------
        with tab2:
            st.markdown("### 🏷️ 公司背景與板塊")
            with st.spinner("正在自動搜尋並翻譯公司背景資料..."):
                try:
                    info = yf.Ticker(ticker).info
                    sector_en = info.get('sector', '未知板塊')
                    industry_en = info.get('industry', '未知產業')
                    summary_en = info.get('longBusinessSummary', '目前無法自動取得這家公司的簡介。')
                    
                    # 🎯 自動將英文翻譯成繁體中文
                    translator = GoogleTranslator(source='auto', target='zh-TW')
                    sector_zh = translator.translate(sector_en) if sector_en != '未知板塊' else sector_en
                    industry_zh = translator.translate(industry_en) if industry_en != '未知產業' else industry_en
                    
                    # 避免簡介太長導致翻譯逾時，加上防錯機制
                    try:
                        summary_zh = translator.translate(summary_en) if summary_en != '目前無法自動取得這家公司的簡介。' else summary_en
                    except:
                        summary_zh = "翻譯伺服器忙碌中，原文：" + summary_en

                    st.info(f"**所屬板塊：** {sector_zh} | **所屬產業：** {industry_zh}")
                    with st.expander("📖 點擊查看公司詳細業務簡介 (中文翻譯)"):
                        st.write(summary_zh)
                    
                    st.markdown("### 🕵️‍♂️ AI 財報白話文掃描")
                    
                    eps = info.get('trailingEps', 0)
                    if eps and eps > 0:
                        st.success(f"💰 **這家公司有實質獲利！** (近四季 EPS: {eps:.2f} 元)。不是只靠做夢炒作，是有真金白銀進帳的，買起來相對安心。")
                    elif eps and eps <= 0:
                        st.error(f"🩸 **注意！這家公司目前還在賠錢。** (近四季 EPS: {eps:.2f} 元)。操作上要極度短線，一旦跌破籌碼支撐必須秒逃！")
                    else:
                        st.warning("🔍 暫時查無獲利資料。")

                    rev_growth = info.get('revenueGrowth', 0)
                    if rev_growth and rev_growth > 0.1:
                        st.success(f"🚀 **公司越做越大，業績大爆發！** (營收成長率: {rev_growth*100:.1f}%)。代表公司處於擴張期，有機會成為飆股！")
                    elif rev_growth and rev_growth < 0:
                        st.warning(f"🐢 **公司業績正在衰退...** (營收成長率: {rev_growth*100:.1f}%)。本業表現不佳，股價若上漲高機率是主力硬拉。")
                    
                    yield_pct = info.get('dividendYield', 0)
                    if yield_pct and yield_pct > 0.04:
                        st.info(f"🛡️ **自帶防護罩！** (現金殖利率高達 {yield_pct*100:.1f}%)。配息大方，套牢了還可以當作存股領股利。")
                    elif yield_pct and yield_pct < 0.02:
                        st.markdown(f"⚔️ **純攻擊型股票。** (殖利率僅 {yield_pct*100:.1f}% 或無配息)。買它就是為了賺價差，不要有存股的幻想。")

                except Exception as e:
                    st.error("⚠️ 無法自動取得財報或背景資料，請確認該股票是否存在。")

        # ------------------------------------------
        # 🕵️‍♂️ 第三頁：真實三大法人追蹤 (API 連線修復版)
        # ------------------------------------------
        with tab3:
            st.markdown("### 🏦 真實三大法人買賣超 (FinMind 即時數據)")
            
            with st.spinner("正在連線 FinMind 抓取並解析真實籌碼..."):
                inst_df = get_institutional_data(ticker)
                
                if not inst_df.empty:
                    # 🎯 修正：FinMind 的外資英文代號是 Foreign_Investor，投信是 Investment_Trust
                    foreign = inst_df[inst_df['name'] == 'Foreign_Investor']
                    trust = inst_df[inst_df['name'] == 'Investment_Trust']
                    
                    # 計算近 5 日與近 10 日累積 (單位已經轉換成張)
                    f_5d = foreign.tail(5)['net_buy'].sum() if not foreign.empty else 0
                    f_10d = foreign.tail(10)['net_buy'].sum() if not foreign.empty else 0
                    t_5d = trust.tail(5)['net_buy'].sum() if not trust.empty else 0
                    t_10d = trust.tail(10)['net_buy'].sum() if not trust.empty else 0
                    
                    col_a, col_b, col_c, col_d = st.columns(4)
                    
                    # 動態顯示顏色與箭頭
                    def get_status(val):
                        return ("偏多", "normal") if val > 0 else ("偏空", "inverse") if val < 0 else ("無動靜", "off")

                    f5_stat, f5_color = get_status(f_5d)
                    col_a.metric("外資 5日累積", f"{f_5d:,.0f} 張", f5_stat, delta_color=f5_color)
                    
                    t5_stat, t5_color = get_status(t_5d)
                    col_b.metric("投信 5日累積", f"{t_5d:,.0f} 張", t5_stat, delta_color=t5_color)
                    
                    f10_stat, f10_color = get_status(f_10d)
                    col_c.metric("外資 10日累積", f"{f_10d:,.0f} 張", f10_stat, delta_color=f10_color)
                    
                    t10_stat, t10_color = get_status(t_10d)
                    col_d.metric("投信 10日累積", f"{t_10d:,.0f} 張", t10_stat, delta_color=t10_color)

                    st.divider()
                    st.markdown("### 📊 近期每日詳細進出 (單位：張)")
                    
                    # 將資料依照日期整理成表格
                    pivot_df = inst_df.pivot_table(index='date', columns='name', values='net_buy', aggfunc='sum').fillna(0)
                    
                    # 🎯 修正：將 FinMind 的英文標題翻譯成中文
                    rename_dict = {
                        'Foreign_Investor': '外資',
                        'Investment_Trust': '投信',
                        'Dealer_self': '自營商(自行買賣)',
                        'Dealer_Hedging': '自營商(避險)',
                        'Foreign_Dealer_Self': '外資自營商'
                    }
                    pivot_df = pivot_df.rename(columns=rename_dict)
                    
                    # 整理小數點並排序顯示最近 10 天
                    pivot_df = pivot_df.round(0).sort_index(ascending=False).head(10) 
                    st.dataframe(pivot_df, use_container_width=True)

                else:
                    st.error("⚠️ 無法取得籌碼資料，可能是該股票無法人進出，或是 API Token 額度已滿。")

else:
    st.info("👈 在左側輸入股票代碼與分析天數，啟動台股三引擎戰情室。")
