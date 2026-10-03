"""Financial analytics on categorized transactions.

Everything here is plain pandas — deterministic, testable, no AI needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

NON_SPENDING = {"Income", "Transfers"}


def spending(df: pd.DataFrame) -> pd.DataFrame:
    """Only real spending (money out, excluding transfers between own accounts)."""
    out = df[(df["amount"] < 0) & (~df["category"].isin(NON_SPENDING))].copy()
    out["spend"] = -out["amount"]
    return out


@dataclass
class Summary:
    income: float
    spend: float
    net: float
    savings_rate: float  # 0.25 = 25%
    months: int
    avg_monthly_spend: float
    top_category: str
    transactions: int


def summary(df: pd.DataFrame) -> Summary:
    income = df.loc[df["category"] == "Income", "amount"].clip(lower=0).sum()
    sp = spending(df)
    total_spend = sp["spend"].sum()
    months = max(df["month"].nunique(), 1)
    top = sp.groupby("category")["spend"].sum().idxmax() if not sp.empty else "—"
    return Summary(
        income=float(income),
        spend=float(total_spend),
        net=float(income - total_spend),
        savings_rate=float((income - total_spend) / income) if income > 0 else 0.0,
        months=months,
        avg_monthly_spend=float(total_spend / months),
        top_category=top,
        transactions=len(df),
    )


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    sp = spending(df)
    out = (
        sp.groupby("category")["spend"]
        .agg(total="sum", count="count")
        .sort_values("total", ascending=False)
        .reset_index()
    )
    out["share"] = out["total"] / out["total"].sum() if not out.empty else 0
    return out


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Income, spending and net per month."""
    sp = spending(df).groupby("month")["spend"].sum()
    inc = df[df["category"] == "Income"].groupby("month")["amount"].sum()
    out = pd.DataFrame({"income": inc, "spend": sp}).fillna(0).sort_index()
    out["net"] = out["income"] - out["spend"]
    return out.reset_index().rename(columns={"index": "month"})


def monthly_by_category(df: pd.DataFrame) -> pd.DataFrame:
    sp = spending(df)
    return sp.groupby(["month", "category"])["spend"].sum().reset_index()


def top_merchants(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    sp = spending(df)
    return (
        sp.groupby(["merchant", "category"])["spend"]
        .agg(total="sum", visits="count")
        .sort_values("total", ascending=False)
        .head(n)
        .reset_index()
    )


def recurring(df: pd.DataFrame, tolerance: float = 0.15) -> pd.DataFrame:
    """Detect subscriptions / recurring bills.

    A merchant is 'recurring' if it charged us in 3+ different months,
    roughly every 25–35 days, with amounts within ±15% of the median.
    """
    sp = spending(df)
    rows = []
    for merchant, g in sp.groupby("merchant"):
        if g["month"].nunique() < 3:
            continue
        g = g.sort_values("date")
        median = g["spend"].median()
        steady = (g["spend"] - median).abs() <= tolerance * median
        if steady.mean() < 0.8:
            continue
        gaps = g["date"].diff().dt.days.dropna()
        if gaps.empty or not (25 <= gaps.median() <= 35):
            continue
        rows.append(
            {
                "merchant": merchant,
                "category": g["category"].mode().iat[0],
                "monthly_cost": round(float(median), 2),
                "annual_cost": round(float(median) * 12, 2),
                "charges": len(g),
                "last_charged": g["date"].max().date(),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("annual_cost", ascending=False).reset_index(drop=True) if rows else out


def anomalies(df: pd.DataFrame, multiplier: float = 3.0, min_amount: float = 50) -> pd.DataFrame:
    """Flag unusually large purchases compared with the category's typical size.

    Uses the median and MAD (robust to outliers, unlike mean/std).
    """
    sp = spending(df)
    flagged = []
    for category, g in sp.groupby("category"):
        if len(g) < 4:
            continue
        median = g["spend"].median()
        mad = (g["spend"] - median).abs().median() or median * 0.25
        threshold = median + multiplier * 1.4826 * mad
        hits = g[(g["spend"] > threshold) & (g["spend"] >= min_amount) & (g["spend"] >= 2 * median)]
        for _, r in hits.iterrows():
            flagged.append(
                {
                    "date": r["date"].date(),
                    "merchant": r["merchant"],
                    "category": category,
                    "amount": round(r["spend"], 2),
                    "typical": round(median, 2),
                    "times_typical": round(r["spend"] / median, 1) if median else None,
                }
            )
    out = pd.DataFrame(flagged)
    return out.sort_values("amount", ascending=False).reset_index(drop=True) if flagged else out


def month_over_month(df: pd.DataFrame) -> pd.DataFrame:
    """Category spend in the latest month vs. average of previous months."""
    mbc = monthly_by_category(df)
    months = sorted(mbc["month"].unique())
    if len(months) < 2:
        return pd.DataFrame()
    latest = months[-1]
    pivot = mbc.pivot(index="category", columns="month", values="spend").fillna(0)
    prev_avg = pivot[months[:-1]].mean(axis=1)
    out = pd.DataFrame({"latest": pivot[latest], "previous_avg": prev_avg})
    out["change"] = out["latest"] - out["previous_avg"]
    out["change_pct"] = out["change"] / out["previous_avg"].replace(0, pd.NA)
    return out.sort_values("change", ascending=False).reset_index()


def insights(df: pd.DataFrame, currency: str = "$") -> list[str]:
    """Plain-English observations, generated without any AI call."""
    s = summary(df)
    notes: list[str] = []
    c = currency

    if s.income > 0:
        verdict = "healthy" if s.savings_rate >= 0.2 else "below the common 20% guideline"
        notes.append(f"Your savings rate is **{s.savings_rate:.0%}** — {verdict}.")

    cats = by_category(df)
    if not cats.empty:
        top = cats.iloc[0]
        notes.append(
            f"**{top['category']}** is your biggest expense: {c}{top['total']:,.0f} "
            f"({top['share']:.0%} of spending)."
        )

    rec = recurring(df)
    if not rec.empty:
        notes.append(
            f"You have **{len(rec)} recurring charges** costing about "
            f"{c}{rec['monthly_cost'].sum():,.0f}/month ({c}{rec['annual_cost'].sum():,.0f}/year)."
        )

    mom = month_over_month(df)
    if not mom.empty:
        up = mom.iloc[0]
        if up["change"] > 0 and pd.notna(up["change_pct"]) and up["change_pct"] > 0.25:
            notes.append(
                f"**{up['category']}** spending jumped {up['change_pct']:.0%} last month "
                f"vs. your average ({c}{up['latest']:,.0f} vs {c}{up['previous_avg']:,.0f})."
            )

    an = anomalies(df)
    if not an.empty:
        a = an.iloc[0]
        notes.append(
            f"Unusual purchase: {c}{a['amount']:,.0f} at **{a['merchant']}** on {a['date']} "
            f"(~{a['times_typical']}× your typical {a['category']} spend)."
        )
    return notes
