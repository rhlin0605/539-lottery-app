import streamlit as st
import pandas as pd
import requests
from collections import Counter
from itertools import combinations
import random

# --------------------------
# 資料下載與處理
# --------------------------
@st.cache_data

def download_and_parse_539_data():
    url = "https://www.pilio.idv.tw/lto539/list.asp"
    html = requests.get(url).content.decode("big5", errors="ignore")
    tables = pd.read_html(html)

    df = tables[0].copy()
    df.columns = ["期別", "日期", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]
    df = df.dropna().reset_index(drop=True)
    df = df.head(200)  # 最多200期
    for col in ["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]:
        df[col] = df[col].astype(int)

    return df


def extract_draws(df, recent_n=100):
    draw_cols = ["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]
    draws = df[draw_cols].head(recent_n).values.tolist()
    return [set(draw) for draw in draws]


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


# --------------------------
# Streamlit 介面開始
# --------------------------
st.title("🎯 今彩539 熱門雙號模擬分析 App")

with st.spinner("下載並解析最新開獎資料中..."):
    df = download_and_parse_539_data()
    draws = extract_draws(df)
    st.success("最新開獎資料已讀取完成！")

st.markdown(f"共載入 **{len(df)} 期** 資料，顯示近 100 期統計分析")

# 熱門號碼區
top_hot = get_top_hot_numbers(draws)
st.markdown("### 🔥 熱門號碼前 15 名 (排除近3期過熱)")
st.write(sorted(top_hot))

# 模擬開始
st.markdown("---")
st.markdown("### 🧪 雙號配對模擬（模擬未來 3 期）")

if st.button("開始模擬分析"):
    st.info("模擬中，請稍候... (約 5 秒)")
    random.seed(42)

    results = []
    top_pairs = list(combinations(top_hot, 2))

    for pair in top_pairs:
        prob = simulate_pair_hit(draws, pair, sample_size=3)
        score, reason = score_pair_with_rules(pair, prob)
        results.append((pair, prob, score, reason))

    df_result = pd.DataFrame(results, columns=["號碼配對", "原始命中率", "加權後分數", "加權原因"])
    df_result = df_result.sort_values(by="加權後分數", ascending=False).reset_index(drop=True)
    st.markdown("#### 🏅 前 5 名加權雙號建議：")
    st.dataframe(df_result.head(5), use_container_width=True)

    st.markdown("---")
    with st.expander("📋 查看所有模擬配對結果"):
        st.dataframe(df_result, use_container_width=True)
