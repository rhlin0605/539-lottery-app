import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from collections import Counter
from itertools import combinations
import random
from datetime import datetime

# 頁面設定
st.set_page_config(page_title="今彩539預測系統", layout="wide")
st.title("🎯 今彩539預測系統（多資料源+Debug Mode+日期統一）")

local_csv = "539_data.csv"

# 日期格式標準化
def standardize_date(date_str):
    try:
        date_str = date_str.strip().replace('-', '/')
        date_obj = datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        try:
            date_obj = datetime.strptime(date_str, "%Y/%-m/%-d")
        except ValueError:
            try:
                date_obj = datetime.strptime(date_str, "%Y/%m/%d")
            except Exception:
                return date_str.strip()  # 若失敗，保留原樣
    return date_obj.strftime("%Y/%m/%d")

# 讀取CSV
try:
    local_df = pd.read_csv(local_csv, encoding='utf-8')
except FileNotFoundError:
    local_df = pd.DataFrame(columns=['Date', 'NO.1', 'NO.2', 'NO.3', 'NO.4', 'NO.5'])

# Sidebar 設定
debug_mode = st.sidebar.checkbox("🔧 Debug Mode", value=False)
num_fetch = st.sidebar.number_input("抓取最新N期（網站資料）", 1, 100, 50)

# 抓資料
def fetch_from_primary_source(num_fetch=50, debug=False):
    url = 'https://www.pilio.idv.tw/lto539/list.asp'
    latest_rows = []
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            has_header = False
            if rows and len(rows[0].find_all('td')) >= 2:
                first_row_text = [c.get_text(strip=True) for c in rows[0].find_all('td')]
                if any('日期' in text or '今彩' in text for text in first_row_text):
                    has_header = True
            start_idx = 1 if has_header else 0
            for row in rows[start_idx:start_idx+num_fetch]:
                cols = row.find_all('td')
                if len(cols) >= 2 and '/' in cols[0].get_text():
                    try:
                        date = cols[0].get_text(strip=True).split('(')[0]
                        date = standardize_date(date)
                        numbers_text = cols[1].get_text(strip=True).replace('\xa0', '')
                        numbers = [int(x) for x in numbers_text.split(',')]
                        latest_rows.append([date] + numbers)
                    except Exception as e:
                        if debug:
                            st.warning(f"⚠️ Pilio解析錯誤: {e}")
        return latest_rows
    except Exception as e:
        st.warning(f"⚠️ 主資料源抓取失敗：{e}")
        return []

def fetch_from_secondary_source(debug=False):
    url = 'https://lotto.ctbcbank.com/result_all.htm#07'
    latest_rows = []
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                try:
                    date_text = cols[0].get_text(strip=True)
                    if '/' in date_text:
                        date = date_text.split(' ')[0]
                        date = standardize_date(date)
                        numbers_text = cols[4].get_text(strip=True).replace('\xa0', '')
                        numbers = [int(x) for x in numbers_text.split()]
                        latest_rows.append([date] + numbers)
                except Exception as e:
                    if debug:
                        st.warning(f"⚠️ CTBC解析錯誤: {e}")
        return latest_rows
    except Exception as e:
        st.warning(f"⚠️ 備用資料源抓取失敗：{e}")
        return []

# Debug Mode按鈕
if st.sidebar.button("🛠️ 立即抓取資料（Debug）"):
    st.subheader("🔎 Debug Mode：立即抓取資料")
    pilio_data = fetch_from_primary_source(num_fetch, debug=True)
    ctbcbank_data = fetch_from_secondary_source(debug=True)
    st.write("✅ Primary Source（Pilio）資料（前5筆）:", pilio_data[:5])
    st.write("✅ Secondary Source（CTBC）資料（前5筆）:", ctbcbank_data[:5])

# 自動抓資料
latest_rows = fetch_from_primary_source(num_fetch, debug=debug_mode)
if not latest_rows:
    if debug_mode:
        st.info("🔄 Primary Source 抓取失敗或無資料，嘗試使用備用資料源...")
    latest_rows = fetch_from_secondary_source(debug=debug_mode)

if latest_rows:
    latest_df = pd.DataFrame(latest_rows, columns=['Date', 'NO.1', 'NO.2', 'NO.3', 'NO.4', 'NO.5'])
    latest_df['Date'] = latest_df['Date'].apply(standardize_date)
    local_df['Date'] = local_df['Date'].apply(standardize_date)

    existing_dates = set(local_df['Date'])
    new_rows = latest_df[~latest_df['Date'].isin(existing_dates)]

    if debug_mode:
        st.write("📅 資料庫已有日期：", sorted(existing_dates))
        st.write("📅 Pilio抓到最新日期：", latest_df.iloc[0]['Date'])
        st.write("✅ 新資料筆數：", len(new_rows))

    if not new_rows.empty:
        local_df = pd.concat([new_rows, local_df], ignore_index=True)
        local_df.drop_duplicates(subset=['Date'], inplace=True)
        local_df.sort_values(by='Date', ascending=False, inplace=True)
        local_df.to_csv(local_csv, index=False, encoding='utf-8')
        st.success(f"✅ 資料庫已補上 {len(new_rows)} 筆新資料，共 {len(local_df)} 期")
    else:
        st.info("📅 資料庫已是最新，無需更新。")
else:
    st.error("❌ 無法從任一資料源取得資料，請稍後再試。")

# 顯示最新資料
st.subheader("📅 最新資料（前 5 筆）")
st.dataframe(local_df.head(5))

# （這裡繼續保留統計分析、權重設定、預測按鈕等區塊）
# 例如：
st.write("⚡️ 接下來請接上統計分析和預測的邏輯")
