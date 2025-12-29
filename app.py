import streamlit as st
import pandas as pd
import requests
from io import StringIO
from collections import Counter
import random
from itertools import combinations
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_latest_539():
    url = "https://www.pilio.idv.tw/lto539/list.asp"
    response = requests.get(url)
    response.encoding = "big5"  # 網站編碼為 big5
    soup = BeautifulSoup(response.text, "html.parser")

    # 尋找所有中獎資料列
    rows = soup.select("table.dynamic-table tr")
    
    for row in rows:
        cells = row.find_all("td")
        if len(cells) == 2:
            date_raw = cells[0].get_text(strip=True).split("\n")[0]  # 取 "12/29"
            numbers_raw = cells[1].get_text(strip=True)  # "05, 10, 13, 29, 37"
            try:
                month, day = map(int, date_raw.split("/"))
                year = datetime.today().year
                today = datetime.today()
                # 若跨年（例如12月時出現 1/2），補隔年
                if month > today.month + 1:
                    year += 1
                date_str = f"{year}/{month:02d}/{day:02d}"
                numbers = [n.strip() for n in numbers_raw.split(",")]
                if len(numbers) == 5:
                    return date_str, numbers
            except Exception as e:
                continue
    return None, None
    
def prepare_draws(df, recent_n=100):
    draw_cols = ["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]
    draws = df[draw_cols].astype(int).values.tolist()
    return [set(draw) for draw in draws[:recent_n]]

def get_top_hot_numbers(draws, top_n=13, exclude_recent=3):
    flat_numbers = [num for draw in draws for num in draw]
    number_counts = Counter(flat_numbers)
    recent_nums = [num for draw in draws[:exclude_recent] for num in draw]
    overhot = [num for num, cnt in Counter(recent_nums).items() if cnt >= 2]
    top_hot = [num for num, _ in number_counts.most_common(20) if num not in overhot][:top_n]
    return top_hot

def simulate_pair_hit(draws, pair, simulations=5000, sample_size=3):
    hits = 0
    for _ in range(simulations):
        sample_draws = random.sample(draws, sample_size)
        if any(num in draw for draw in sample_draws for num in pair):
            hits += 1
    return hits / simulations

def score_pair_with_rules(pair, base_prob):
    score = base_prob
    reasons = []
    odds = [num % 2 for num in pair]
    if sum(odds) == 1:
        score += 0.02
        reasons.append("奇偶平衡 +0.02")
    else:
        score -= 0.02
        reasons.append("奇偶失衡 -0.02")
    tails = [num % 10 for num in pair]
    if tails[0] == tails[1]:
        score -= 0.03
        reasons.append("尾數相同 -0.03")
    else:
        score += 0.01
        reasons.append("尾數不同 +0.01")
    return score, "；".join(reasons)

st.set_page_config(page_title="539 雙號策略模擬", layout="centered")
st.title("🎯 今彩 539 熱門雙號組合預測模擬")

if st.button("📥 取得最新 539 開獎資料"):
    date_str, numbers = fetch_latest_539()
    st.success("資料抓取成功，總共筆數：" + str(len(df)))
    draws = prepare_draws(df)

    st.write("⬇️ 最新 5 期開獎紀錄：")
    st.dataframe(df[["日期", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]].head(5))

    st.write("📊 執行模擬中，請稍候...")

    top_hot = get_top_hot_numbers(draws)
    top_pairs = list(combinations(top_hot, 2))
    results = []
    random.seed(42)
    for pair in top_pairs:
        prob = simulate_pair_hit(draws, pair)
        score, reason = score_pair_with_rules(pair, prob)
        results.append((pair, prob, score, reason))
    df_result = pd.DataFrame(results, columns=["號碼配對", "原始命中率", "加權後分數", "加權原因"])
    df_result = df_result.sort_values(by="加權後分數", ascending=False).reset_index(drop=True)
    st.subheader("🏆 前 5 名雙號建議組合（未來 3 期）")
    st.dataframe(df_result.head(5), use_container_width=True)
else:
    st.info("請按上方按鈕以載入最新資料並執行模擬。")
