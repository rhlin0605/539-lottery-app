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
st.title("🎯 今彩539預測系統（自動更新+統計+預測）")

# 本地 CSV 檔案
local_csv = "539_data.csv"
try:
    local_df = pd.read_csv(local_csv, encoding='utf-8')
except FileNotFoundError:
    local_df = pd.DataFrame(columns=['Date', 'NO.1', 'NO.2', 'NO.3', 'NO.4', 'NO.5'])

# 取得最新資料
url = 'https://www.pilio.idv.tw/lto539/list.asp'
try:
    resp = requests.get(url, timeout=10)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')

    tables = soup.find_all('table')
    latest_rows = []
    num_fetch = st.sidebar.number_input("抓取最新N期（網站資料）", 1, 100, 10)

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
                    numbers_text = cols[1].get_text(strip=True).replace('\xa0', '')
                    numbers = [int(x) for x in numbers_text.split(',')]
                    latest_rows.append([date] + numbers)
                except:
                    pass

    if not latest_rows:
        st.error("⚠️ 找不到正確的開獎資料列，請稍後再試。")
        st.stop()

    new_data_count = 0
    for row in latest_rows:
        date = row[0]
        if not local_df.empty and date in local_df['Date'].astype(str).values:
            continue
        new_row = pd.DataFrame([row], columns=['Date', 'NO.1', 'NO.2', 'NO.3', 'NO.4', 'NO.5'])
        local_df = pd.concat([new_row, local_df], ignore_index=True)
        new_data_count += 1

    if new_data_count > 0:
        local_df.drop_duplicates(subset=['Date'], inplace=True)
        local_df.sort_values(by='Date', ascending=False, inplace=True)
        local_df.to_csv(local_csv, index=False, encoding='utf-8')
        backup_file = f"539_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        local_df.to_csv(backup_file, index=False, encoding='utf-8')
        st.success(f"✅ 已新增 {new_data_count} 筆最新資料，並備份：{backup_file}")
    else:
        st.info("📅 資料庫已是最新，無需更新。")

except Exception as e:
    st.error(f"⚠️ 抓取資料失敗：{e}")
    st.stop()

# 顯示最新資料
st.subheader("📅 最新資料（前 5 筆）")
st.dataframe(local_df.head(5))

# 統計分析
num_periods = st.selectbox("選擇統計期數（分析區間）", [15, 50, 100, 200], index=1)
df_sorted = local_df.head(num_periods)

# Sidebar 權重設定
st.sidebar.header("⚙️ 權重設定")
weight_sum = st.sidebar.slider("和值分佈", 1, 10, 3)
weight_streak = st.sidebar.slider("連莊號碼", 1, 10, 3)
weight_hot = st.sidebar.slider("熱門號碼", 1, 10, 2)
weight_pair = st.sidebar.slider("雙號同開", 1, 10, 1)
weight_headtail = st.sidebar.slider("同首數/尾數", 1, 10, 1)
weight_miss = st.sidebar.slider("連續未開期數", 1, 10, 1)
weight_multiplier = st.sidebar.slider("🎚️ 全域權重倍數", 0.5, 2.0, 1.0, step=0.1)

# 統計計算
sum_counter = Counter()
sum_to_draws = {}
streak_counter = Counter()
num_counter = Counter()
pair_counter = Counter()
head_counter = Counter()
tail_counter = Counter()
miss_counter = {num: 0 for num in range(1, 40)}
prev_nums = set()

for _, row in df_sorted.iterrows():
    nums = [row[f'NO.{i}'] for i in range(1, 6)]
    total_sum = sum(nums)
    sum_counter[total_sum] += 1
    sum_to_draws.setdefault(total_sum, []).append(nums)

    curr_nums = set(nums)
    for num in prev_nums & curr_nums:
        streak_counter[num] += 1
    prev_nums = curr_nums

    for num in nums:
        num_counter[num] += 1

    for pair in combinations(sorted(nums), 2):
        pair_counter[pair] += 1

    heads = [num // 10 for num in nums]
    tails = [num % 10 for num in nums]
    for head in set(heads):
        if heads.count(head) >= 2:
            head_counter[head] += 1
    for tail in set(tails):
        if tails.count(tail) >= 2:
            tail_counter[tail] += 1

    for num in miss_counter.keys():
        if num in curr_nums:
            miss_counter[num] = 0
        else:
            miss_counter[num] += 1

sum_sorted = sorted(sum_counter.items(), key=lambda x: x[1], reverse=True)[:25]
top_streaks = sorted(streak_counter.items(), key=lambda x: x[1], reverse=True)[:25]
hot_numbers = sorted(num_counter.items(), key=lambda x: x[1], reverse=True)[:25]
top_pairs = pair_counter.most_common(25)
head_sorted = sorted(head_counter.items(), key=lambda x: x[1], reverse=True)[:25]
tail_sorted = sorted(tail_counter.items(), key=lambda x: x[1], reverse=True)[:25]
sorted_miss = sorted(miss_counter.items(), key=lambda x: x[1], reverse=True)[:25]

# 顯示統計
st.subheader("📊 統計分析（前25筆）")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("### 🧮 和值分佈")
    st.dataframe(pd.DataFrame(sum_sorted, columns=["和值", "次數"]), use_container_width=True, height=300)
    st.markdown("### 🔄 連莊號碼排行")
    st.dataframe(pd.DataFrame(top_streaks, columns=["號碼", "連莊次數"]), use_container_width=True, height=300)
with col2:
    st.markdown("### 🔥 熱門號碼排行")
    st.dataframe(pd.DataFrame(hot_numbers, columns=["號碼", "次數"]), use_container_width=True, height=300)
    st.markdown("### 🔗 雙號同開排行")
    pair_df = pd.DataFrame(top_pairs, columns=["雙號組合", "次數"])
    pair_df["雙號組合"] = pair_df["雙號組合"].apply(lambda x: f"{x[0]} & {x[1]}")
    st.dataframe(pair_df, use_container_width=True, height=300)
with col3:
    st.markdown("### 🔢 同首數排行（至少2顆）")
    st.dataframe(pd.DataFrame(head_sorted, columns=["首數", "次數"]), use_container_width=True, height=300)
    st.markdown("### 🔢 同尾數排行（至少2顆）")
    st.dataframe(pd.DataFrame(tail_sorted, columns=["尾數", "次數"]), use_container_width=True, height=300)
    st.markdown("### 📉 連續未開期數統計")
    st.dataframe(pd.DataFrame(sorted_miss, columns=["號碼", "連續未開期數"]), use_container_width=True, height=300)

# 預測選號（避免重複、範圍1~39）
st.subheader("🔮 自動預測組合（進階權重）")
weighted_numbers = []
for sum_value, _ in sum_sorted:
    for nums in sum_to_draws.get(sum_value, []):
        weighted_numbers.extend(nums * int(weight_sum * weight_multiplier))
for num, _ in top_streaks:
    weighted_numbers.extend([num] * int(weight_streak * weight_multiplier))
for num, _ in hot_numbers:
    weighted_numbers.extend([num] * int(weight_hot * weight_multiplier))
for pair, _ in top_pairs:
    weighted_numbers.extend([pair[0]] * int(weight_pair * weight_multiplier))
    weighted_numbers.extend([pair[1]] * int(weight_pair * weight_multiplier))
for head, _ in head_sorted:
    weighted_numbers.extend([num for num in range(head*10, min(head*10+10, 40))] * int(weight_headtail * weight_multiplier))
for tail, _ in tail_sorted:
    weighted_numbers.extend([num for num in range(tail, 40, 10)] * int(weight_headtail * weight_multiplier))
for num, miss_count in sorted_miss:
    points = min(miss_count, 5) * int(weight_miss * weight_multiplier)
    weighted_numbers.extend([num] * points)

# 號碼去重並限制範圍
weighted_numbers = [num for num in set(weighted_numbers) if 1 <= num <= 39]

# 補足5碼
remaining_numbers = list(set(range(1, 40)) - set(weighted_numbers))
while len(weighted_numbers) < 5 and remaining_numbers:
    weighted_numbers.append(random.choice(remaining_numbers))

# 從 weighted_numbers 中隨機抽樣
prediction = sorted(random.sample(weighted_numbers, 5))
prediction_sum = sum(prediction)
st.write(f"🎉 建議選號：{prediction}（和值：{prediction_sum}）")

# 下載 CSV
csv_download = local_df.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="📥 下載完整CSV",
    data=csv_download,
    file_name=f"539_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime='text/csv'
)
