"""Chat with your finances using Claude.

Privacy by design: the model never sees raw transactions or account
numbers. It receives an aggregated summary (totals by month, category and
merchant) which is enough to answer most questions.
"""

from __future__ import annotations

import os

import pandas as pd

from . import analytics as an

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

SYSTEM_PROMPT = """You are a friendly, sharp personal-finance analyst.
You are given an aggregated summary of the user's bank transactions.
Answer the user's question using ONLY this data. Be specific: quote numbers,
months and merchants. Keep answers short (under 200 words), use bullet points
where helpful, and end with one practical, actionable suggestion when relevant.
If the data cannot answer the question, say so plainly.
You are not a licensed financial adviser; avoid investment recommendations."""


def get_client(api_key: str | None = None):
    """Return an Anthropic client, or None if no key is configured."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    import anthropic

    return anthropic.Anthropic(api_key=key)


def build_context(df: pd.DataFrame, currency: str = "$") -> str:
    """Compact, privacy-preserving text summary of the user's finances."""
    s = an.summary(df)
    parts = [
        f"Currency: {currency}",
        f"Period: {df['date'].min().date()} to {df['date'].max().date()} ({s.months} months)",
        f"Total income: {s.income:,.2f} | Total spending: {s.spend:,.2f} | "
        f"Net: {s.net:,.2f} | Savings rate: {s.savings_rate:.1%}",
        "",
        "Monthly totals:",
        an.monthly(df).round(2).to_string(index=False),
        "",
        "Spending by category:",
        an.by_category(df).round(2).to_string(index=False),
        "",
        "Spending by month and category:",
        an.monthly_by_category(df)
        .pivot(index="category", columns="month", values="spend")
        .fillna(0)
        .round(0)
        .to_string(),
        "",
        "Top 15 merchants:",
        an.top_merchants(df, 15).round(2).to_string(index=False),
    ]
    rec = an.recurring(df)
    if not rec.empty:
        parts += ["", "Recurring charges / subscriptions:", rec.to_string(index=False)]
    anom = an.anomalies(df)
    if not anom.empty:
        parts += ["", "Unusually large purchases:", anom.head(10).to_string(index=False)]
    return "\n".join(parts)


def ask(client, model: str, context: str, history: list[dict], question: str) -> str:
    """Send the question (plus chat history) to Claude and return the answer."""
    messages = [
        {"role": "user", "content": f"Here is my financial data:\n\n{context}"},
        {"role": "assistant", "content": "Thanks — I've reviewed your data. What would you like to know?"},
        *history,
        {"role": "user", "content": question},
    ]
    response = client.messages.create(
        model=model,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return "".join(block.text for block in response.content if block.type == "text")
