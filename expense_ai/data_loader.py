"""Load bank-statement CSVs from different banks into one clean format.

Every bank exports CSVs differently. This module detects the date,
description and amount columns automatically and returns a DataFrame with:

    date (datetime) | description (str) | amount (float)

Convention: negative amount = money out (spending), positive = money in.
"""

from __future__ import annotations

import re
from typing import IO

import pandas as pd

DATE_HINTS = ["date", "posted", "transaction date", "booking date", "value date"]
DESC_HINTS = ["description", "merchant", "details", "payee", "narrative", "memo", "name"]
AMOUNT_HINTS = ["amount", "value", "transaction amount"]
DEBIT_HINTS = ["debit", "withdrawal", "money out", "paid out"]
CREDIT_HINTS = ["credit", "deposit", "money in", "paid in"]


def _find_column(columns: list[str], hints: list[str]) -> str | None:
    """Return the first column whose name matches one of the hints."""
    lowered = {c: c.lower().strip() for c in columns}
    # exact match first, then "contains"
    for hint in hints:
        for col, low in lowered.items():
            if low == hint:
                return col
    for hint in hints:
        for col, low in lowered.items():
            if hint in low:
                return col
    return None


def _to_number(series: pd.Series) -> pd.Series:
    """Convert strings like '$1,234.50', '(45.00)' or '-12' into floats."""
    s = series.astype(str).str.strip()
    negative_parens = s.str.match(r"^\(.*\)$")
    s = s.str.replace(r"[^\d.\-]", "", regex=True)
    nums = pd.to_numeric(s, errors="coerce")
    nums[negative_parens] = -nums[negative_parens].abs()
    return nums


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Turn any reasonable bank export into the standard 3-column format."""
    cols = list(df.columns)
    date_col = _find_column(cols, DATE_HINTS)
    desc_col = _find_column(cols, DESC_HINTS)
    amount_col = _find_column(cols, AMOUNT_HINTS)
    debit_col = _find_column(cols, DEBIT_HINTS)
    credit_col = _find_column(cols, CREDIT_HINTS)

    if date_col is None or desc_col is None:
        raise ValueError(
            "Could not find a date and description column. "
            f"Columns found: {cols}"
        )

    if amount_col is not None and amount_col not in (debit_col, credit_col):
        amount = _to_number(df[amount_col])
    elif debit_col is not None or credit_col is not None:
        debit = _to_number(df[debit_col]).fillna(0).abs() if debit_col else 0
        credit = _to_number(df[credit_col]).fillna(0).abs() if credit_col else 0
        amount = credit - debit
    else:
        raise ValueError(
            "Could not find an amount column (or debit/credit columns). "
            f"Columns found: {cols}"
        )

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce"),
            "description": df[desc_col].astype(str).str.strip(),
            "amount": amount,
        }
    )
    out = out.dropna(subset=["date", "amount"])
    out = out[out["description"] != ""]
    return out.sort_values("date").reset_index(drop=True)


def load_csv(file: str | IO) -> pd.DataFrame:
    """Read a CSV file (path or uploaded file object) and normalize it."""
    return normalize(pd.read_csv(file))


def clean_merchant(description: str) -> str:
    """Make a readable merchant name from a raw bank description.

    'AMAZON MKTPLACE PMTS #8392 SEATTLE WA' -> 'Amazon Mktplace Pmts'
    """
    text = re.sub(r"^(SQ|TST|SP|PP)\s*\*\s*", "", description.strip(), flags=re.I)  # card-terminal prefixes
    text = re.sub(r"#\s*\w*\d\w*", " ", text)  # reference numbers like #10234
    text = text.replace("*", " ").replace(" - ", " ")
    text = re.sub(r"\b\d[\d\-/]*\b", " ", text)  # stray numbers / dates
    text = re.sub(r"\b[A-Z]{2}\b$", " ", text.strip())  # trailing state codes
    text = re.sub(r"\s+", " ", text).strip(" -*")
    words = [w for w in text.split() if w.strip("-")][:3]
    words = words or description.split()[:3]
    return " ".join(w[:1].upper() + w[1:].lower() for w in words)
