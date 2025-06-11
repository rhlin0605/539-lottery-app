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
st.title("🎯 今彩539預測系統（多資料源+Debug Mode+日期統一+20組模擬+權重記憶）")

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
                return date_str.strip()
    return date_obj.strftime("%Y/%m/%d")

# 讀取CSV
try:
    local_df = pd.read_csv(local_csv, encoding='utf-8')
except FileNotFoundError:
    local_df = pd.DataFrame(columns=['Date', 'NO.1', 'NO.2', 'NO.3', 'NO.4', 'NO.5'])

# Sidebar 設定
debug_mode = st.sidebar.checkbox("🔧 Debug Mode", value=False)
num_fetch = st.sidebar.number_input("抓取最新N期（網站資料）", 1, 100, 50)

# 權重設定（支援記憶）
st.sidebar.header("⚙️ 權重設定（支援記憶）")
for key, label, default in [
    ('weight_sum', "和值分佈", 3),
    ('weight_streak', "連莊號碼", 3),
    ('weight_hot', "熱門號碼", 2),
    ('weight_pair', "雙號同開", 1),
    ('weight_head', "同首數", 1),
    ('weight_tail', "同尾數", 1),
    ('weight_miss', "連續未開期數", 1)
]:
    if key not in st.session_state:
        st.session_state[key] = default
    st.session_state[key] = st.sidebar.slider(label, 1, 10, st.session_state[key])

weight_sum = st.session_state.weight_sum
weight_streak = st.session_state.weight_streak
weight_hot = st.session_state.weight_hot
weight_pair = st.session_state.weight_pair
weight_head = st.session_state.weight_head
weight_tail = st.session_state.weight_tail
weight_miss = st.session_state.weight_miss
weight_multiplier = st.sidebar.slider("🎚️ 全域權重倍數", 0.5, 2.0, 1.0, step=0.1)

# 資料抓取函數
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

# Debug Mode
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

st.subheader("📅 最新資料（前5筆）")
st.dataframe(local_df.head(5))

# 統計分析
num_periods = st.selectbox("選擇統計期數（分析區間）", [15, 50, 100, 200], index=1)
df_sorted = local_df.head(num_periods)

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

# 統計顯示
st.subheader("📊 統計分析（前25筆）")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("### 🧮 和值分佈")
    st.dataframe(pd.DataFrame(sum_sorted, columns=["和值", "次數"]))
    st.markdown("### 🔄 連莊號碼排行")
    st.dataframe(pd.DataFrame(top_streaks, columns=["號碼", "連莊次數"]))
with col2:
    st.markdown("### 🔥 熱門號碼排行")
    st.dataframe(pd.DataFrame(hot_numbers, columns=["號碼", "次數"]))
    st.markdown("### 🔗 雙號同開排行")
    pair_df = pd.DataFrame(top_pairs, columns=["雙號組合", "次數"])
    pair_df["雙號組合"] = pair_df["雙號組合"].apply(lambda x: f"{x[0]} & {x[1]}")
    st.dataframe(pair_df)
with col3:
    st.markdown("### 🔢 同首數排行（至少2顆）")
    st.dataframe(pd.DataFrame(head_sorted, columns=["首數", "次數"]))
    st.markdown("### 🔢 同尾數排行（至少2顆）")
    st.dataframe(pd.DataFrame(tail_sorted, columns=["尾數", "次數"]))
    st.markdown("### 📉 連續未開期數統計")
    st.dataframe(pd.DataFrame(sorted_miss, columns=["號碼", "連續未開期數"]))

# 🔮 進階預測（20組模擬）
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

    simulated_draws = [generate_prediction() for _ in range(20)]
    st.write("🔄 模擬 20 組選號：")
    for i, draw in enumerate(simulated_draws, 1):
        st.write(f"第{i}組：{draw}")

    # 統計熱門號碼
    all_numbers = [num for draw in simulated_draws for num in draw]
    number_counts = Counter(all_numbers)
    top_numbers_counts = number_counts.most_common(15)
    st.write("🔥 20組模擬選號的熱門號碼（前15個+次數）：")
    st.dataframe(pd.DataFrame(top_numbers_counts, columns=['號碼', '次數']))

    # 建議3組
    st.subheader("🎯 建議選號（綜合分析）")
    top_numbers = [num for num, _ in top_numbers_counts]
    available_numbers = set(top_numbers)
    recommendations = []
    for _ in range(3):
        if len(available_numbers) < 5:
            remaining_pool = set(range(1, 40)) - available_numbers
            recommendation = list(available_numbers)
            while len(recommendation) < 5:
                recommendation.append(random.choice(list(remaining_pool)))
            recommendations.append(sorted(random.sample(recommendation, 5)))
        else:
            recommendations.append(sorted(random.sample(list(available_numbers), 5)))
    for i, rec in enumerate(recommendations, 1):
        st.write(f"建議第{i}組：{rec}（和值：{sum(rec)})")

# CSV下載
csv_download = local_df.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="📥 下載完整CSV",
    data=csv_download,
    file_name=f"539_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime='text/csv'
)
