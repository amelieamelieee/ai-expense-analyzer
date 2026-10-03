"""Generate a realistic, fully synthetic 6-month bank statement.

Run:  python data/generate_sample.py
No real personal data is used anywhere in this project.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 42
START = date(2026, 4, 1)
MONTHS = 6

FIXED_MONTHLY = [  # (day, description, amount)
    (1, "PAYROLL ACME CORP DIRECT DEP", 3900.00),
    (15, "PAYROLL ACME CORP DIRECT DEP", 3900.00),
    (2, "RENT PAYMENT - PARKVIEW PROPERTY MGMT", -2350.00),
    (5, "CITY ELECTRIC UTILITY #44821", None),  # variable
    (8, "COMCAST INTERNET 8772", -79.99),
    (9, "T-MOBILE MOBILE PLAN", -55.00),
    (3, "NETFLIX.COM", -15.49),
    (4, "SPOTIFY USA", -11.99),
    (11, "CLAUDE.AI SUBSCRIPTION", -20.00),
    (12, "ADOBE CREATIVE CLOUD", -22.99),
    (14, "PLANET FITNESS GYM MEMBERSHIP", -24.99),
    (20, "TRANSFER TO SAVINGS ACCT 9921", -1500.00),
]

VARIABLE = {  # description pool, (min, max) amount, visits per month (min, max)
    "Groceries": (["WHOLE FOODS MKT #10234", "TRADER JOE'S #552", "COSTCO WHSE #0481", "SAFEWAY #1290"], (25, 180), (6, 9)),
    "Dining": (["STARBUCKS STORE #22931", "CHIPOTLE 1932", "DOORDASH*THAI BASIL", "UBER EATS *SUSHI ZEN",
                "BLUE DOOR BISTRO", "JOE'S PIZZA", "SQ *BLUE BOTTLE COFFEE"], (6, 85), (10, 16)),
    "Transport": (["UBER *TRIP", "LYFT *RIDE", "SHELL OIL 57442", "CITY PARKING GARAGE", "METRO TRANSIT CARD"], (8, 65), (5, 9)),
    "Shopping": (["AMAZON MKTPLACE PMTS", "TARGET 00012", "UNIQLO USA", "IKEA SEATTLE", "ETSY.COM"], (15, 140), (3, 6)),
    "Health": (["CVS/PHARMACY #0912", "WALGREENS #3341"], (10, 45), (1, 2)),
    "Entertainment": (["AMC CINEMA 14", "STEAM PURCHASE", "TICKETMASTER"], (15, 90), (1, 2)),
    "Uncategorized": (["TST* LITTLE SHEEP HOTPOT", "SQ *FARMERS STAND", "PAYPAL *KOFI", "HAIRCUT STUDIO 9"], (12, 60), (1, 3)),
}

ONE_OFFS = [  # one-time events to make the story interesting
    (date(2026, 6, 18), "DELTA AIR LINES 0062341", -642.80),
    (date(2026, 6, 19), "MARRIOTT HOTEL LISBON", -918.40),
    (date(2026, 6, 22), "RESTAURANTE O PITEU", -96.50),
    (date(2026, 8, 7), "BEST BUY 00041 LAPTOP", -1499.99),
    (date(2026, 5, 10), "COURSERA PYTHON FOR FINANCE", -49.00),
    (date(2026, 9, 3), "IRS TAX REFUND", 812.00),
    (date(2026, 7, 28), "OVERDRAFT FEE", -35.00),
]


def generate() -> pd.DataFrame:
    rng = random.Random(SEED)
    rows = []
    for m in range(MONTHS):
        year = START.year + (START.month - 1 + m) // 12
        month = (START.month - 1 + m) % 12 + 1
        first = date(year, month, 1)
        days_in_month = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - first).days

        for day, desc, amount in FIXED_MONTHLY:
            if amount is None:  # electricity: higher in summer
                amount = -round(rng.uniform(70, 95) + (55 if month in (7, 8) else 0), 2)
            rows.append((date(year, month, day), desc, amount))

        for category, (pool, (lo, hi), (vmin, vmax)) in VARIABLE.items():
            visits = rng.randint(vmin, vmax)
            # lifestyle creep: dining picks up in the final month
            if category == "Dining" and m == MONTHS - 1:
                visits += 7
            for _ in range(visits):
                d = date(year, month, rng.randint(1, days_in_month))
                rows.append((d, rng.choice(pool), -round(rng.uniform(lo, hi), 2)))

    rows += ONE_OFFS
    df = pd.DataFrame(rows, columns=["Date", "Description", "Amount"])
    return df.sort_values("Date").reset_index(drop=True)


if __name__ == "__main__":
    out = Path(__file__).with_name("sample_transactions.csv")
    generate().to_csv(out, index=False)
    print(f"Wrote {out}")
