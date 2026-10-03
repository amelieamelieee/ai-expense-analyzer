# 💸 AI Expense Analyzer

**Upload a bank statement → get a personal-finance dashboard, subscription audit, anomaly alerts, and an AI analyst you can chat with.**

Built by a finance professional using AI-assisted development ("vibecoding") with Claude. The finance logic is mine; AI helped me turn it into working, tested software.

[![tests](https://github.com/amelieamelieee/ai-expense-analyzer/actions/workflows/tests.yml/badge.svg)](https://github.com/amelieamelieee/ai-expense-analyzer/actions)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B)
![Claude](https://img.shields.io/badge/AI-Claude-D97757)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

> 🔗 **Live demo:** _add your Streamlit Cloud link here_

![Dashboard overview](docs/screenshots/overview.png)

---

## The problem

Most people can't answer three simple questions about their money:

1. **Where does it actually go?**
2. **What am I paying for every month without noticing?**
3. **Was that month unusual — or is this the new normal?**

Bank apps show transactions, not answers. Spreadsheets take hours. This tool answers all three in seconds from a CSV export any bank provides.

## What it does

| Feature | How it works |
|---|---|
| 📥 **Reads any bank CSV** | Auto-detects date / description / amount columns, including separate debit & credit columns, `$1,234.50` and `(45.00)` formats |
| 🏷️ **Auto-categorizes spending** | ~150 keyword rules across 15 categories, then **Claude categorizes the leftovers** in one batched call |
| 📊 **Dashboard** | Income vs. spending, savings rate, category mix, trends over time, top merchants |
| 🔁 **Subscription detector** | Finds charges that repeat every ~30 days at a stable amount and shows the **annual cost** |
| ⚠️ **Anomaly alerts** | Flags purchases far above your normal for that category using a robust median/MAD test |
| 📈 **Month-over-month** | Shows which categories grew vs. your average (e.g. "Dining +57%") |
| 💬 **Ask AI** | Chat with your finances: *"Where can I cut $300 a month?"*, *"Why was June so expensive?"* |
| ✏️ **Human in the loop** | Correct any category in the table; export the clean, categorized CSV |

## Screenshots

| Subscriptions & alerts | Spending trends |
|---|---|
| ![Alerts](docs/screenshots/alerts.png) | ![Spending](docs/screenshots/spending.png) |

## Privacy by design 🔒

Financial data is sensitive, so the app was designed around it:

- Files are processed **in memory only** — nothing is saved to disk or a database.
- The AI **never sees raw transactions or account numbers.** It receives aggregated totals (by month, category, merchant). For categorization, only merchant names are sent.
- The app works **fully offline without an API key** — AI features are optional extras.
- `.gitignore` blocks committing any CSV except the synthetic sample.

## Quick start

```bash
git clone https://github.com/amelieamelieee/ai-expense-analyzer.git
cd ai-expense-analyzer
pip install -r requirements.txt
streamlit run app.py
```

The app opens with a **synthetic 6-month sample statement** so you can explore immediately. To enable AI features, paste an [Anthropic API key](https://console.anthropic.com) in the sidebar (or set `ANTHROPIC_API_KEY` as an environment variable).

### Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```

21 tests cover CSV parsing, categorization edge cases (e.g. "coff**ee**" must not match the "fee" rule), the analytics, and the AI layer (with a mocked client, so no API key is needed). They run automatically on every push via GitHub Actions.

## How it works

```
bank.csv ──► data_loader ──► categorizer ──► analytics ──► Streamlit dashboard
             (any format)    rules + Claude   pandas         │
                                                             └──► ai_assistant ──► Claude
                                                                  (aggregates only)
```

```
ai-expense-analyzer/
├── app.py                      # Streamlit UI
├── expense_ai/
│   ├── data_loader.py          # CSV detection & cleaning
│   ├── categorizer.py          # keyword rules + AI categorization
│   ├── analytics.py            # KPIs, recurring charges, anomalies, insights
│   └── ai_assistant.py         # privacy-preserving context + chat
├── data/
│   ├── generate_sample.py      # creates the synthetic demo statement
│   └── sample_transactions.csv
└── tests/test_core.py
```

### The finance logic, in plain English

- **Savings rate** = (income − spending) ÷ income. Transfers to your own savings account are *not* counted as spending.
- **Recurring charge** = same merchant in 3+ months, ~25–35 days apart, amount within ±15% of its median.
- **Anomaly** = a purchase more than 3 robust standard deviations (median + 3 × 1.4826 × MAD) above the category's typical size *and* at least 2× the typical amount. Median/MAD is used instead of mean/standard deviation because one big purchase would otherwise distort the baseline it's measured against.

## How I built it (AI-assisted development)

I approached this as a finance professional, not a software engineer:

1. **I defined the finance logic** — what counts as spending, how to detect subscriptions, what "unusual" means.
2. **I used Claude as a pair programmer** to translate that logic into Python, structure the project, and write tests.
3. **I reviewed and tested every output** — e.g. making sure a naive "fee" rule can't mislabel every coffee shop as a bank fee.

**What I learned:** AI dramatically lowers the barrier to building, but domain expertise decides whether the output is *right*. Knowing which questions to ask about the numbers was the hard part.

## Roadmap

- [ ] Budgets per category with progress bars
- [ ] Multi-currency support with FX conversion
- [ ] PDF statement parsing
- [ ] Cash-flow forecast for the next 3 months

## Disclaimer

For educational and personal use. Not financial advice. The bundled sample data is entirely synthetic.

## License

MIT — see [LICENSE](LICENSE).
