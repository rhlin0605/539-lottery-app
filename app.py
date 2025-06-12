import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import Counter
from itertools import combinations
import random
import os

st.set_page_config(page_title="今彩539預測系統", layout="wide")
st.title("🎯 今彩539預測系統（自動更新+統計+預測）")

CSV_FILE = "539_data.csv"
BACKUP_FOLDER = "backups"
os.makedirs(BACKUP_FOLDER, exist_ok=True)

def standardize_date(date_str):
    try:
        dt = datetime.strptime(date_str.strip(), "%Y/%m/%d")
    except ValueError:
        dt = datetime.strptime(date_str.strip(), "%Y/%m/%-d")
    return dt.strftime("%Y/%m/%d")

def fetch_pilio_data(n=20):
    url = 'https://www.pilio.idv.tw/lto539/list.asp'
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        tables = soup.find_all('table')
        rows = []
        for table in tables:
            trs = table.find_all('tr')
            for tr in trs:
                tds = tr.find_all('td')
                if len(tds) >= 2 and '/' in tds[0].get_text():
                    try:
                        date = standardize_date(tds[0].get_text().split('(')[0].strip())
                        numbers = [int(x) for x in tds[1].get_text().replace('\xa0', '').split(',')]
                        if len(numbers) == 5:
                            rows.append([date] + numbers)
                    except:
                        continue
        return rows[:n]
    except Exception as e:
        st.warning(f"抓取 Pilio 失敗：{e}")
        return []

def update_data():
    try:
        local_df = pd.read_csv(CSV_FILE, encoding='utf-8')
    except:
        local_df = pd.DataFrame(columns=['Date', 'NO.1', 'NO.2', 'NO.3', 'NO.4', 'NO.5'])

    latest_local_date = local_df['Date'].iloc[0] if not local_df.empty else "2000/01/01"
    fetched_data = fetch_pilio_data(30)

    new_rows = []
    for row in fetched_data:
        if row[0] > latest_local_date:
            new_rows.append(row)

    if new_rows:
        df_new = pd.DataFrame(new_rows, columns=local_df.columns)
        local_df = pd.concat([df_new, local_df], ignore_index=True)
        local_df.drop_duplicates(subset='Date', inplace=True)
        local_df.sort_values(by='Date', ascending=False, inplace=True)
        local_df.to_csv(CSV_FILE, index=False, encoding='utf-8')
        backup_name = f"{BACKUP_FOLDER}/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        local_df.to_csv(backup_name, index=False, encoding='utf-8')
        st.success(f"✅ 已更新 {len(new_rows)} 筆資料，並備份至 {backup_name}")
    else:
        st.info("📅 資料已是最新，不需更新。")
    return local_df

local_df = update_data()
st.subheader("📅 最新資料（前 5 筆）")
st.dataframe(local_df.head(5))

# 統計分析與預測
st.subheader("📊 統計分析")
num_periods = st.selectbox("選擇統計期數", [50, 100, 200], index=1)
df_sorted = local_df.head(num_periods)

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
    for h in set(heads):
        if heads.count(h) >= 2:
            head_counter[h] += 1
    for t in set(tails):
        if tails.count(t) >= 2:
            tail_counter[t] += 1

    for num in miss_counter:
        if num in curr_nums:
            miss_counter[num] = 0
        else:
            miss_counter[num] += 1

sum_sorted = sorted(sum_counter.items(), key=lambda x: x[1], reverse=True)[:10]
top_streaks = sorted(streak_counter.items(), key=lambda x: x[1], reverse=True)
hot_numbers = sorted(num_counter.items(), key=lambda x: x[1], reverse=True)
top_pairs = [p for p in pair_counter.items() if p[1] >= 2]
head_sorted = sorted(head_counter.items(), key=lambda x: x[1], reverse=True)
tail_sorted = sorted(tail_counter.items(), key=lambda x: x[1], reverse=True)
sorted_miss = sorted(miss_counter.items(), key=lambda x: x[1], reverse=True)

st.write("### 和值分佈（前10）")
st.dataframe(pd.DataFrame(sum_sorted, columns=["和值", "次數"]))

st.write("### 熱門號碼")
st.dataframe(pd.DataFrame(hot_numbers[:10], columns=["號碼", "次數"]))

st.write("### 雙號同開（次數 ≥ 2）")
pair_df = pd.DataFrame(top_pairs, columns=["組合", "次數"])
pair_df["組合"] = pair_df["組合"].apply(lambda x: f"{x[0]} & {x[1]}")
st.dataframe(pair_df)

st.write("### 同首數（至少2顆）")
st.dataframe(pd.DataFrame(head_sorted, columns=["首數", "次數"]))

st.write("### 同尾數（至少2顆）")
st.dataframe(pd.DataFrame(tail_sorted, columns=["尾數", "次數"]))

st.write("### 連續未開期數")
st.dataframe(pd.DataFrame(sorted_miss[:10], columns=["號碼", "未開期數"]))

# 預測號碼
st.subheader("🔮 自動預測組合")
pool = []
for k, _ in sum_sorted:
    for nums in sum_to_draws.get(k, []):
        pool.extend(nums)

for n, _ in top_streaks[:10]:
    pool.extend([n] * 2)
for n, _ in hot_numbers[:10]:
    pool.extend([n] * 2)
for p, _ in top_pairs:
    pool.extend(p)
for h, _ in head_sorted:
    pool.extend([n for n in range(h*10, min(h*10+10, 40))])
for t, _ in tail_sorted:
    pool.extend([n for n in range(t, 40, 10)])
for n, c in sorted_miss[:10]:
    pool.extend([n] * (c // 5 + 1))

pool = list(set([n for n in pool if 1 <= n <= 39]))
if len(pool) >= 5:
    result = sorted(random.sample(pool, 5))
    st.write(f"🎯 建議號碼：{result}（和值：{sum(result)}）")
else:
    st.warning("資料不足，無法預測號碼。")
