# 🧠 Universal AI Portfolio Analyzer 

> **Any broker. Any format. Instant insights.**

A production-grade AI-powered portfolio analysis engine that automatically parses holding statements from **any Indian broker**, enriches missing data, fetches live market prices, and delivers a forensic health report — all through a clean Streamlit dashboard.

# Access LINK -: https://aiportfoli.streamlit.app/

---

## ✨ Features

### 🔍 AI Forensic Parser
- Accepts CSV / XLSX from **Zerodha, Groww, HDFC Securities, Angel One, Geojit, IndMoney, NJ Wealth, Kotak Neo, Upstox** and any custom format
- **No column mapping required** — the AI detects headers dynamically, skips junk rows, and standardises the schema automatically
- Handles multi-sheet files, merged cells, and mid-file header rows

### ⚡ Multi-Model AI Fallback
```
Gemini 2.5 Flash → Gemini 2.0 Flash → Claude 3.5 Sonnet → OpenRouter
```
- Automatic key rotation across two Gemini API keys
- Zero downtime — if one model is rate-limited, the next kicks in instantly

### 🧮 Smart Data Derivation
| Missing Field | Derivation |
|---|---|
| `invested_amount` | `quantity × avg_price` |
| `quantity` | `invested_amount ÷ avg_price` |
| `current_value` | `quantity × LTP` (live market data) |

### 🌐 3-Tier ISIN Enrichment
1. **AI Knowledge** — batch lookup from internal training data
2. **SerpAPI (Google Search)** — searches NSE/BSE/Screener.in via real Google results
3. **Screener.in scrape** → **NSE autocomplete API** — free fallback

### 📊 Portfolio Health Dashboard
- **Health Score (0–100)** based on diversification, sector spread, and P&L
- Sector allocation & asset class distribution charts
- P&L distribution waterfall chart per holding
- Live LTP via Financial Modelling Prep (FMP) + Alpha Vantage APIs

### 🤖 AI Forensics Report (Easy Language)
Generates a plain-language portfolio summary in a warm, relatable tone:
> *"Your portfolio is like a thali — it has most of the right items, but the portions need a little balancing."*

Includes:
- Investor personality type
- Strategic verdict
- Concentration risk analysis
- Tactical rebalancing advice (3 actionable steps)
- Grandparent-style health scan analogy

---

## 🚀 Quick Start

### 1. Clone & install
```bash
git clone https://github.com/Ankitdahiya2002/AI-PORTFOLIO-ANALYZE.git
cd AI-PORTFOLIO-ANALYZE
pip install -r requirements.txt
```

### 2. Configure environment
Create a `.env` file in the project root:
```env
API_KEY_1=
OPENROUTER_API_KEY=your_openrouter_key
SERP_API_KEY=your_serpapi_key
FMP_KEY_1=your_fmp_key
ALPHA_VANTAGE_KEY=your_alpha_vantage_key
```

### 3. Run
```bash
streamlit run app.py
```

---

## 🗂️ Project Structure

```
portfolio_analyzer_pipeline/
├── app.py                   # Main Streamlit app + AI forensic parser
├── core/
│   ├── parser.py            # Rule-based CSV/XLSX parser & column mapper
│   └── metrics.py           # Portfolio health score & analytics
├── services/
│   ├── ai_analyzer.py       # Multi-model AI service (Gemini/Claude/OpenRouter)
│   ├── market_data.py       # Live LTP fetching (FMP + Alpha Vantage)
│   └── database.py          # Supabase persistence layer
├── universal_schema.json    # Standard holdings schema definition
├── requirements.txt
└── .gitignore
```

---

## 🔑 API Keys Required

| Service | Purpose | Free Tier |
|---|---|---|
| [Google Gemini](https://aistudio.google.com/) | Primary AI parser & ISIN lookup | ✅ Yes |
| [Anthropic Claude](https://console.anthropic.com/) | AI fallback | ❌ Paid |
| [OpenRouter](https://openrouter.ai/) | Last-resort AI fallback | ✅ Free models |
| [SerpAPI](https://serpapi.com/) | Google Search for ISIN enrichment | ✅ 100 searches/mo |
| [FMP](https://financialmodelingprep.com/) | Live stock prices | ✅ Limited |
| [Alpha Vantage](https://www.alphavantage.co/) | Live stock prices (backup) | ✅ Yes |

> **Note:** The app works with just a Gemini API key. All other keys improve reliability and data quality.

---

## 📸 Screenshots

### Portfolio Dashboard
- Invested Capital, Current Valuation, Unrealised P&L, Health Score
- Universal Audit Matrix with ISIN, Qty, LTP, P&L per holding

### AI Forensics Report
- Investor personality type
- Easy-language summary with Indian analogies
- Sector allocation charts

---

## 🛠️ Supported Brokers

| Broker | Format | Auto-Detected |
|---|---|---|
| Zerodha | CSV (avg cost per unit) | ✅ |
| Groww | CSV/Excel | ✅ |
| HDFC Securities | Excel (multi-section) | ✅ |
| Angel One | CSV | ✅ |
| Geojit | CSV | ✅ |
| IndMoney | Excel | ✅ |
| NJ Wealth | Excel | ✅ |
| Upstox | CSV | ✅ |
| Kotak Neo | CSV/Excel | ✅ |
| Any custom format | CSV/Excel | ✅ (AI fallback) |

---

## 🧱 Tech Stack

- **Frontend**: Streamlit
- **AI Models**: Google Gemini 2.5 Flash, Claude 3.5 Sonnet, OpenRouter
- **Data**: Pandas, NumPy
- **Market Data**: FMP, Alpha Vantage
- **ISIN Search**: SerpAPI (Google), Screener.in, NSE India
- **Storage**: Supabase (optional)
- **Language**: Python 3.10+

---

## 📄 License

MIT License — free to use, modify, and distribute.


## Developed by Ankit Dahiya

## Copyright 
All Rights Reserved@2026

---

<p align="center">Built with ❤️ for Indian retail investors 🇮🇳</p>
