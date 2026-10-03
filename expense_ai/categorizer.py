"""Assign a spending category to every transaction.

Two layers:
1. Fast, free keyword rules (work offline, no API key needed).
2. Optional AI pass: anything the rules can't place ("Other") is sent to
   Claude in one batch, which returns a category for each merchant.
"""

from __future__ import annotations

import json

import pandas as pd

from .data_loader import clean_merchant

CATEGORIES = [
    "Income",
    "Housing",
    "Utilities",
    "Groceries",
    "Dining",
    "Transport",
    "Shopping",
    "Subscriptions",
    "Health",
    "Entertainment",
    "Travel",
    "Education",
    "Fees & Interest",
    "Transfers",
    "Other",
]

# Order matters: the first matching rule wins.
KEYWORD_RULES: dict[str, list[str]] = {
    "Income": ["payroll", "salary", "direct dep", "dividend", "interest paid", "refund", "bonus"],
    "Transfers": ["transfer", "zelle", "venmo", "paypal transfer", "fps", "savings acct"],
    "Housing": [" rent", "mortgage", "landlord", "property mgmt", "hoa"],
    "Utilities": ["electric", "water", "gas co", "utility", "internet", "comcast", "verizon",
                  "at&t", "t-mobile", "pccw", "hkbn", "clp", "towngas", "mobile plan"],
    "Subscriptions": ["netflix", "spotify", "disney+", "youtube premium", "apple.com/bill",
                      "icloud", "chatgpt", "openai", "claude.ai", "anthropic", "adobe",
                      "microsoft 365", "notion", "gym membership", "amazon prime", "patreon"],
    "Groceries": ["grocery", "supermarket", "whole foods", "trader joe", "costco", "safeway",
                  "kroger", "aldi", "wellcome", "parknshop", "market place", "lidl", "tesco"],
    "Dining": ["restaurant", "cafe", "coffee", "starbucks", "mcdonald", "burger", "pizza",
               "sushi", "doordash", "uber eats", "deliveroo", "foodpanda", "grubhub", "bar & grill",
               "bistro", "kitchen", "chipotle", "pret"],
    "Transport": ["uber", "lyft", "taxi", "shell", "chevron", "exxon", "bp ", "fuel", "parking",
                  "metro", "mtr", "octopus", "transit", "toll"],
    "Travel": ["airline", "airways", "cathay", "delta", "united air", "hotel", "airbnb",
               "booking.com", "expedia", "marriott", "hilton"],
    "Health": ["pharmacy", "cvs", "walgreens", "watsons", "clinic", "dental", "doctor",
               "hospital", "medical", "insurance"],
    "Entertainment": ["cinema", "movie", "theater", "concert", "ticketmaster", "steam", "playstation",
                      "xbox", "nintendo"],
    "Education": ["udemy", "coursera", "tuition", "university", "books", "kindle", "masterclass"],
    "Fees & Interest": ["fee", "interest charge", "overdraft", "late charge", " atm "],
    "Shopping": ["amazon", "target", "walmart", "ikea", "uniqlo", "zara", "h&m", "best buy",
                 "apple store", "etsy", "ebay", "shein", "taobao", "hktvmall"],
}


def rule_category(description: str, amount: float) -> str:
    text = f" {description.lower()} "
    for category, keywords in KEYWORD_RULES.items():
        if any(k in text for k in keywords):
            # A "refund" from a shop is income-ish, but only if money came in.
            if category == "Income" and amount < 0:
                continue
            return category
    if amount > 0:
        return "Income"
    return "Other"


def categorize(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'merchant' and 'category' columns using keyword rules."""
    out = df.copy()
    out["merchant"] = out["description"].map(clean_merchant)
    out["category"] = [rule_category(d, a) for d, a in zip(out["description"], out["amount"])]
    out["month"] = out["date"].dt.to_period("M").astype(str)
    return out


def ai_categorize(df: pd.DataFrame, client, model: str, max_merchants: int = 80) -> pd.DataFrame:
    """Ask Claude to categorize merchants the keyword rules left as 'Other'.

    Only merchant names are sent — never amounts, dates or account details.
    """
    unknown = df.loc[df["category"] == "Other", "description"].unique().tolist()[:max_merchants]
    if not unknown:
        return df

    prompt = (
        "You are a personal-finance assistant. Categorize each bank transaction "
        f"description into exactly one of these categories: {', '.join(CATEGORIES)}.\n"
        "Respond with ONLY a JSON object mapping each description to its category.\n\n"
        + "\n".join(f"- {u}" for u in unknown)
    )
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return df
    try:
        mapping = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return df

    out = df.copy()
    mask = out["category"] == "Other"
    out.loc[mask, "category"] = (
        out.loc[mask, "description"]
        .map(lambda d: mapping.get(d, "Other"))
        .where(lambda s: s.isin(CATEGORIES), "Other")
    )
    return out
