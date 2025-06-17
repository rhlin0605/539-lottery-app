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

# 日期標準化
def standardize_date(date_str):
    try:
        return datetime.strptime(date_str.strip(), "%Y/%m/%d").strftime("%Y/%m/%d")
    except:
        try:
            return datetime.strptime(date_str.strip(), "%Y/%m/%d(%a)").strftime("%Y/%m/%d")
        except:
            return date_str.strip()

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
                    date = standardize_date(cols[0].get_text(strip=True).split('(')[0])
                    numbers_text = cols[1].get_text(strip=True).replace('\xa0', '')
                    numbers = [int(x) for x in numbers_text.split(',')]
                    latest_rows.append([date] + numbers)
                except:
                    pass

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
num_periods = st.selectbox("選擇統計期數（分析區間）", [15, 50, 75,100,150, 200], index=1)
df_sorted = local_df.head(num_periods)

# Sidebar 權重設定
st.sidebar.header("⚙️ 權重設定")
weight_sum = st.sidebar.slider("和值分佈", 1, 10, 2)
weight_streak = st.sidebar.slider("連莊號碼", 1, 10, 2)
weight_hot = st.sidebar.slider("熱門號碼", 1, 10, 6)
weight_pair = st.sidebar.slider("雙號同開", 1, 10, 2)
weight_head = st.sidebar.slider("同首數（至少兩顆）", 1, 10, 6)
weight_tail = st.sidebar.slider("同尾數（至少兩顆）", 1, 10, 5)
weight_miss = st.sidebar.slider("連續未開期數", 1, 10, 4)
weight_multiplier = st.sidebar.slider("🎚️ 全域權重倍數", 0.5, 2.0, 1.0, step=0.1)

# 統計資料處理
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
# 🔍 新增篩選條件：僅保留 8~12 期未開的號碼
filtered_miss = [(num, count) for num, count in sorted_miss if 8 <= count <= 12]

# 🔮 進階預測（20組模擬 + 頻率加分系統）
st.subheader("🔮 自動預測組合（20組模擬）")

if st.button("🎯 立即產生預測號碼"):

    def generate_prediction():
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
            weighted_numbers.extend([num for num in range(head*10, min(head*10+10, 40))] * int(weight_head * weight_multiplier))
        for tail, _ in tail_sorted:
            weighted_numbers.extend([num for num in range(tail, 40, 10)] * int(weight_tail * weight_multiplier))
        for num, miss_count in sorted_miss:
            points = min(miss_count, 5) * int(weight_miss * weight_multiplier)
            weighted_numbers.extend([num] * points)

        weighted_numbers = [num for num in set(weighted_numbers) if 1 <= num <= 39]
        remaining_numbers = list(set(range(1, 40)) - set(weighted_numbers))
        while len(weighted_numbers) < 5 and remaining_numbers:
            weighted_numbers.append(random.choice(list(remaining_numbers)))

        prediction = sorted(random.sample(weighted_numbers, 5))
        return prediction

    # 模擬 20 組
    simulated_draws = [generate_prediction() for _ in range(20)]
    st.write("🔄 模擬 20 組選號：")
    for i, draw in enumerate(simulated_draws, 1):
        st.write(f"第{i}組：{draw}")

    # 統計所有號碼頻率
    all_numbers = [num for draw in simulated_draws for num in draw]
    number_counts = Counter(all_numbers)
    top_numbers_counts = number_counts.most_common(15)
    st.write("🔥 20組模擬選號的熱門號碼（前15個+次數）：")
    st.dataframe(pd.DataFrame(top_numbers_counts, columns=['號碼', '次數']))
    

    # 建議選號邏輯（分數機制）
    st.subheader("🎯 建議選號（綜合分析）")
    top_number_pool = [num for num, _ in top_numbers_counts]
    available_numbers = set(top_number_pool)
    recommendations = []
    used_numbers = set()

    while len(recommendations) < 3 and len(available_numbers) >= 5:
        best_group = sorted(random.sample(list(available_numbers), 5))
        score = sum(number_counts.get(n, 0) for n in best_group)
        recommendations.append((best_group, score))
        used_numbers.update(best_group)
        available_numbers = available_numbers - used_numbers

    for i, (rec, score) in enumerate(recommendations, 1):
        st.write(f"建議第{i}組：{rec}（和值：{sum(rec)}，加總分數：{score}）")
