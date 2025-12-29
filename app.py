import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime

@st.cache_data
def fetch_latest_539_data():
    url = "https://www.pilio.idv.tw/lto539/list.asp"
    response = requests.get(url)
    response.encoding = 'big5'  # Pilio 網站編碼為 big5
    soup = BeautifulSoup(response.text, "html.parser")

    rows = soup.select("table tr")
    data = []
    current_year = datetime.today().year
    last_month = None

    for i in range(0, len(rows) - 1, 2):
        date_row = rows[i].find_all("td")
        num_row = rows[i + 1].find_all("td")

        if not date_row or not num_row:
            continue

        raw_date = date_row[0].text.strip()
        raw_num_text = num_row[0].text.strip()

        # 跳過非標準格式
        if not re.match(r"^\d{1,2}/\d{1,2}$", raw_date):
            continue

        # 判斷年份 (跨年資料)
        try:
            month = int(raw_date.split("/")[0])
            if last_month and month < last_month:
                current_year += 1
            last_month = month
        except:
            continue

        # 處理日期格式 yyyy/mm/dd
        try:
            parsed_date = datetime.strptime(f"{current_year}/{raw_date}", "%Y/%m/%d")
            formatted_date = parsed_date.strftime("%Y/%m/%d")
        except:
            continue

        # 處理號碼，去除前綴如 "25(一)"
        number_match = re.search(r"((\d{2},\s*){4}\d{2})", raw_num_text)
        if number_match:
            numbers = [n.strip() for n in number_match.group(1).split(",")]
            if len(numbers) == 5:
                data.append([formatted_date] + numbers)

    df = pd.DataFrame(data, columns=["日期", "NO.1", "NO.2", "NO.3", "NO.4", "NO.5"])
    return df

st.title("今彩 539 最新一期資料 - Pilio")
df = fetch_latest_539_data()

if df.empty:
    st.error("無法抓取資料，請稍後再試。")
else:
    st.dataframe(df)
