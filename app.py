
import pandas as pd
import streamlit as st
import altair as alt

  
st.set_page_config(
    page_title="전월세 매물 경제성 비교 앱",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 전월세 매물 경제성 비교 앱")
st.caption("실매물의 보증금·월세·관리비를 같은 기준의 월 환산비용으로 비교합니다.")


def calc_monthly_cost(
    deposit_manwon: float,
    rent_manwon: float,
    maintenance_manwon: float,
    annual_invest_return: float,
    loan_ratio: float,
    annual_loan_rate: float,
) -> dict:
    """
    월 환산 총비용 =
        월세 + 관리비
        + 보증금의 월 기회비용
        + 보증금 대출분의 월 이자비용

    단위:
    - deposit_manwon, rent_manwon, maintenance_manwon: 만원
    - annual rates: decimal, e.g. 0.05 = 5%
    """
    monthly_invest_rate = (1 + annual_invest_return) ** (1 / 12) - 1
    monthly_loan_rate = annual_loan_rate / 12

    deposit_opp_cost = deposit_manwon * monthly_invest_rate
    loan_interest_cost = deposit_manwon * loan_ratio * monthly_loan_rate
    cash_outflow = rent_manwon + maintenance_manwon
    total_monthly_cost = cash_outflow + deposit_opp_cost + loan_interest_cost

    return {
        "월 현금지출(만원)": cash_outflow,
        "보증금 기회비용(만원/월)": deposit_opp_cost,
        "보증금 대출이자(만원/월)": loan_interest_cost,
        "월 환산 총비용(만원)": total_monthly_cost,
    }


def classify_listing(deposit_manwon: float, rent_manwon: float) -> str:
    """
    법적 분류가 아니라, 비교 목적의 실용적 분류입니다.
    """
    if deposit_manwon >= 8000 and rent_manwon <= 20:
        return "전세형"
    if deposit_manwon >= 3000 and rent_manwon <= 60:
        return "반전세형"
    return "월세형"


def add_analysis_columns(df: pd.DataFrame, annual_return, loan_ratio, loan_rate) -> pd.DataFrame:
    df = df.copy()

    required = ["매물명", "지역", "보증금(만원)", "월세(만원)", "관리비(만원)"]
    for col in required:
        if col not in df.columns:
            df[col] = ""

    for col in ["보증금(만원)", "월세(만원)", "관리비(만원)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    results = df.apply(
        lambda row: calc_monthly_cost(
            deposit_manwon=float(row["보증금(만원)"]),
            rent_manwon=float(row["월세(만원)"]),
            maintenance_manwon=float(row["관리비(만원)"]),
            annual_invest_return=annual_return,
            loan_ratio=loan_ratio,
            annual_loan_rate=loan_rate,
        ),
        axis=1,
        result_type="expand",
    )

    df = pd.concat([df, results], axis=1)
    df["유형"] = df.apply(lambda r: classify_listing(r["보증금(만원)"], r["월세(만원)"]), axis=1)

    avg_cost = df["월 환산 총비용(만원)"].mean()
    min_cost = df["월 환산 총비용(만원)"].min()

    non_rent_cost = (
        df["관리비(만원)"]
        + df["보증금 기회비용(만원/월)"]
        + df["보증금 대출이자(만원/월)"]
    )

    df["시장평균 기준 적정 월세(만원)"] = avg_cost - non_rent_cost
    df["시장평균 대비 조정액(만원)"] = df["시장평균 기준 적정 월세(만원)"] - df["월세(만원)"]

    df["최저비용 기준 적정 월세(만원)"] = min_cost - non_rent_cost
    df["최저비용 대비 조정액(만원)"] = df["최저비용 기준 적정 월세(만원)"] - df["월세(만원)"]

    df["순위"] = df["월 환산 총비용(만원)"].rank(method="min", ascending=True).astype(int)

    return df.sort_values("월 환산 총비용(만원)").reset_index(drop=True)


def to_csv_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


sample_data = pd.DataFrame(
    [
        {"매물명": "낙성대 A", "지역": "낙성대역", "보증금(만원)": 1000, "월세(만원)": 60, "관리비(만원)": 10, "메모": "공개 매물 예시"},
        {"매물명": "낙성대 B", "지역": "낙성대역", "보증금(만원)": 2000, "월세(만원)": 50, "관리비(만원)": 10, "메모": "공개 매물 예시"},
        {"매물명": "낙성대 C", "지역": "낙성대역", "보증금(만원)": 2000, "월세(만원)": 75, "관리비(만원)": 0, "메모": "공개 매물 예시"},
        {"매물명": "봉천동 A", "지역": "봉천동", "보증금(만원)": 500, "월세(만원)": 55, "관리비(만원)": 12, "메모": "공개 매물 예시"},
        {"매물명": "봉천동 B", "지역": "봉천동", "보증금(만원)": 3000, "월세(만원)": 60, "관리비(만원)": 8, "메모": "공개 매물 예시"},
        {"매물명": "봉천동 C", "지역": "봉천동", "보증금(만원)": 5000, "월세(만원)": 50, "관리비(만원)": 10, "메모": "공개 매물 예시"},
        {"매물명": "서울대입구 A", "지역": "서울대입구역", "보증금(만원)": 1000, "월세(만원)": 70, "관리비(만원)": 0, "메모": "입력 예시"},
        {"매물명": "서울대입구 B", "지역": "서울대입구역", "보증금(만원)": 800, "월세(만원)": 52, "관리비(만원)": 8, "메모": "입력 예시"},
        {"매물명": "전세형 예시", "지역": "봉천동", "보증금(만원)": 10000, "월세(만원)": 0, "관리비(만원)": 0, "메모": "보증금 높은 매물 예시"},
    ]
)


st.sidebar.header("⚙️ 가정값")

annual_return_pct = st.sidebar.slider(
    "연 투자수익률 (%)",
    min_value=0.0,
    max_value=15.0,
    value=5.0,
    step=0.5,
)

loan_ratio_pct = st.sidebar.slider(
    "보증금 중 대출 비율 (%)",
    min_value=0.0,
    max_value=100.0,
    value=50.0,
    step=5.0,
)

loan_rate_pct = st.sidebar.slider(
    "전월세 보증금 대출금리 (%)",
    min_value=0.0,
    max_value=10.0,
    value=4.0,
    step=0.25,
)

residence_months = st.sidebar.slider(
    "거주 기간 (개월)",
    min_value=1,
    max_value=72,
    value=24,
    step=1,
)

annual_return = annual_return_pct / 100
loan_ratio = loan_ratio_pct / 100
loan_rate = loan_rate_pct / 100


st.subheader("1. 매물 입력")

input_mode = st.radio(
    "입력 방식",
    ["예시 데이터 사용", "CSV 업로드", "직접 편집"],
    horizontal=True,
)

if input_mode == "CSV 업로드":
    uploaded = st.file_uploader("CSV 파일 업로드", type=["csv"])
    if uploaded is not None:
        raw_df = pd.read_csv(uploaded)
    else:
        st.info("CSV를 업로드하거나 다른 입력 방식을 선택하세요.")
        raw_df = sample_data.copy()
elif input_mode == "직접 편집":
    st.write("아래 표를 직접 수정하거나 행을 추가하세요. 단위는 모두 **만원**입니다.")
    raw_df = st.data_editor(
        sample_data.copy(),
        num_rows="dynamic",
        use_container_width=True,
        key="listing_editor",
    )
else:
    raw_df = sample_data.copy()
    st.dataframe(raw_df, use_container_width=True)


analyzed = add_analysis_columns(raw_df, annual_return, loan_ratio, loan_rate)
analyzed["예상 총비용(만원)"] = analyzed["월 환산 총비용(만원)"] * residence_months


st.subheader("2. 한눈에 보는 결론")

best = analyzed.iloc[0]
worst = analyzed.iloc[-1]
avg_monthly_cost = analyzed["월 환산 총비용(만원)"].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("가장 경제적인 매물", best["매물명"], f'{best["월 환산 총비용(만원)"]:.1f}만원/월')
col2.metric("평균 월 환산비용", f"{avg_monthly_cost:.1f}만원/월")
col3.metric("최고-최저 차이", f'{worst["월 환산 총비용(만원)"] - best["월 환산 총비용(만원)"]:.1f}만원/월')
col4.metric(f"{residence_months}개월 기준 최저 총비용", f'{best["예상 총비용(만원)"]:.0f}만원')


st.subheader("3. 시각화")

chart_df = analyzed.copy()
chart_df["매물명"] = chart_df["매물명"].astype(str)

bar = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(
        x=alt.X("월 환산 총비용(만원):Q", title="월 환산 총비용 (만원/월)"),
        y=alt.Y("매물명:N", sort="-x", title="매물"),
        color=alt.Color("유형:N", title="유형"),
        tooltip=[
            "매물명",
            "지역",
            "유형",
            alt.Tooltip("보증금(만원):Q", format=",.0f"),
            alt.Tooltip("월세(만원):Q", format=",.0f"),
            alt.Tooltip("관리비(만원):Q", format=",.0f"),
            alt.Tooltip("월 환산 총비용(만원):Q", format=",.2f"),
        ],
    )
    .properties(height=max(350, len(chart_df) * 28))
)

st.altair_chart(bar, use_container_width=True)

col_a, col_b = st.columns(2)

with col_a:
    scatter = (
        alt.Chart(chart_df)
        .mark_circle(size=120)
        .encode(
            x=alt.X("보증금(만원):Q", title="보증금 (만원)"),
            y=alt.Y("월 현금지출(만원):Q", title="월세 + 관리비 (만원/월)"),
            color=alt.Color("유형:N"),
            tooltip=[
                "매물명",
                "지역",
                "유형",
                alt.Tooltip("보증금(만원):Q", format=",.0f"),
                alt.Tooltip("월 현금지출(만원):Q", format=",.1f"),
                alt.Tooltip("월 환산 총비용(만원):Q", format=",.2f"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(scatter, use_container_width=True)

with col_b:
    adjust = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("시장평균 대비 조정액(만원):Q", title="시장평균 대비 월세 조정액 (만원)"),
            y=alt.Y("매물명:N", sort="-x", title="매물"),
            color=alt.condition(
                alt.datum["시장평균 대비 조정액(만원)"] < 0,
                alt.value("#d95f02"),
                alt.value("#1b9e77"),
            ),
            tooltip=[
                "매물명",
                alt.Tooltip("월세(만원):Q", format=",.1f"),
                alt.Tooltip("시장평균 기준 적정 월세(만원):Q", format=",.1f"),
                alt.Tooltip("시장평균 대비 조정액(만원):Q", format=",.1f"),
            ],
        )
        .properties(height=360)
    )
    st.altair_chart(adjust, use_container_width=True)


st.subheader("4. 상세 비교표")

display_cols = [
    "순위",
    "매물명",
    "지역",
    "유형",
    "보증금(만원)",
    "월세(만원)",
    "관리비(만원)",
    "월 현금지출(만원)",
    "보증금 기회비용(만원/월)",
    "보증금 대출이자(만원/월)",
    "월 환산 총비용(만원)",
    "예상 총비용(만원)",
    "시장평균 기준 적정 월세(만원)",
    "시장평균 대비 조정액(만원)",
    "최저비용 기준 적정 월세(만원)",
    "최저비용 대비 조정액(만원)",
    "메모",
]

existing_cols = [c for c in display_cols if c in analyzed.columns]

st.dataframe(
    analyzed[existing_cols].style.format({
        "보증금(만원)": "{:,.0f}",
        "월세(만원)": "{:,.1f}",
        "관리비(만원)": "{:,.1f}",
        "월 현금지출(만원)": "{:,.1f}",
        "보증금 기회비용(만원/월)": "{:,.2f}",
        "보증금 대출이자(만원/월)": "{:,.2f}",
        "월 환산 총비용(만원)": "{:,.2f}",
        "예상 총비용(만원)": "{:,.0f}",
        "시장평균 기준 적정 월세(만원)": "{:,.1f}",
        "시장평균 대비 조정액(만원)": "{:+,.1f}",
        "최저비용 기준 적정 월세(만원)": "{:,.1f}",
        "최저비용 대비 조정액(만원)": "{:+,.1f}",
    }),
    use_container_width=True,
)

st.download_button(
    label="분석 결과 CSV 다운로드",
    data=to_csv_download(analyzed[existing_cols]),
    file_name="rent_fair_value_analysis.csv",
    mime="text/csv",
)


with st.expander("계산 방식 보기"):
    st.markdown(
        """
### 핵심 공식

**월 환산 총비용 = 월세 + 관리비 + 보증금 기회비용 + 보증금 대출이자**

- **보증금 기회비용**: 보증금을 투자했다면 벌 수 있었던 월 수익
- **보증금 대출이자**: 보증금 중 대출로 조달한 금액에 대한 월 이자
- **시장평균 기준 적정 월세**: 해당 매물의 보증금과 관리비를 유지한다고 할 때, 월 환산비용이 전체 평균과 같아지는 월세
- **최저비용 기준 적정 월세**: 해당 매물이 가장 싼 매물과 같은 경제성이 되려면 필요한 월세

### 조정액 해석

- 조정액이 **음수**이면 현재 월세가 비싼 편입니다. 그만큼 내려가야 기준에 맞습니다.
- 조정액이 **양수**이면 현재 월세가 싼 편입니다. 그만큼 올라가도 기준과 같습니다.
        """
    )
