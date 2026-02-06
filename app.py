# app.py
# Streamlit app for California Fantasy 5 (加州天天樂) auto-fetch + your strategy simulation
# Strategy source: your provided script logic (hot numbers, exclude over-hot, pair simulation, weighting) :contentReference[oaicite:3]{index=3}

import re
import random
fr:contentReference[oaicite:4]{index=4}ombinations
from collections import Counter
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

# ===============================
# Config
# ===============================
DEFAULT_CSV_PATH = "Fan_number.csv"

# Primary data source (accessible & has recent results listing)
SOURCE_SC888 = "https://sc888.net/index.php?s=%2FLotteryFan%2Findex"  # :contentReference[oaicite:5]{index=5}

# A simple user-agent reduces some trivial blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ===============================
# Utilities: parse and normalize
# ===============================

def normalize_date_to_csv_fmt(dt: datetime) -> str:
    """Return 'YYYY/M/D' (no zero padding), matching your CSV style."""
    return f"{dt.year}/{dt.month}/{dt.day}"

def parse_sc888_fantasy5(html: str) -> pd.DataFrame:
    """
    Parse sc888 '加州天天樂' page into DataFrame with columns:
    date, NO.1..NO.5

    The page text includes blocks like:
    2026-02-06 星期五 08 26 28 32 38
    We'll regex scan for: YYYY-MM-DD + 5 numbers (1-39).
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    # Match: date + (optional weekday text) + five numbers (allow leading zeros)
    # We'll capture: YYYY-MM-DD then 5 numbers separated by whitespace/newlines
    pattern = re.compile(
        r"(?P<date>\d{4}-\d{2}-\d{2})\s*(?:星期[一二三四五六日])?\s*"
        r"(?P<n1>\d{1,2})\s+(?P<n2>\d{1,2})\s+(?P<n3>\d{1,2})\s+(?P<n4>\d{1,2})\s+(?P<n5>\d{1,2})"
    )

    rows = []
    for m in pattern.finditer(text):
        d = datetime.strptime(m.group("date"), "%Y-%m-%d")
        nums = [int(m.group(f"n{i}")) for i in range(1, 6)]

        # Basic sanity: Fantasy 5 is 1~39, 5 unique numbers
        if any(n < 1 or n > 39 for n in nums):
            continue
        if len(set(nums)) != 5:
            continue

        rows.append([normalize_date_to_csv_fmt(d), *nums])

    if not rows:
        return pd.DataFrame(columns=["date", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"])

    df = pd.DataFrame(rows, columns=["date", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"])

    # sc888 page lists recent first; keep recent-first
    # Remove duplicates by date (keep first)
    df = df.drop_duplicates(subset=["date"], keep="first")

    # Sort by date desc (recent first)
    df["__dt"] = pd.to_datetime(df["date"], format="%Y/%m/%d")
    df = df.sort_values("__dt", ascending=False).drop(columns="__dt").reset_index(drop=True)
    return df

@st.cache_data(ttl=300)
def fetch_latest_from_web() -> pd.DataFrame:
    """Fetch latest draws from the web source(s)."""
    resp = requests.get(SOURCE_SC888, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return parse_sc888_fantasy5(resp.text)

def load_local_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = ["date", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少欄位：{missing}（需要：{required}）")

    # Normalize types
    for c in ["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    # Keep recent first
    df["__dt"] = pd.to_datetime(df["date"], format="%Y/%m/%d", errors="coerce")
    df = df.dropna(subset=["__dt"]).sort_values("__dt", ascending=False).drop(columns="__dt")
    df = df.reset_index(drop=True)
    return df

def merge_and_update(local_df: pd.DataFrame, web_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return:
    - merged_df: local + new web rows (recent first)
    - new_rows_df: only newly added rows
    """
    local_dates = set(local_df["date"].astype(str).tolist())
    new_rows = web_df[~web_df["date"].astype(str).isin(local_dates)].copy()
    merged = pd.concat([new_rows, local_df], ignore_index=True)

    # De-dup & sort recent first
    merged["__dt"] = pd.to_datetime(merged["date"], format="%Y/%m/%d", errors="coerce")
    merged = merged.dropna(subset=["__dt"]).sort_values("__dt", ascending=False)
    merged = merged.drop_duplicates(subset=["date"], keep="first").drop(columns="__dt").reset_index(drop=True)

    return merged, new_rows.reset_index(drop=True)

# ===============================
# Strategy (your logic) :contentReference[oaicite:6]{index=6}
# ===============================

def df_to_draw_sets(df: pd.DataFrame, rec:contentReference[oaicite:7]{index=7}et[int]]:
    draw_cols = ["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]
    draws = df[draw_cols].dropna().astype(int).values.tolist()
    draws = draws[:recent_n]  # recent first
    return [set(d) for d in draws]

def get_top_hot_numbers(draws: list[set[int]], top_n: int, exclude_recent: int) -> list[int]:
    flat_numbers = [num for draw in draws for num in draw]
    number_counts = Counter(flat_numbers)

    recent_nums = [num for draw in draws[:exclude_recent] for num in draw]
    overhot = [num for num, cnt in Counter(recent_nums).items() if cnt >= 2]

    top_hot = [num for num, _ in number_counts.most_common(20) if num not in overhot][:top_n]
    return top_hot

def simulate_pair_hit(draws: list[set[int]], pair: tuple[int, int], simulations: int, sample_size: int) -> float:
    hits = 0
    for _ in range(simulations):
        sample_draws = random.sample(draws, sample_size)
        if any(num in draw for draw in sample_draws for num in pair):
            hits += 1
    return hits / simulations

def score_pair_with_rules(pair: tuple[int, int], base_prob: float) -> tuple[float, str]:
    score = base_prob
    reasons = []

    # 奇偶加權
    odds = [num % 2 for num in pair]
    if sum(odds) == 1:
        score += 0.02
        reasons.append("奇偶平衡 +0.02")
    else:
        score -= 0.02
        reasons.append("奇偶失衡 -0.02")

    # 尾數加權
    tails = [num % 10 for num in pair]
    if tails[0] == tails[1]:
        score -= 0.03
        reasons.append("尾數相同 -0.03")
    else:
        score += 0.01
        reasons.append("尾數不同 +0.01")

    return score, "；".join(reasons)

def run_strategy(df: pd.DataFrame,
                 recent_n: int,
                 top_n: int,
                 exclude_recent: int,
                 simulations: int,
                 sample_size: int,
                 seed: int) -> pd.DataFrame:
    draws = df_to_draw_sets(df, recent_n=recent_n)
    if len(draws) < max(sample_size, exclude_recent, 10):
        raise ValueError(f"可用期數不足：目前只有 {len(draws)} 期，至少需要 >= {max(sample_size, exclude_recent, 10)} 期。")

    top_hot = get_top_hot_numbers(draws, top_n=top_n, exclude_recent=exclude_recent)

    # 固定種子，確保可重現
    random.seed(seed)

    results = []
    for pair in combinations(top_hot, 2):
        prob = simulate_pair_hit(draws, pair, simulations=simulations, sample_size=sample_size)
        score, reason = score_pair_with_rules(pair, prob)
        results.append((f"{pair[0]}-{pair[1]}", prob, score, reason))

    out = pd.DataFrame(results, columns=["號碼配對", "原始命中率", "加權後分數", "加權原因"])
    out = out.sort_values("加權後分數", ascending=False).reset_index(drop=True)
    return out

# ===============================
# Streamlit UI
# ===============================

st.set_page_config(page_title="加州天天樂 Fantasy 5｜自動抓取＋策略分析", layout="wide")

st.title("加州天天樂 (Fantasy 5)｜自動抓取最新號碼 + 你的策略分析")
st.caption("資料來源預設使用可正常抓取的第三方結果頁（官方頁面常見 403）。請理性看待模擬結果。")

with st.sidebar:
    st.subheader("資料設定")
    csv_path = st.text_input("本地/專案內 CSV 路徑", value=DEFAULT_CSV_PATH)

    st.subheader("策略參數（可調）")
    recent_n = st.number_input("取最近 N 期做統計", min_value=20, max_value=2000, value=63, step=1)
    top_n = st.number_input("熱門號碼 top_n", min_value=5, max_value=39, value=13, step=1)
    exclude_recent = st.number_input("排除最近幾期的過熱號（>=2 次）", min_value=1, max_value=20, value=3, step=1)
    simulations = st.number_input("模擬次數", min_value=100, max_value=200000, value=5096, step=100)
    sample_size = st.number_input("抽樣期數（預測窗口）", min_value=1, max_value=30, value=3, step=1)
    seed = st.number_input("Random seed（固定可重現）", min_value=0, max_value=10_000, value=66, step=1)

    st.divider()
    do_update = st.button("🔄 抓取最新號碼並更新 CSV")
    do_run = st.button("📈 執行策略分析")

# Load local
try:
    local_df = load_local_csv(csv_path)
except Exception as e:
    st.error(f"讀取 CSV 失敗：{e}")
    st.stop()

colA, colB = st.columns([1, 1])

with colA:
    st.subheader("本地歷史資料（最近 20 期）")
    st.dataframe(local_df.head(20), use_container_width=True)

with colB:
    st.subheader("網站最新資料（抓取預覽）")
    try:
        web_df = fetch_latest_from_web()
        st.dataframe(web_df.head(20), use_container_width=True)
        st.caption(f"來源：{SOURCE_SC888}")
    except Exception as e:
        web_df = None
        st.warning(f"抓取網站資料失敗：{e}")

# Update CSV if requested
updated_df = local_df
new_rows_df = pd.DataFrame()

if do_update:
    if web_df is None:
        st.error("目前無法取得網站資料，請稍後再試或更換來源。")
    else:
        updated_df, new_rows_df = merge_and_update(local_df, web_df)

        st.success(f"已合併完成：新增 {len(new_rows_df)} 期。")
        if len(new_rows_df) > 0:
            st.subheader("✅ 新增的期數")
            st.dataframe(new_rows_df, use_container_width=True)

        # Try to persist to disk (works locally; Streamlit Cloud is ephemeral but still okay per session)
        try:
            updated_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            st.info(f"已寫回 CSV：{csv_path}")
        except Exception as e:
            st.warning(f"寫回 CSV 失敗（但已在記憶體合併）：{e}")

        st.download_button(
            "⬇️ 下載更新後 CSV",
            data=updated_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="Fan_number_updated.csv",
            mime="text/csv"
        )

# Run strategy if requested
if do_run:
    # If user updated just now, use updated_df; else use local
    base_df = updated_df

    st.subheader("策略分析結果")
    try:
        result_df = run_strategy(
            base_df,
            recent_n=int(recent_n),
            top_n=int(top_n),
            exclude_recent=int(exclude_recent),
            simulations=int(simulations),
            sample_size=int(sample_size),
            seed=int(seed),
        )

        st.write("🎯 前 3 名建議（加權後分數最高）")
        st.dataframe(result_df.head(3), use_container_width=True)

        st.write("完整排名（可排序）")
        st.dataframe(result_df, use_container_width=True)

        st.download_button(
            "⬇️ 下載結果 CSV（排名）",
            data=result_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="fantasy5_pair_ranking.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"策略執行失敗：{e}")

