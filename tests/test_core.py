from pathlib import Path

import pandas as pd
import pytest

from expense_ai import analytics as an
from expense_ai.ai_assistant import build_context
from expense_ai.categorizer import categorize, rule_category
from expense_ai.data_loader import clean_merchant, normalize

SAMPLE = Path(__file__).parents[1] / "data" / "sample_transactions.csv"


@pytest.fixture(scope="module")
def df():
    return categorize(normalize(pd.read_csv(SAMPLE)))


# ---------- data loading ----------
def test_normalize_single_amount_column():
    raw = pd.DataFrame({"Date": ["2026-01-02"], "Description": ["Coffee"], "Amount": ["-$4.50"]})
    out = normalize(raw)
    assert out.loc[0, "amount"] == -4.50


def test_normalize_debit_credit_columns():
    raw = pd.DataFrame(
        {
            "Transaction Date": ["2026-01-02", "2026-01-03"],
            "Details": ["Salary", "Groceries"],
            "Debit": ["", "1,200.00"],
            "Credit": ["3,000.00", ""],
        }
    )
    out = normalize(raw)
    assert out["amount"].tolist() == [3000.0, -1200.0]


def test_parentheses_are_negative():
    raw = pd.DataFrame({"date": ["2026-01-02"], "memo": ["Fee"], "amount": ["(35.00)"]})
    assert normalize(raw).loc[0, "amount"] == -35.0


def test_missing_columns_raises():
    with pytest.raises(ValueError):
        normalize(pd.DataFrame({"foo": [1], "bar": [2]}))


def test_clean_merchant():
    assert clean_merchant("WHOLE FOODS MKT #10234") == "Whole Foods Mkt"
    assert clean_merchant("SQ *BLUE BOTTLE COFFEE") == "Blue Bottle Coffee"
    assert clean_merchant("TRADER JOE'S #552") == "Trader Joe's"


# ---------- categorization ----------
@pytest.mark.parametrize(
    "desc, amount, expected",
    [
        ("NETFLIX.COM", -15.49, "Subscriptions"),
        ("UBER EATS *SUSHI", -30, "Dining"),
        ("UBER *TRIP", -12, "Transport"),
        ("PAYROLL ACME CORP", 3900, "Income"),
        ("AMAZON REFUND", -20, "Shopping"),  # 'refund' with money out isn't income
        ("STARBUCKS COFFEE", -5, "Dining"),  # 'coffee' must not match 'fee'
        ("MYSTERY SHOP 42", -10, "Other"),
    ],
)
def test_rule_category(desc, amount, expected):
    assert rule_category(desc, amount) == expected


# ---------- analytics ----------
def test_summary_math(df):
    s = an.summary(df)
    assert s.net == pytest.approx(s.income - s.spend)
    assert 0 < s.savings_rate < 1
    assert s.months == 6


def test_transfers_not_counted_as_spending(df):
    assert "Transfers" not in an.spending(df)["category"].unique()


def test_recurring_finds_subscriptions(df):
    merchants = an.recurring(df)["merchant"].tolist()
    assert "Netflix.com" in merchants
    assert "Starbucks Store" not in merchants  # frequent but irregular


def test_anomaly_flags_laptop(df):
    anomalies = an.anomalies(df)
    assert "Best Buy Laptop" in anomalies["merchant"].tolist()


def test_insights_are_generated(df):
    assert len(an.insights(df)) >= 3


def test_ai_context_has_no_raw_descriptions(df):
    ctx = build_context(df)
    assert "#10234" not in ctx  # raw reference numbers never leave the app
    assert "Spending by category" in ctx


# ---------- AI layer (mocked — no API key or network needed) ----------
class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create for tests."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Resp", (), {"content": [_Block(self.reply)]})()


def test_ai_categorize_fills_other(df):
    from expense_ai.categorizer import ai_categorize

    unknown = df.loc[df["category"] == "Other", "description"].unique()
    reply = "{" + ", ".join(f'"{d}": "Dining"' for d in unknown) + "}"
    out = ai_categorize(df, FakeClient(reply), "test-model")
    assert (out["category"] == "Other").sum() == 0


def test_ai_categorize_ignores_invalid_category(df):
    from expense_ai.categorizer import ai_categorize

    unknown = df.loc[df["category"] == "Other", "description"].unique()
    reply = "{" + ", ".join(f'"{d}": "Crypto Moonshots"' for d in unknown) + "}"
    out = ai_categorize(df, FakeClient(reply), "test-model")
    assert (out["category"] == "Other").sum() == (df["category"] == "Other").sum()


def test_ask_sends_context_and_returns_text(df):
    from expense_ai.ai_assistant import ask

    client = FakeClient("You spent the most on Housing.")
    answer = ask(client, "test-model", build_context(df), [], "Where does my money go?")
    assert "Housing" in answer
    sent = client.calls[0]["messages"]
    assert sent[-1]["content"] == "Where does my money go?"
    assert "Spending by category" in sent[0]["content"]
