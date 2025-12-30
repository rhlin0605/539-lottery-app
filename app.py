import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import random

CSV_PATH = "539_data.csv"

@st.cache_data
def fetch_new_data_from_website():
    url = "https://www.lottery.com.tw/l539?c=list"
    resp = requests.get(url)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = soup.select("table.tableWin tbody tr")
    new_data = []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 2:
            raw_date = cells[0].get_text(strip=True)
            raw_numbers = cells[1].get_text(strip=True)

            try:
                month, day = raw_date.split("/")
                today_year = datetime.today().year
                full_date = f"{today_year}/{int(month):02d}/{int(day):02d}"
                parsed_date = datetime.strptime(full_date, "%Y/%m/%d")
            except:
                continue

            parts = raw_numbers.replace("、", ",").replace(" ", ",").split(",")
            numbers = [int(p) for p in parts if p.isdigit()]

            if len(numbers) == 5:
                new_data.append({
                    "日期": parsed_date.strftime("%Y/%m/%d"),
                    "NO.1": numbers[0],
                    "NO.2": numbers[1],
                    "NO.3": numbers[2],
                    "NO.4": numbers[3],
                    "NO.5": numbers[4]
                })

    return pd.DataFrame(new_data)

def update_local_csv():
    try:
        df_old = pd.read_csv(CSV_PATH)
    except:
        df_old = pd.DataFrame(columns=["日期", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"])

    df_new = fetch_new_data_from_website()
    df_combined = pd.concat([df_old, df_new])
    df_combined = df_combined.drop_duplicates(subset=["日期"])
    df_combined = df_combined.sort_values(by="日期", ascending=False)
    df_combined.to_csv(CSV_PATH, index=False)
    return df_combined

def get_hot_numbers(df, recent_periods=20):
    flat = df.head(recent_periods)[["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]].values.flatten()
    return pd.Series(flat).value_counts().sort_values(ascending=False)

def simulate_pair(pair, df, simulations=5000, lookahead=3):
    count = 0
    for _ in range(simulations):
        start = random.randint(0, len(df) - lookahead - 1)
        sub = df.iloc[start+1:start+1+lookahead]
        future_numbers = set(sub[["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]].values.flatten())
        if pair[0] in future_numbers or pair[1] in future_numbers:
            count += 1
    return count / simulations

def main():
    st.title("🎯 今彩539 雙號策略推薦系統")

    df = update_local_csv()
    st.success(f"已讀取資料，共 {len(df)} 期")

    recent = df.head(100)
    last3 = df.head(3)[["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]].values.flatten()
    overhot = pd.Series(last3).value_counts()
    overhot_numbers = overhot[overhot >= 2].index.tolist()

    hot_numbers = get_hot_numbers(recent, recent_periods=20)
    hot_filtered = [n for n in hot_numbers.index if n not in overhot_numbers]

    pairs = []
    for i in range(len(hot_filtered)):
        for j in range(i+1, len(hot_filtered)):
            pairs.append((hot_filtered[i], hot_filtered[j]))

    st.write(f"候選雙號組合共 {len(pairs)} 組，開始模擬...")

    results = []
    for p in pairs:
        score = simulate_pair(p, df)
        odds_even_weight = 1.2 if (p[0] % 2) != (p[1] % 2) else 1.0
        tail_weight = 1.2 if (p[0] % 10) != (p[1] % 10) else 1.0
        total_score = score * odds_even_weight * tail_weight
        results.append({
            "號碼組合": f"{p[0]:02d}-{p[1]:02d}",
            "命中率": f"{score:.2%}",
            "加權分數": round(total_score, 4)
        })

    result_df = pd.DataFrame(results).sort_values(by="加權分數", ascending=False).head(3)
    st.subheader("🔥 前3名雙號推薦")
    st.table(result_df)

if __name__ == "__main__":
    main()
