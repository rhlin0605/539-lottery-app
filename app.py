import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from itertools import combinations
from collections import Counter

st.set_page_config(page_title="今彩539 熱門號碼模擬器", layout="wide")

@st.cache_data
def download_and_parse_539_data():
    url = "https://www.pilio.idv.tw/lto539/list.asp"
    res = requests.get(url)
    res.encoding = "big5"

    soup = BeautifulSoup(res.text, "html.parser")
    tables = soup.find_all("table")
    target_table = None
    for table in tables:
        if "期數" not in table.text and "NO.1" in table.text:
            target_table = table
            break

    if target_table is None:
        st.error("找不到今彩539資料表格，請稍後再試。")
        return pd.DataFrame()

    df = pd.read_html(str(target_table), header=0)[0]
    df = df.dropna(how="any")
    df = df[df["NO.1"].apply(lambda x: isinstance(x, int))]

    # 日期轉換為 yyyy/mm/dd 格式
    def clean_date(d):
        if isinstance(d, str) and "(" in d:
            d = d.split("(")[0]
        try:
            mm, dd = map(int, d.split("/"))
            return f"2025/{mm:02d}/{dd:02d}"
        except:
            return None

    df["日期"] = df["日期"].apply(clean_date)
    df = df.dropna(subset=["日期"])
    return df.reset_index(drop=True)

def score_pair(pair):
    even_count = sum(1 for x in pair if x % 2 == 0)
    last_digit_count = len(set(x % 10 for x in pair))
    return even_count + last_digit_count

def get_top_weighted_pairs(df, recent_draws=3, top_n=5):
    recent_data = df.head(recent_draws)
    all_numbers = recent_data[[f"NO.{i}" for i in range(1, 6)]].values.flatten()
    number_counts = Counter(all_numbers)

    top_numbers = [num for num, _ in number_counts.most_common(10)]
    top_pairs = list(combinations(top_numbers, 2))
    pair_scores = [(pair, score_pair(pair)) for pair in top_pairs]
    sorted_pairs = sorted(pair_scores, key=lambda x: x[1], reverse=True)
    return sorted_pairs[:top_n]

# App 主流程
st.title("🎯 今彩539 熱門號碼策略模擬器")
st.markdown("資料來源：[pilio.idv.tw](https://www.pilio.idv.tw/lto539/list.asp)｜策略固定為最近 **3期** 模擬 + 熱門號碼加權（奇偶數 + 尾數）")

df = download_and_parse_539_data()
if not df.empty:
    st.dataframe(df.head(10), use_container_width=True)

    top_pairs = get_top_weighted_pairs(df)
    st.subheader("🔥 模擬推薦前5組號碼組合")
    for idx, (pair, score) in enumerate(top_pairs, 1):
        st.markdown(f"**#{idx} ➤ 號碼：{pair[0]}、{pair[1]} ｜ 分數：{score}**")
