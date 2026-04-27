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


# ─────────────────────────────────────────────
# 핵심 계산 함수
# ─────────────────────────────────────────────

def calc_monthly_cost(
    deposit_manwon: float,
    rent_manwon: float,
    maintenance_manwon: float,
    annual_invest_return: float,
    loan_ratio: float,
    annual_loan_rate: float,
) -> dict:
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
    if deposit_manwon >= 8000 and rent_manwon <= 20:
        return "전세형"
    if deposit_manwon >= 3000 and rent_manwon <= 60:
        return "반전세형"
    return "월세형"


# ─────────────────────────────────────────────
# [NEW] 깡통전세 위험도 계산
# ─────────────────────────────────────────────

def calc_jeonse_risk(deposit_manwon: float, estimated_price_manwon: float) -> dict:
    """
    보증금이 추정 시세 대비 몇 %인지 계산.
    70% 이상이면 위험, 50~70%는 주의, 50% 미만은 안전.
    estimated_price_manwon=0 이면 시세 미입력으로 처리.
    """
    if estimated_price_manwon <= 0:
        return {"깡통전세 비율(%)": None, "위험등급": "미입력"}

    ratio = (deposit_manwon / estimated_price_manwon) * 100

    if ratio >= 70:
        grade = "🔴 위험"
    elif ratio >= 50:
        grade = "🟡 주의"
    else:
        grade = "🟢 안전"

    return {"깡통전세 비율(%)": ratio, "위험등급": grade}


# ─────────────────────────────────────────────
# [NEW] 손익분기 계산
# ─────────────────────────────────────────────

def calc_breakeven_months(
    deposit_a: float, rent_a: float, maintenance_a: float,
    deposit_b: float, rent_b: float, maintenance_b: float,
    annual_invest_return: float,
    loan_ratio: float,
    annual_loan_rate: float,
    max_months: int = 120,
) -> int | None:
    """
    매물 A와 B의 누적 총비용이 역전되는 월(손익분기)을 반환.
    역전이 없으면 None.
    """
    monthly_invest_rate = (1 + annual_invest_return) ** (1 / 12) - 1
    monthly_loan_rate = annual_loan_rate / 12

    def monthly_total(deposit, rent, maint):
        opp = deposit * monthly_invest_rate
        loan = deposit * loan_ratio * monthly_loan_rate
        return rent + maint + opp + loan

    total_a = monthly_total(deposit_a, rent_a, maintenance_a)
    total_b = monthly_total(deposit_b, rent_b, maintenance_b)

    if total_a == total_b:
        return 0

    # A가 더 비싸면 역전은 발생하지 않음 (월비용 기준 고정비이므로)
    # 손익분기는 초기 보증금 차이를 월비용 차이로 회수하는 시점
    deposit_diff = deposit_a - deposit_b   # A가 보증금 더 많이 냄
    monthly_saving = total_b - total_a     # A가 매달 절약하는 금액

    if monthly_saving <= 0:
        return None  # A가 보증금도 많고 월비용도 많으면 의미없음

    breakeven = deposit_diff / monthly_saving
    if 0 < breakeven <= max_months:
        return round(breakeven)
    return None


# ─────────────────────────────────────────────
# [NEW] 체크리스트 점수 계산
# ─────────────────────────────────────────────

CHECKLIST_ITEMS = {
    "햇빛": ("☀️ 햇빛", "남향·채광 좋음"),
    "소음": ("🔇 소음", "조용한 환경"),
    "지하철": ("🚇 지하철", "역까지 도보 10분 이내"),
    "주차": ("🚗 주차", "주차 가능"),
    "보안": ("🔒 보안", "현관 잠금·CCTV"),
    "냉난방": ("❄️ 냉난방", "에어컨·보일러 정상"),
    "수압": ("🚿 수압", "수압·온수 양호"),
    "창고": ("📦 수납", "수납공간 충분"),
    "인터넷": ("🌐 인터넷", "광랜 가능"),
    "주변편의": ("🏪 편의시설", "편의점·마트 도보권"),
}

MAX_CHECKLIST_SCORE = len(CHECKLIST_ITEMS) * 2  # 각 항목 0·1·2점


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


# ─────────────────────────────────────────────
# 예시 데이터
# ─────────────────────────────────────────────

sample_data = pd.DataFrame(
    [
        {"매물명": "낙성대 A", "지역": "낙성대역", "보증금(만원)": 1000, "월세(만원)": 60, "관리비(만원)": 10, "추정시세(만원)": 30000, "네이버링크": "", "메모": "공개 매물 예시"},
        {"매물명": "낙성대 B", "지역": "낙성대역", "보증금(만원)": 2000, "월세(만원)": 50, "관리비(만원)": 10, "추정시세(만원)": 30000, "네이버링크": "", "메모": "공개 매물 예시"},
        {"매물명": "낙성대 C", "지역": "낙성대역", "보증금(만원)": 2000, "월세(만원)": 75, "관리비(만원)": 0,  "추정시세(만원)": 30000, "네이버링크": "", "메모": "공개 매물 예시"},
        {"매물명": "봉천동 A",  "지역": "봉천동",   "보증금(만원)": 500,  "월세(만원)": 55, "관리비(만원)": 12, "추정시세(만원)": 20000, "네이버링크": "", "메모": "공개 매물 예시"},
        {"매물명": "봉천동 B",  "지역": "봉천동",   "보증금(만원)": 3000, "월세(만원)": 60, "관리비(만원)": 8,  "추정시세(만원)": 20000, "네이버링크": "", "메모": "공개 매물 예시"},
        {"매물명": "봉천동 C",  "지역": "봉천동",   "보증금(만원)": 5000, "월세(만원)": 50, "관리비(만원)": 10, "추정시세(만원)": 20000, "네이버링크": "", "메모": "공개 매물 예시"},
        {"매물명": "서울대입구 A", "지역": "서울대입구역", "보증금(만원)": 1000, "월세(만원)": 70, "관리비(만원)": 0, "추정시세(만원)": 0, "네이버링크": "", "메모": "입력 예시"},
        {"매물명": "서울대입구 B", "지역": "서울대입구역", "보증금(만원)": 800,  "월세(만원)": 52, "관리비(만원)": 8, "추정시세(만원)": 0, "네이버링크": "", "메모": "입력 예시"},
        {"매물명": "전세형 예시",  "지역": "봉천동",   "보증금(만원)": 10000, "월세(만원)": 0, "관리비(만원)": 0, "추정시세(만원)": 15000, "네이버링크": "", "메모": "보증금 높은 매물 예시"},
    ]
)


# ─────────────────────────────────────────────
# 사이드바 — 가정값
# ─────────────────────────────────────────────

st.sidebar.header("⚙️ 가정값")

annual_return_pct = st.sidebar.slider("연 투자수익률 (%)", 0.0, 15.0, 5.0, 0.5)
loan_ratio_pct    = st.sidebar.slider("보증금 중 대출 비율 (%)", 0.0, 100.0, 50.0, 5.0)
loan_rate_pct     = st.sidebar.slider("전월세 보증금 대출금리 (%)", 0.0, 10.0, 4.0, 0.25)
residence_months  = st.sidebar.slider("거주 기간 (개월)", 1, 72, 24, 1)

annual_return = annual_return_pct / 100
loan_ratio    = loan_ratio_pct / 100
loan_rate     = loan_rate_pct / 100


# ─────────────────────────────────────────────
# 섹션 1 — 매물 입력
# ─────────────────────────────────────────────

st.subheader("1. 매물 입력")

input_mode = st.radio(
    "입력 방식",
    ["예시 데이터 사용", "CSV 업로드", "직접 편집"],
    horizontal=True,
)

column_config = {
    "추정시세(만원)": st.column_config.NumberColumn(
        "추정시세(만원)",
        help="네이버 부동산 등에서 확인한 해당 건물의 매매 시세. 깡통전세 위험도 계산에 사용됩니다. 모르면 0.",
        min_value=0,
    ),
    "네이버링크": st.column_config.LinkColumn(
        "네이버 부동산 링크",
        help="네이버 부동산 매물 URL을 붙여넣으세요.",
        display_text="🔗 링크",
    ),
}

if input_mode == "CSV 업로드":
    uploaded = st.file_uploader("CSV 파일 업로드", type=["csv"])
    if uploaded is not None:
        raw_df = pd.read_csv(uploaded)
        # 새 컬럼 없으면 기본값으로 추가
        for col, default in [("추정시세(만원)", 0), ("네이버링크", ""), ("메모", "")]:
            if col not in raw_df.columns:
                raw_df[col] = default
    else:
        st.info("CSV를 업로드하거나 다른 입력 방식을 선택하세요.")
        raw_df = sample_data.copy()
elif input_mode == "직접 편집":
    st.write("아래 표를 직접 수정하거나 행을 추가하세요. 단위는 모두 **만원**입니다.")
    raw_df = st.data_editor(
        sample_data.copy(),
        num_rows="dynamic",
        use_container_width=True,
        column_config=column_config,
        key="listing_editor",
    )
else:
    raw_df = sample_data.copy()
    st.dataframe(raw_df, use_container_width=True, column_config=column_config)


# ─────────────────────────────────────────────
# 분석 실행
# ─────────────────────────────────────────────

analyzed = add_analysis_columns(raw_df, annual_return, loan_ratio, loan_rate)
analyzed["예상 총비용(만원)"] = analyzed["월 환산 총비용(만원)"] * residence_months

# 깡통전세 위험도 붙이기
if "추정시세(만원)" in raw_df.columns:
    analyzed["추정시세(만원)"] = pd.to_numeric(
        raw_df.set_index("매물명").reindex(analyzed["매물명"].values)["추정시세(만원)"].values,
        errors="coerce",
    ).fillna(0)
else:
    analyzed["추정시세(만원)"] = 0

risk_results = analyzed.apply(
    lambda r: calc_jeonse_risk(r["보증금(만원)"], r["추정시세(만원)"]),
    axis=1,
    result_type="expand",
)
analyzed = pd.concat([analyzed, risk_results], axis=1)

# 네이버 링크 붙이기
if "네이버링크" in raw_df.columns:
    analyzed["네이버링크"] = raw_df.set_index("매물명").reindex(analyzed["매물명"].values)["네이버링크"].values
else:
    analyzed["네이버링크"] = ""


# ─────────────────────────────────────────────
# 섹션 2 — 결론 KPI
# ─────────────────────────────────────────────

st.subheader("2. 한눈에 보는 결론")

best = analyzed.iloc[0]
worst = analyzed.iloc[-1]
avg_monthly_cost = analyzed["월 환산 총비용(만원)"].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("가장 경제적인 매물", best["매물명"], f'{best["월 환산 총비용(만원)"]:.1f}만원/월')
col2.metric("평균 월 환산비용", f"{avg_monthly_cost:.1f}만원/월")
col3.metric("최고-최저 차이", f'{worst["월 환산 총비용(만원)"] - best["월 환산 총비용(만원)"]:.1f}만원/월')
col4.metric(f"{residence_months}개월 기준 최저 총비용", f'{best["예상 총비용(만원)"]:.0f}만원')


# ─────────────────────────────────────────────
# [NEW] 섹션 3 — 깡통전세 위험도
# ─────────────────────────────────────────────

st.subheader("3. 깡통전세 위험도")
st.caption("보증금이 추정 시세의 몇 %인지 보여줍니다. 70% 이상이면 경매 시 보증금 미회수 위험이 있습니다.")

risk_df = analyzed[["매물명", "지역", "보증금(만원)", "추정시세(만원)", "깡통전세 비율(%)", "위험등급"]].copy()

# 시세 미입력 매물 구분
entered = risk_df[risk_df["추정시세(만원)"] > 0].copy()
missing = risk_df[risk_df["추정시세(만원)"] <= 0].copy()

if not entered.empty:
    risk_bar = (
        alt.Chart(entered)
        .mark_bar()
        .encode(
            x=alt.X("깡통전세 비율(%):Q", title="보증금 / 추정시세 (%)"),
            y=alt.Y("매물명:N", sort="-x"),
            color=alt.Color(
                "깡통전세 비율(%):Q",
                scale=alt.Scale(domain=[0, 50, 70, 100], range=["#1b9e77", "#d4b84a", "#d95f02", "#cc0000"]),
                legend=None,
            ),
            tooltip=[
                "매물명",
                alt.Tooltip("보증금(만원):Q", format=",.0f"),
                alt.Tooltip("추정시세(만원):Q", format=",.0f"),
                alt.Tooltip("깡통전세 비율(%):Q", format=".1f"),
                "위험등급",
            ],
        )
        .properties(height=max(200, len(entered) * 30))
    )

    # 70% 기준선
    rule = alt.Chart(pd.DataFrame({"x": [70]})).mark_rule(color="#cc0000", strokeDash=[4, 4]).encode(x="x:Q")

    st.altair_chart(risk_bar + rule, use_container_width=True)

if not missing.empty:
    st.info(f"추정시세 미입력 매물 {len(missing)}개: {', '.join(missing['매물명'].tolist())} — '직접 편집' 모드에서 추정시세를 입력하면 위험도를 볼 수 있습니다.")


# ─────────────────────────────────────────────
# 섹션 4 — 기존 시각화
# ─────────────────────────────────────────────

st.subheader("4. 비용 시각화")

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
            "매물명", "지역", "유형",
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
                "매물명", "지역", "유형",
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


# ─────────────────────────────────────────────
# [NEW] 섹션 5 — 손익분기 분석
# ─────────────────────────────────────────────

st.subheader("5. 손익분기 분석")
st.caption("보증금이 높은 매물이 월비용이 낮다면, 몇 개월 살아야 본전인지 계산합니다.")

listing_names = analyzed["매물명"].tolist()

if len(listing_names) >= 2:
    col_be1, col_be2 = st.columns(2)
    with col_be1:
        be_a = st.selectbox("기준 매물 (보증금 높은 쪽)", listing_names, index=0, key="be_a")
    with col_be2:
        default_b = 1 if listing_names[1] != be_a else 0
        be_b = st.selectbox("비교 매물 (보증금 낮은 쪽)", listing_names, index=default_b, key="be_b")

    if be_a != be_b:
        row_a = analyzed[analyzed["매물명"] == be_a].iloc[0]
        row_b = analyzed[analyzed["매물명"] == be_b].iloc[0]

        breakeven = calc_breakeven_months(
            deposit_a=row_a["보증금(만원)"], rent_a=row_a["월세(만원)"], maintenance_a=row_a["관리비(만원)"],
            deposit_b=row_b["보증금(만원)"], rent_b=row_b["월세(만원)"], maintenance_b=row_b["관리비(만원)"],
            annual_invest_return=annual_return,
            loan_ratio=loan_ratio,
            annual_loan_rate=loan_rate,
        )

        monthly_a = row_a["월 환산 총비용(만원)"]
        monthly_b = row_b["월 환산 총비용(만원)"]
        deposit_diff = row_a["보증금(만원)"] - row_b["보증금(만원)"]

        c1, c2, c3 = st.columns(3)
        c1.metric(f"{be_a} 월비용", f"{monthly_a:.1f}만원/월")
        c2.metric(f"{be_b} 월비용", f"{monthly_b:.1f}만원/월")
        c3.metric("보증금 차이", f"{deposit_diff:,.0f}만원")

        if breakeven is not None:
            st.success(
                f"**{be_a}**는 보증금이 {deposit_diff:,.0f}만원 더 많지만 월비용이 {monthly_b - monthly_a:.1f}만원 적습니다. "
                f"**{breakeven}개월({breakeven // 12}년 {breakeven % 12}개월)** 거주하면 총비용 기준으로 {be_a}가 더 유리해집니다."
            )

            # 누적비용 비교 차트
            months_range = list(range(0, min(73, breakeven + 25)))
            be_data = pd.DataFrame({
                "개월": months_range * 2,
                "매물": [be_a] * len(months_range) + [be_b] * len(months_range),
                "누적비용(만원)": (
                    [row_a["보증금(만원)"] * loan_ratio + monthly_a * m for m in months_range]
                    + [row_b["보증금(만원)"] * loan_ratio + monthly_b * m for m in months_range]
                ),
            })

            be_chart = (
                alt.Chart(be_data)
                .mark_line(point=False)
                .encode(
                    x=alt.X("개월:Q", title="거주 기간 (개월)"),
                    y=alt.Y("누적비용(만원):Q", title="누적 총비용 (만원)"),
                    color=alt.Color("매물:N"),
                    tooltip=["매물", "개월", alt.Tooltip("누적비용(만원):Q", format=",.0f")],
                )
                .properties(height=300)
            )

            be_line = (
                alt.Chart(pd.DataFrame({"x": [breakeven]}))
                .mark_rule(color="gray", strokeDash=[4, 4])
                .encode(x="x:Q")
            )

            st.altair_chart(be_chart + be_line, use_container_width=True)

        elif monthly_a >= monthly_b:
            st.warning(
                f"**{be_a}**는 보증금도 더 많고 월비용({monthly_a:.1f}만원)도 **{be_b}**({monthly_b:.1f}만원)보다 높습니다. "
                f"어떤 기간으로 봐도 {be_b}가 유리합니다."
            )
        else:
            st.info("두 매물의 보증금 차이가 없거나 손익분기가 72개월을 초과합니다.")
    else:
        st.info("서로 다른 매물 두 개를 선택하세요.")
else:
    st.info("매물이 2개 이상이어야 손익분기 분석이 가능합니다.")


# ─────────────────────────────────────────────
# [NEW] 섹션 6 — 매물별 체크리스트
# ─────────────────────────────────────────────

st.subheader("6. 매물 체크리스트")
st.caption("경제성 외에 실거주 조건을 항목별로 평가합니다. 0=나쁨 / 1=보통 / 2=좋음")

checklist_listing = st.selectbox("체크리스트 작성할 매물 선택", listing_names, key="cl_listing")

# session_state에 체크리스트 저장
if "checklist" not in st.session_state:
    st.session_state["checklist"] = {}

if checklist_listing not in st.session_state["checklist"]:
    st.session_state["checklist"][checklist_listing] = {k: 1 for k in CHECKLIST_ITEMS}

scores = st.session_state["checklist"][checklist_listing]

cols = st.columns(5)
for i, (key, (emoji_label, desc)) in enumerate(CHECKLIST_ITEMS.items()):
    with cols[i % 5]:
        scores[key] = st.radio(
            f"{emoji_label}",
            options=[0, 1, 2],
            index=scores[key],
            key=f"cl_{checklist_listing}_{key}",
            help=desc,
            horizontal=True,
        )

st.session_state["checklist"][checklist_listing] = scores

total_score = sum(scores.values())
score_pct = total_score / MAX_CHECKLIST_SCORE * 100

col_s1, col_s2 = st.columns([1, 3])
with col_s1:
    st.metric(
        f"{checklist_listing} 실거주 점수",
        f"{total_score} / {MAX_CHECKLIST_SCORE}점",
        f"{score_pct:.0f}%",
    )

# 전체 매물 점수 요약 (작성된 매물만)
if len(st.session_state["checklist"]) > 1:
    summary_data = []
    for name, s in st.session_state["checklist"].items():
        sc = sum(s.values())
        monthly_cost = analyzed.loc[analyzed["매물명"] == name, "월 환산 총비용(만원)"]
        mc = monthly_cost.iloc[0] if not monthly_cost.empty else None
        summary_data.append({"매물명": name, "실거주점수": sc, "월환산총비용(만원)": mc})

    summary_df = pd.DataFrame(summary_data).dropna()
    if not summary_df.empty:
        st.write("**전체 비교 — 경제성 vs 실거주 점수**")
        bubble = (
            alt.Chart(summary_df)
            .mark_circle()
            .encode(
                x=alt.X("월환산총비용(만원):Q", title="월 환산 총비용 (만원/월, 낮을수록 좋음)"),
                y=alt.Y("실거주점수:Q", title="실거주 점수 (높을수록 좋음)"),
                size=alt.value(200),
                color=alt.Color("매물명:N"),
                tooltip=["매물명", alt.Tooltip("월환산총비용(만원):Q", format=",.1f"), "실거주점수"],
            )
            .properties(height=300)
        )
        st.altair_chart(bubble, use_container_width=True)


# ─────────────────────────────────────────────
# 섹션 7 — 상세 비교표
# ─────────────────────────────────────────────

st.subheader("7. 상세 비교표")

display_cols = [
    "순위", "매물명", "지역", "유형",
    "보증금(만원)", "월세(만원)", "관리비(만원)",
    "월 현금지출(만원)", "보증금 기회비용(만원/월)", "보증금 대출이자(만원/월)",
    "월 환산 총비용(만원)", "예상 총비용(만원)",
    "시장평균 기준 적정 월세(만원)", "시장평균 대비 조정액(만원)",
    "최저비용 기준 적정 월세(만원)", "최저비용 대비 조정액(만원)",
    "깡통전세 비율(%)", "위험등급",
    "네이버링크", "메모",
]

existing_cols = [c for c in display_cols if c in analyzed.columns]

st.dataframe(
    analyzed[existing_cols].style.format(
        {
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
            "깡통전세 비율(%)": lambda x: f"{x:.1f}%" if pd.notna(x) else "미입력",
        },
        na_rep="미입력",
    ),
    use_container_width=True,
    column_config={
        "네이버링크": st.column_config.LinkColumn("네이버 부동산", display_text="🔗 링크"),
    },
)

st.download_button(
    label="분석 결과 CSV 다운로드",
    data=to_csv_download(analyzed[existing_cols]),
    file_name="rent_fair_value_analysis.csv",
    mime="text/csv",
)


# ─────────────────────────────────────────────
# 계산 방식 설명
# ─────────────────────────────────────────────

with st.expander("계산 방식 보기"):
    st.markdown(
        """
### 핵심 공식

**월 환산 총비용 = 월세 + 관리비 + 보증금 기회비용 + 보증금 대출이자**

- **보증금 기회비용**: 보증금을 투자했다면 벌 수 있었던 월 수익
- **보증금 대출이자**: 보증금 중 대출로 조달한 금액에 대한 월 이자

### 깡통전세 위험도

- **보증금 / 추정시세** 비율로 계산합니다.
- 🔴 70% 이상: 경매 시 보증금 전액 회수 불가 위험 (선순위 채권 고려 필요)
- 🟡 50~70%: 선순위 채권 규모에 따라 주의 필요
- 🟢 50% 미만: 일반적으로 안전한 수준
- 추정시세는 **네이버 부동산 → 해당 건물 → 시세** 탭에서 확인하세요.

### 손익분기 계산

- **보증금 차이 ÷ 월비용 차이** = 손익분기 개월 수
- 보증금이 높은 매물은 기회비용이 크지만 월세가 낮을 수 있으므로,
  충분히 오래 살면 누적 총비용 기준으로 역전될 수 있습니다.

### 체크리스트 점수

- 0 = 나쁨, 1 = 보통, 2 = 좋음
- 최대 20점 (항목 10개 × 2점)
- 경제성 점수와 함께 보면 실질적인 의사결정에 도움이 됩니다.

### 조정액 해석

- 조정액이 **음수**이면 현재 월세가 비싼 편입니다.
- 조정액이 **양수**이면 현재 월세가 싼 편입니다.
        """
    )