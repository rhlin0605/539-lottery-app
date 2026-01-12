import base64
import io
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


# ===============================
# 基本設定
# ===============================
TZ_TAIPEI = timezone(timedelta(hours=8))
DEFAULT_COLS = ["日期", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]


# ===============================
# GitHub 設定資料類
# ===============================
@dataclass
class GitHubCfg:
    token: str
    owner: str
    repo: str
    branch: str
    path: str
    user_name: str
    user_email: str


def get_github_cfg() -> GitHubCfg:
    g = st.secrets["github"]
    return GitHubCfg(
        token=g["token"],
        owner=g["repo_owner"],
        repo=g["repo_name"],
        branch=g.get("branch", "main"),
        path=g.get("csv_path", "539_data.csv"),
        user_name=g.get("commit_user_name", "streamlit-bot"),
        user_email=g.get("commit_user_email", "streamlit-bot@users.noreply.github.com"),
    )


# ===============================
# HTTP Helpers
# ===============================
def http_get(url: str, headers: dict | None = None, timeout: int = 20) -> requests.Response:
    return requests.get(url, headers=headers, timeout=timeout)


def http_put(url: str, headers: dict, payload: dict, timeout: int = 20) -> requests.Response:
    return requests.put(url, headers=headers, data=json.dumps(payload), timeout=timeout)


# ===============================
# 讀取 GitHub CSV（raw）
# ===============================
@st.cache_data(ttl=3600, show_spinner=False)
def read_csv_from_github_raw(owner: str, repo: str, branch: str, path: str) -> str:
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    r = http_get(raw_url)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub raw 讀取失敗: {r.status_code} {r.text[:200]}")
    return r.text


def read_df_from_github(cfg: GitHubCfg) -> pd.DataFrame:
    try:
        csv_text = read_csv_from_github_raw(cfg.owner, cfg.repo, cfg.branch, cfg.path)
        df = pd.read_csv(io.StringIO(csv_text))
    except Exception:
        df = pd.DataFrame(columns=DEFAULT_COLS)

    # 標準化欄位
    for c in DEFAULT_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[DEFAULT_COLS].copy()

    # 日期轉換
    if len(df) > 0:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df = df.dropna(subset=["日期"])

    # 數字轉 int
    for c in ["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    # 排序（新到舊）
    if len(df) > 0:
        df = df.sort_values("日期", ascending=False).reset_index(drop=True)
    return df


# ===============================
# GitHub Contents API：取得 SHA + 回寫內容
# ===============================
def github_contents_url(cfg: GitHubCfg) -> str:
    return f"https://api.github.com/repos/{cfg.owner}/{cfg.repo}/contents/{cfg.path}"


def github_headers(cfg: GitHubCfg) -> dict:
    return {
        "Authorization": f"Bearer {cfg.token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }


def get_github_file_sha(cfg: GitHubCfg) -> str | None:
    url = github_contents_url(cfg)
    r = http_get(url, headers=github_headers(cfg))
    if r.status_code == 200:
        js = r.json()
        return js.get("sha")
    if r.status_code == 404:
        return None
    raise RuntimeError(f"取得 GitHub 檔案 SHA 失敗: {r.status_code} {r.text[:200]}")


def push_df_to_github(cfg: GitHubCfg, df: pd.DataFrame, message: str) -> None:
    # 內容轉 CSV
    df_out = df.copy()
    # 日期輸出成 YYYY/MM/DD（與你原本格式一致）
    df_out["日期"] = df_out["日期"].dt.strftime("%Y/%m/%d")
    csv_str = df_out.to_csv(index=False)

    content_b64 = base64.b64encode(csv_str.encode("utf-8")).decode("utf-8")
    sha = get_github_file_sha(cfg)

    payload = {
        "message": message,
        "content": content_b64,
        "branch": cfg.branch,
        "committer": {"name": cfg.user_name, "email": cfg.user_email},
    }
    if sha:
        payload["sha"] = sha

    url = github_contents_url(cfg)
    r = http_put(url, headers=github_headers(cfg), payload=payload)

    if r.status_code not in (200, 201):
        # 常見：409 conflict（多人同時 push）
        raise RuntimeError(f"GitHub 回寫失敗: {r.status_code} {r.text[:300]}")


# ===============================
# 官網抓取：今彩539
# ===============================
def infer_year_for_mmdd(mm: int, dd: int, now: datetime) -> int:
    """
    官網若只有 MM/DD，需推斷年份：
    - 預設用今年
    - 若 mm 大於當前月份很多（例如現在 1 月，抓到 12 月） -> 視為去年
    """
    year = now.year
    if mm > now.month + 1:  # 容錯：1月看到12月
        year -= 1
    return year


@st.cache_data(ttl=1800, show_spinner=False)  # 半小時最多抓一次，避免被打爆
def fetch_latest_draws_from_website() -> pd.DataFrame:
    url = "https://www.lottery.com.tw/l539?c=list"
    resp = http_get(url)
    resp.encoding = "utf-8"
    soup = Beautifulsoup = BeautifulSoup(resp.text, "html.parser")

    rows = soup.select("table.tableWin tbody tr")
    now = datetime.now(TZ_TAIPEI)

    data = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        raw_date = cells[0].get_text(strip=True)
        raw_numbers = cells[1].get_text(strip=True)

        # date: "MM/DD"
        try:
            mm_str, dd_str = raw_date.split("/")
            mm, dd = int(mm_str), int(dd_str)
            year = infer_year_for_mmdd(mm, dd, now)
            parsed = datetime(year, mm, dd, tzinfo=TZ_TAIPEI)
        except Exception:
            continue

        parts = raw_numbers.replace("、", ",").replace(" ", ",").split(",")
        nums = [int(p) for p in parts if p.isdigit()]
        if len(nums) != 5:
            continue

        data.append(
            {
                "日期": parsed.date().isoformat(),
                "NO.1": nums[0],
                "NO.2": nums[1],
                "NO.3": nums[2],
                "NO.4": nums[3],
                "NO.5": nums[4],
            }
        )

    df = pd.DataFrame(data)
    if len(df) == 0:
        return pd.DataFrame(columns=DEFAULT_COLS)

    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.dropna(subset=["日期"])
    df = df.sort_values("日期", ascending=False).reset_index(drop=True)
    return df[DEFAULT_COLS]


# ===============================
# 更新流程：讀 GitHub → 抓官網 → 補新 → 回寫 GitHub
# ===============================
def update_github_csv(cfg: GitHubCfg) -> pd.DataFrame:
    df_old = read_df_from_github(cfg)
    df_web = fetch_latest_draws_from_website()

    if len(df_old) == 0:
        last_date = None
    else:
        last_date = df_old["日期"].max()

    if last_date is not None:
        df_new = df_web[df_web["日期"] > last_date].copy()
    else:
        df_new = df_web.copy()

    if len(df_new) == 0:
        return df_old

    df_combined = pd.concat([df_old, df_new], ignore_index=True)
    df_combined = df_combined.drop_duplicates(subset=["日期"])
    df_combined = df_combined.sort_values("日期", ascending=False).reset_index(drop=True)

    # Push 回 GitHub（避免每次都 commit：只有有新資料才 commit）
    msg = f"Auto update 539_data.csv (+{len(df_new)} draws) {datetime.now(TZ_TAIPEI).strftime('%Y-%m-%d %H:%M:%S %z')}"
    push_df_to_github(cfg, df_combined, msg)

    # 重要：push 完後，Streamlit cache 可能還拿舊的 raw。這裡手動清一次相關 cache。
    read_csv_from_github_raw.clear()

    return df_combined


# ===============================
# 策略（你原本的邏輯保留，僅做安全修正）
# ===============================
def get_hot_numbers(df: pd.DataFrame, recent_periods: int = 20) -> pd.Series:
    sub = df.head(recent_periods)[["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]]
    flat = sub.values.flatten()
    return pd.Series(flat).value_counts().sort_values(ascending=False)


def simulate_pair(pair: tuple[int, int], df: pd.DataFrame, simulations: int = 5000, lookahead: int = 3) -> float:
    if len(df) <= lookahead + 1:
        return 0.0

    hit = 0
    max_start = len(df) - lookahead - 1

    # 這裡是「歷史抽樣」模擬，不使用未來資料
    for _ in range(simulations):
        start = random.randint(0, max_start)
        future = df.iloc[start + 1 : start + 1 + lookahead]
        future_numbers = set(future[["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]].values.flatten())
        if (pair[0] in future_numbers) or (pair[1] in future_numbers):
            hit += 1

    return hit / simulations


# ===============================
# Streamlit UI
# ===============================
def main():
    st.write("DEBUG secrets github:", st.secrets["github"])

    st.title("今彩539 雙號策略推薦系統（GitHub 永久資料版）")

    cfg = get_github_cfg()

    with st.status("同步資料中（GitHub ↔ 官網）...", expanded=False):
        try:
            df = update_github_csv(cfg)
            st.success(f"資料已就緒，共 {len(df)} 期（來源：GitHub，必要時由官網補齊）")
        except Exception as e:
            st.error("同步失敗，將改用 GitHub 既有資料（不更新）")
            st.exception(e)
            df = read_df_from_github(cfg)
            st.info(f"已載入 GitHub 既有資料，共 {len(df)} 期")

    if len(df) == 0:
        st.warning("目前沒有可用資料。請先在 repo 放入 539_data.csv（至少 1 筆）。")
        return

    # 顯示最後更新日期
    st.caption(f"最新一期日期：{df['日期'].max().strftime('%Y-%m-%d')}")

    # 取最近 100 期策略用
    recent = df.head(100).copy()

    # 近 3 期出現 >=2 的過熱號
    last3 = recent.head(3)[["NO.1", "NO.2", "NO.3", "NO.4", "NO.5"]].values.flatten()
    overhot = pd.Series(last3).value_counts()
    overhot_numbers = overhot[overhot >= 2].index.tolist()

    hot_numbers = get_hot_numbers(recent, recent_periods=20)
    hot_filtered = [int(n) for n in hot_numbers.index.tolist() if int(n) not in overhot_numbers]

    # 產生 pair
    pairs = []
    for i in range(len(hot_filtered)):
        for j in range(i + 1, len(hot_filtered)):
            pairs.append((hot_filtered[i], hot_filtered[j]))

    st.write(f"候選雙號組合：{len(pairs)} 組")
    st.write(f"排除過熱號（近3期出現>=2）：{sorted(overhot_numbers)}")

    # 控制模擬量（Cloud 成本考量：提供 UI）
    simulations = st.slider("每組模擬次數", min_value=500, max_value=20000, value=5000, step=500)
    lookahead = st.selectbox("命中窗口（期數）", [3, 4, 5], index=0)

    if st.button("開始計算 Top 3", type="primary"):
        with st.spinner("模擬計算中..."):
            results = []
            for p in pairs:
                score = simulate_pair(p, df, simulations=simulations, lookahead=lookahead)

                # 權重：奇偶平衡 / 尾數分散
                odds_even_weight = 1.2 if (p[0] % 2) != (p[1] % 2) else 1.0
                tail_weight = 1.2 if (p[0] % 10) != (p[1] % 10) else 1.0
                total_score = score * odds_even_weight * tail_weight

                results.append(
                    {
                        "號碼組合": f"{p[0]:02d}-{p[1]:02d}",
                        "原始命中率": score,
                        "奇偶權重": odds_even_weight,
                        "尾數權重": tail_weight,
                        "加權分數": total_score,
                    }
                )

            result_df = pd.DataFrame(results).sort_values(by="加權分數", ascending=False).head(3)

        st.subheader("前 3 名雙號推薦")
        show = result_df.copy()
        show["原始命中率"] = show["原始命中率"].map(lambda x: f"{x:.2%}")
        show["加權分數"] = show["加權分數"].map(lambda x: f"{x:.4f}")
        st.table(show)

    with st.expander("查看最近 20 期資料"):
        st.dataframe(df.head(20))


if __name__ == "__main__":
    main()

