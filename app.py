"""AI Expense Analyzer — Streamlit app.

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from expense_ai import analytics as an
from expense_ai.ai_assistant import DEFAULT_MODEL, ask, build_context, get_client
from expense_ai.categorizer import CATEGORIES, ai_categorize, categorize
from expense_ai.data_loader import load_csv

SAMPLE = Path(__file__).parent / "data" / "sample_transactions.csv"
PALETTE = px.colors.qualitative.Safe

st.set_page_config(page_title="AI Expense Analyzer", page_icon="💸", layout="wide")


# ---------- helpers ----------
def secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)  # Streamlit Cloud secrets
    except Exception:
        return os.getenv(name)


@st.cache_data(show_spinner=False)
def load(file_bytes: bytes | None) -> pd.DataFrame:
    import io

    source = io.BytesIO(file_bytes) if file_bytes else SAMPLE
    return categorize(load_csv(source))


def money(x: float) -> str:
    return f"{st.session_state.currency}{x:,.0f}"


def esc(text: str) -> str:
    """Escape '$' so Streamlit markdown doesn't render it as LaTeX math."""
    return text.replace("$", r"\$")


def style_fig(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
        hoverlabel=dict(namelength=-1),
    )
    return fig


# ---------- sidebar ----------
with st.sidebar:
    st.title("💸 AI Expense Analyzer")
    st.caption("Upload a bank statement CSV and get instant, AI-powered insights.")

    uploaded = st.file_uploader("Bank statement (CSV)", type="csv")
    st.caption("No file? The app uses a synthetic 6-month sample statement.")

    st.session_state.currency = st.text_input("Currency symbol", value="$", max_chars=4)

    st.divider()
    st.subheader("🤖 AI settings")
    key_input = st.text_input(
        "Anthropic API key",
        type="password",
        placeholder="sk-ant-…",
        help="Optional. Enables AI categorization and chat. Never stored.",
    )
    api_key = key_input or secret("ANTHROPIC_API_KEY")
    model = st.text_input("Model", value=secret("ANTHROPIC_MODEL") or DEFAULT_MODEL)
    client = get_client(api_key)
    st.caption("✅ AI enabled" if client else "AI features are off — analytics still work without a key.")

    st.divider()
    st.caption(
        "🔒 Privacy: your file is processed in memory only. The AI receives aggregated "
        "totals — never raw account numbers."
    )

# ---------- data ----------
file_bytes = uploaded.getvalue() if uploaded else None
data_key = hash(file_bytes) if file_bytes else "sample"
if st.session_state.get("data_key") != data_key:
    try:
        st.session_state.df = load(file_bytes)
    except ValueError as e:
        st.error(f"Couldn't read that CSV: {e}")
        st.stop()
    st.session_state.data_key = data_key
    st.session_state.chat = []

df: pd.DataFrame = st.session_state.df
cur = st.session_state.currency

if df.empty:
    st.warning("No transactions found in this file.")
    st.stop()

# ---------- header ----------
s = an.summary(df)
st.title("Your money, explained")
st.caption(
    f"{s.transactions} transactions · {df['date'].min():%d %b %Y} – {df['date'].max():%d %b %Y}"
    + (" · *sample data*" if not uploaded else "")
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Income", money(s.income))
k2.metric("Spending", money(s.spend))
k3.metric("Net saved", money(s.net), f"{s.savings_rate:.0%} savings rate")
k4.metric("Avg monthly spend", money(s.avg_monthly_spend))

tab_overview, tab_spend, tab_alerts, tab_chat, tab_data = st.tabs(
    ["📊 Overview", "🧾 Spending", "🔔 Subscriptions & alerts", "💬 Ask AI", "🗂️ Transactions"]
)

# ---------- overview ----------
with tab_overview:
    st.subheader("Key insights")
    for note in an.insights(df, cur):
        st.markdown(f"- {esc(note)}")

    c1, c2 = st.columns([3, 2])
    m = an.monthly(df)
    fig = go.Figure()
    fig.add_bar(x=m["month"], y=m["income"], name="Income", marker_color=PALETTE[0])
    fig.add_bar(x=m["month"], y=m["spend"], name="Spending", marker_color=PALETTE[1])
    fig.add_scatter(x=m["month"], y=m["net"], name="Net", mode="lines+markers",
                    line=dict(color=PALETTE[2], width=3))
    fig.update_layout(title="Income vs. spending by month", barmode="group",
                      yaxis_tickprefix=cur)
    c1.plotly_chart(style_fig(fig), width="stretch")

    cats = an.by_category(df)
    pie = px.pie(cats, names="category", values="total", hole=0.55,
                 title="Where the money goes", color_discrete_sequence=PALETTE)
    pie.update_traces(textposition="inside", textinfo="percent")
    pie = style_fig(pie)
    pie.update_layout(legend=dict(orientation="v", y=0.5, yanchor="middle", x=1.02))
    c2.plotly_chart(pie, width="stretch")

# ---------- spending ----------
with tab_spend:
    mbc = an.monthly_by_category(df)
    order = an.by_category(df)["category"].tolist()
    bar = px.bar(mbc, x="month", y="spend", color="category", category_orders={"category": order},
                 title="Spending by category over time", color_discrete_sequence=PALETTE)
    bar.update_layout(yaxis_tickprefix=cur, yaxis_title=None, xaxis_title=None)
    st.plotly_chart(style_fig(bar, 420), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top merchants**")
        tm = an.top_merchants(df, 10)
        st.dataframe(
            tm,
            hide_index=True,
            width="stretch",
            column_config={
                "total": st.column_config.NumberColumn("Total", format=f"{cur}%.0f"),
                "visits": "Visits",
            },
        )
    with c2:
        st.markdown("**Latest month vs. your average**")
        mom = an.month_over_month(df)
        if mom.empty:
            st.info("Need at least two months of data.")
        else:
            st.dataframe(
                mom,
                hide_index=True,
                width="stretch",
                column_config={
                    "latest": st.column_config.NumberColumn("Latest", format=f"{cur}%.0f"),
                    "previous_avg": st.column_config.NumberColumn("Avg before", format=f"{cur}%.0f"),
                    "change": st.column_config.NumberColumn("Change", format=f"{cur}%.0f"),
                    "change_pct": st.column_config.NumberColumn("Change %", format="percent"),
                },
            )

# ---------- alerts ----------
with tab_alerts:
    st.subheader("🔁 Recurring charges")
    rec = an.recurring(df)
    if rec.empty:
        st.info("No recurring charges detected.")
    else:
        st.caption(esc(
            f"{len(rec)} recurring charges · {money(rec['monthly_cost'].sum())}/month · "
            f"**{money(rec['annual_cost'].sum())}/year**. Cancel one you don't use and save the annual amount."
        ))
        st.dataframe(
            rec,
            hide_index=True,
            width="stretch",
            column_config={
                "monthly_cost": st.column_config.NumberColumn("Monthly", format=f"{cur}%.2f"),
                "annual_cost": st.column_config.NumberColumn("Per year", format=f"{cur}%.0f"),
            },
        )

    st.subheader("⚠️ Unusual purchases")
    anom = an.anomalies(df)
    if anom.empty:
        st.success("Nothing unusual — every purchase is in line with your normal patterns.")
    else:
        st.caption("Purchases far above what you normally spend in that category (robust median/MAD test).")
        st.dataframe(
            anom,
            hide_index=True,
            width="stretch",
            column_config={
                "amount": st.column_config.NumberColumn("Amount", format=f"{cur}%.2f"),
                "typical": st.column_config.NumberColumn("Typical", format=f"{cur}%.2f"),
                "times_typical": st.column_config.NumberColumn("× typical", format="%.1f×"),
            },
        )

# ---------- AI chat ----------
with tab_chat:
    st.subheader("Ask anything about your finances")
    if not client:
        st.info(
            "Add an Anthropic API key in the sidebar to chat with your data. "
            "Get one at [console.anthropic.com](https://console.anthropic.com)."
        )
    else:
        suggestions = [
            "Where can I cut $300 a month?",
            "Why was June so expensive?",
            "Which subscriptions should I review?",
            "Am I on track to save 25% of my income?",
        ]
        cols = st.columns(len(suggestions))
        clicked = None
        for col, q in zip(cols, suggestions):
            if col.button(q, width="stretch"):
                clicked = q

        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        question = st.chat_input("e.g. How much did I spend on dining out in August?") or clicked
        if question:
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing…"):
                    try:
                        answer = ask(client, model, build_context(df, cur), st.session_state.chat, question)
                    except Exception as e:  # show API errors nicely
                        answer = f"⚠️ AI request failed: `{e}`"
                st.markdown(answer)
            st.session_state.chat += [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]

# ---------- transactions ----------
with tab_data:
    other = int((df["category"] == "Other").sum())
    c1, c2 = st.columns([3, 1])
    c1.caption(
        f"{other} transactions are uncategorized. Fix any category directly in the table, "
        "or let AI categorize them."
    )
    if c2.button("✨ AI-categorize", disabled=not client or other == 0, width="stretch"):
        with st.spinner("Asking Claude to categorize merchants…"):
            try:
                st.session_state.df = ai_categorize(df, client, model)
                st.rerun()
            except Exception as e:
                st.error(f"AI categorization failed: {e}")

    edited = st.data_editor(
        df[["date", "description", "merchant", "category", "amount"]],
        hide_index=True,
        width="stretch",
        height=480,
        disabled=["date", "description", "amount"],
        column_config={
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "category": st.column_config.SelectboxColumn("Category", options=CATEGORIES),
            "amount": st.column_config.NumberColumn(f"Amount ({cur})", format="%.2f"),
        },
        key="editor",
    )
    if not edited[["merchant", "category"]].equals(df[["merchant", "category"]]):
        st.session_state.df.loc[:, ["merchant", "category"]] = edited[["merchant", "category"]].values
        st.rerun()

    st.download_button(
        "⬇️ Download categorized CSV",
        df.to_csv(index=False).encode(),
        file_name="categorized_transactions.csv",
        mime="text/csv",
    )

st.caption("Built with Python, pandas, Plotly, Streamlit and Claude · Not financial advice.")
