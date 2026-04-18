import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import re
import json
import numpy as np
from dotenv import load_dotenv
from core.parser import universal_smart_parse
from core.metrics import calculate_portfolio_metrics, analyze_portfolio_health
from services.market_data import MarketDataService
from services.ai_analyzer import AIAnalyzerService
from services.database import SupabaseService

load_dotenv(override=True)

# ─────────────────────────────────────────────────────────────────
# PAGE CONFIG & STYLING
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Universal Portfolio Analyzer",
    layout="wide",
    initial_sidebar_state="expanded"
)

def local_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Playfair+Display:ital,wght@0,700;1,700&display=swap');

        :root {
            --bg: #060810;
            --card: rgba(255,255,255,0.025);
            --card-border: rgba(255,255,255,0.07);
            --card-hover: rgba(255,255,255,0.05);
            --sky: #38bdf8;
            --emerald: #10b981;
            --rose: #f43f5e;
            --gold: #fbbf24;
            --muted: #64748b;
            --text: #e2e8f0;
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            font-family: 'Outfit', sans-serif !important;
            background: var(--bg) !important;
            color: var(--text);
        }
        [data-testid="stSidebar"] {
            background: rgba(6,8,16,0.95) !important;
            border-right: 1px solid var(--card-border);
        }
        .block-container { padding-top: 2rem !important; }

        /* Metric cards */
        .kpi-card {
            background: var(--card);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 28px 24px;
            transition: all .25s ease;
            height: 100%;
        }
        .kpi-card:hover { background: var(--card-hover); border-color: var(--sky); transform: translateY(-2px); }
        .kpi-label { font-size: 9px; font-weight: 800; letter-spacing: .25em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
        .kpi-value { font-size: 36px; font-weight: 900; line-height: 1; color: var(--text); }
        .kpi-delta { font-size: 11px; font-weight: 700; margin-top: 6px; }

        /* Gradient text */
        .g-blue { background: linear-gradient(135deg,#38bdf8,#818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .g-gold { background: linear-gradient(135deg,#fbbf24,#f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .g-green { background: linear-gradient(135deg,#10b981,#34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

        /* AI Report card */
        .ai-card {
            background: linear-gradient(135deg, rgba(56,189,248,.06), rgba(129,140,248,.04));
            border-left: 3px solid var(--sky);
            border-radius: 0 20px 20px 0;
            padding: 36px;
            margin: 24px 0;
        }

        /* Streamlit overrides */
        .stButton>button {
            border-radius: 50px !important;
            font-weight: 800 !important;
            text-transform: uppercase !important;
            letter-spacing: .08em !important;
            border: none !important;
            background: linear-gradient(135deg,#38bdf8,#818cf8) !important;
            color: white !important;
            transition: all .25s ease !important;
        }
        .stButton>button:hover { transform: scale(1.02) !important; box-shadow: 0 10px 24px rgba(56,189,248,.25) !important; }

        div[data-testid="stMetric"] {
            background: var(--card);
            border: 1px solid var(--card-border);
            padding: 16px;
            border-radius: 16px;
        }

        .stDataFrame { border-radius: 16px; overflow: hidden; }

        /* Status badge */
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: .1em;
            text-transform: uppercase;
        }
        .badge-green { background: rgba(16,185,129,.15); color: #10b981; }
        .badge-blue  { background: rgba(56,189,248,.15);  color: #38bdf8; }
        .badge-gold  { background: rgba(251,191,36,.12);  color: #fbbf24; }
        .badge-red   { background: rgba(244,63,94,.12);   color: #f43f5e; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def kpi(label, value, delta=None, color=None):
    delta_html = ""
    if delta is not None:
        c = color or ("#10b981" if str(delta).startswith("+") or (isinstance(delta, (int,float)) and delta >= 0) else "#f43f5e")
        delta_html = f"<div class='kpi-delta' style='color:{c};'>{delta}</div>"
    st.markdown(f"""
        <div class='kpi-card'>
            <div class='kpi-label'>{label}</div>
            <div class='kpi-value'>{value}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)

def fmt_inr(val):
    val = float(val)
    # Format with standard commas, no abbreviation
    is_negative = val < 0
    val = abs(int(val))
    s = str(val)
    if len(s) > 3:
        s = s[:-3]
        res = "," + str(val)[-3:]
        while len(s) > 2:
            res = "," + s[-2:] + res
            s = s[:-2]
        res = s + res
    else:
        res = s
    return f"₹-{res}" if is_negative else f"₹{res}"

# ─────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:20px;'>
            <div style='background:linear-gradient(135deg,#38bdf8,#818cf8);
                        padding:10px;border-radius:12px;font-size:20px;'>📊</div>
            <div>
                <div style='font-weight:900;font-size:17px;letter-spacing:-.02em;'>
                    UNIVERSAL<span class='g-blue' style='-webkit-text-fill-color:transparent;
                    background:linear-gradient(135deg,#38bdf8,#818cf8);
                    -webkit-background-clip:text;'> ANALYZER</span>
                </div>
                <div style='font-size:9px;font-weight:700;color:#475569;letter-spacing:.3em;'>
                    ANY BROKER · ANY FORMAT
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Load API keys: st.secrets (Streamlit Cloud) → .env (local) ──────
    
    # Fast check to prevent "No secrets files found" terminal spam locally
    import pathlib
    def _has_secrets():
        paths = [
            pathlib.Path.home() / ".streamlit" / "secrets.toml",
            pathlib.Path.cwd() / ".streamlit" / "secrets.toml"
        ]
        return any(p.exists() for p in paths)
        
    _HAS_SECRETS = _has_secrets()

    def _get(key, default=''):
        """Read from st.secrets first (Streamlit Cloud), fallback to os.getenv (.env local)."""
        if _HAS_SECRETS:
            try:
                return st.secrets.get(key, '') or os.getenv(key, default)
            except Exception:
                pass
        return os.getenv(key, default)

    fmp_key      = _get('FMP_KEY_1')   or _get('FMP_KEY_2')
    av_key       = _get('ALPHA_VANTAGE_KEY')
    gemini_key   = _get('GEMINI_API_KEY_1') or _get('GEMINI_API_KEY_2') or _get('GEMINI_API_KEY')
    claude_key   = _get('CLAUDE_API_KEY')
    serpapi_key  = _get('SERP_API_KEY')
    supabase_url = _get('SUPABASE_URL')
    supabase_key = _get('SUPABASE_KEY')

    # Push keys to environment so downstream services can read them
    for _k, _v in {
        'GEMINI_API_KEY_1': gemini_key, 'GEMINI_API_KEY_2': _get('GEMINI_API_KEY_2'),
        'CLAUDE_API_KEY': claude_key, 'SERP_API_KEY': serpapi_key,
        'FMP_KEY_1': fmp_key, 'ALPHA_VANTAGE_KEY': av_key,
        'SUPABASE_URL': supabase_url, 'SUPABASE_KEY': supabase_key,
    }.items():
        if _v:
            os.environ[_k] = _v

    # Automatically default to Claude, fallback handles Gemini transparently
    llm_choice = "Claude"

    st.markdown("---")
    st.caption("📁 UPLOAD PORTFOLIO")
    uploaded_file = st.file_uploader(
        "Drag & drop or click to browse",
        type=['csv', 'xlsx', 'xls'],
        label_visibility="collapsed"
    )


# ─────────────────────────────────────────────────────────────────
# LANDING PAGE
# ─────────────────────────────────────────────────────────────────
if not uploaded_file:
    st.markdown("""
        <div style="text-align: center; padding: 2.5px 20px 60px;">
            <div style="font-size: 64px; margin-bottom: 16px;">📊</div>
            <div class="st-emotion-cache-k7vsyb e1nzilvr2"><h1 level="1" id="analyze-anybroker-portfolio" style="font-size: 72px; font-weight: 900; line-height: 1.05; margin-bottom: 24px;"><div data-testid="StyledLinkIconContainer" class="st-emotion-cache-zt5igj e1nzilvr4"><a href="#analyze-anybroker-portfolio" class="st-emotion-cache-15zrgzn e1nzilvr3"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg></a><span class="st-emotion-cache-10trblm e1nzilvr1">
                Analyze <span style="background: linear-gradient(135deg, rgb(56, 189, 248), rgb(129, 140, 248)) text; -webkit-text-fill-color: transparent;">Any</span><br>Broker Portfolio
            </span></div></h1></div>
            <p style="color: rgb(100, 116, 139); font-size: 18px; max-width: 580px; margin: 0px auto 48px; line-height: 1.6;">
                Universal forensic engine. Supports Zerodha, Groww, HDFC, Kotak, Angel One, 
                Upstox, NJ Wealth, IndMoney, and any custom format — CSV or Excel.
            </p>
        </div>
    """, unsafe_allow_html=True)

    cols = st.columns(4)
    features = [
        ("🔍", "Auto Schema"),
        ("🧹", "Smart Clean"),
        ("🤖", "AI ISIN Resolver"),
        ("📈", "Live Market"),
    ]
    for col, (icon, title) in zip(cols, features):
        col.markdown(f"""
            <div class='kpi-card' style='text-align:center;'>
                <div style='font-size:32px;margin-bottom:12px;'>{icon}</div>
                <div style='font-weight:700;font-size:14px;margin-bottom:6px;'>{title}</div>
            </div>
        """, unsafe_allow_html=True)
    st.stop()

# ─────────────────────────────────────────────────────────────────
# PROCESSING PIPELINE
# ─────────────────────────────────────────────────────────────────
try:
    # ── LOAD FILE ─────────────────────────────────────────────────
    all_dfs = []

    if uploaded_file.name.lower().endswith('.csv'):
        # ── Smart Ragged CSV Loader ──
        # Indian broker CSVs often have 2-column metadata at the top and 20-column data below.
        # This breaks Pandas read_csv (which assumes the first row dictates the column count).
        import csv
        from io import StringIO
        
        uploaded_file.seek(0)
        content_str = uploaded_file.read().decode('utf-8', errors='replace')
        lines = content_str.splitlines()
        
        max_cols = 0
        reader = csv.reader(lines)
        for row in reader:
            if len(row) > max_cols:
                max_cols = len(row)
                
        # Read properly by forcing the maximum width
        raw_io = StringIO(content_str)
        all_dfs.append(pd.read_csv(
            raw_io, header=None, names=range(max_cols), dtype=str, engine='python'
        ))
    else:
        try:
            import xlrd
        except ImportError:
            import subprocess, sys
            # Force precisely the active python interpreter running Streamlit to install the package
            subprocess.check_call([sys.executable, "-m", "pip", "install", "xlrd", "openpyxl"])
            
        xl = pd.ExcelFile(uploaded_file)
        for sheet in xl.sheet_names:
            raw = xl.parse(sheet, header=None, dtype=str)
            if not raw.empty:
                all_dfs.append(raw)

    if not all_dfs:
        st.error("No data found in the uploaded file.")
        st.stop()

    # ── INITIALIZE SERVICES ───────────────────────────────────────
    market_service = MarketDataService(fmp_keys=[fmp_key] if fmp_key else [], av_key=av_key)
    ai_service     = AIAnalyzerService(gemini_key=gemini_key, claude_key=claude_key)
    db_service     = SupabaseService(url=supabase_url, key=supabase_key)

    # ── RULE-BASED PARSE (Steps 1–4) ─────────────────────────────
    processed_dfs = []
    for raw_df in all_dfs:
        if not raw_df.empty:
            df_p = universal_smart_parse(raw_df)
            if not df_p.empty:
                processed_dfs.append(df_p)

    # ── AI FALLBACK (if rule-based fails) ─────────────────────────
    if not processed_dfs and ai_service.is_configured():
        with st.status("🧠 AI Forensic Engine: Direct Parsing...", expanded=True) as status:
            st.write("Rule-based engine couldn't match schema. Engaging AI forensics...")

            # Combine all sheets into one CSV sample for the AI
            all_samples = []
            for i, raw_df in enumerate(all_dfs):
                if raw_df.empty:
                    continue
                sheet_csv = raw_df.head(200).to_csv(index=False, header=True)  # include headers so AI can map columns correctly

                all_samples.append(f"--- Sheet/File {i+1} ---\n{sheet_csv}")
            combined_sample = "\n".join(all_samples)

            prompt = f"""You are a Senior Financial Data Engineer specializing in ETL processes for Indian brokerage holding statements. You have deep knowledge of export formats from Zerodha, Groww, HDFC Securities, Kotak Neo, NJ Wealth, IndMoney, Angel One, Upstox, and similar brokers.

CRITICAL INSTRUCTION: DO NOT WRITE A PYTHON SCRIPT. You are not writing code. You are executing the parsing yourself mentally and outputting the final, extracted JSON array.

Task: Parse the provided file (CSV or Excel) and transform it into a standardized JSON array of objects — one object per individual stock or fund holding.

STEP 1 — Dynamic Header Detection
Do not assume the header is on row 1. Scan from the top downward and identify the first row containing two or more column keywords:
Name, Stock Name, Script Name, Scrip Name, Company Name, Symbol, Instrument, Description, Asset, ISIN, Qty, Quantity, Units, Available Qty, Quantity Available, Avg Price, Average Cost, Average Price, Buy Value, Invested Value, Invested Amount, Total Buying Cost, Value At Cost, Current Value, Closing Value, Valuation, CMP, LTP, NAV, Price, Purchase Amount.
Handle multi-section files by treating mid-file header rows as new tables and merging results.

STEP 2 — Column Mapping
Map detected columns to: stock_name, isin, quantity, invested_amount, current_value, avg_price, sector.

CRITICAL avg_price RULES — READ CAREFULLY:
- avg_price = the per-unit average PURCHASE / COST price paid by the investor.
- Zerodha column names for avg_price: "Avg. cost", "Avg cost", "Average Cost", "Avg Price"
- Groww/Angel column names for avg_price: "Buy Avg", "Avg Buy Price", "Purchase Price"
- NEVER set avg_price to 0 if ANY of these columns exist in the data.
- NEVER use the current market price (CMP/LTP) as avg_price.
- If avg_price cannot be found, use 0.

invested_amount = TOTAL rupees spent to buy the holding.
- If a total invested column exists ("Invested Value", "Total Cost", "Buy Value"), use it directly.
- If NOT (Zerodha/Upstox only give per-unit avg cost), COMPUTE: invested_amount = quantity × avg_price.
- NEVER leave invested_amount as 0 if avg_price > 0.

current_value = TOTAL current market value.
- If a total current value column exists, use it. If NOT, compute: current_value = quantity × CMP/LTP.

sector = Industry/Sector of the company (e.g. "Financial Services", "Industrials", "Healthcare").
- Use your knowledge to populate sector for well-known Indian stocks.
- If unknown, use "Equity".

Priority: Prefer total value columns over per-unit × qty calculations if both exist.

STEP 3 — Row Filtering
Skip rows that are:
- Fully empty.
- Summary/Total rows (contain "Total", "Grand Total", etc.).
- Section labels (text in the first column, but all numeric columns are empty).
- Positions where both quantity and invested_amount are zero.

STEP 4 — Data Cleaning
- stock_name: Strip leading/trailing whitespace. Remove broker-specific exchange suffixes (e.g., - EQ, - BE, - N1) and Face Value patterns (e.g., NEW FV RS.2/-). Do NOT remove "LTD" or "LIMITED".
- isin: Strip whitespace.
- Numeric fields: Remove currency symbols (₹, $), commas, and %. Cast quantity to Integer, and amounts to Float (rounded to 2 decimal places). Preserve negative signs.

STEP 5 — ISIN Enrichment (Search)
If the isin key is missing or empty after parsing the file:
- Use your internal knowledge to find the 12-digit Indian ISIN (starting with 'IN') for each holding.
- Prioritize results from official sources like NSE, BSE, NSDL, or Screener.in.
- Populate the isin field with the found value.

STEP 6 — Missing Data & Multi-Sheet Handling
- If after the search step an ISIN still cannot be found, set isin to an empty string "".
- Process all relevant sections in the data (Equity, Mutual Funds, Holdings). Skip summary/dashboard sections to avoid duplicates.

STEP 7 — Output Format
CRITICAL: DO NOT WRITE PYTHON CODE. RETURN EXCLUSIVELY RAW JSON.
CRITICAL: DO NOT BE LAZY. DO NOT TRUNCATE. You must extract EVERY SINGLE HOLDING present in the input text. If the input has 25 holdings, your JSON array MUST have 25 objects!
Return ONLY a valid JSON array starting with `[` and ending with `]`. No explanation text, no markdown code fences.
Key order per object: stock_name, isin, quantity, invested_amount, current_value, avg_price, sector
- avg_price: MUST be the broker's avg cost per unit. NEVER 0 if the file has an avg cost column.
- invested_amount: qty × avg_price if no total invested column. NEVER 0 if avg_price > 0.
- current_value: TOTAL current market value (qty × LTP if no total column).
- sector: Use your knowledge for common Indian stocks (e.g. BEL→Industrials, HDFC→Financial Services). Default "Equity" if unknown.
- Set any truly unknown numeric field to 0 (never null).

CSV/Excel Data:
{combined_sample}"""

            def _call_gemini(p):
                if not gemini_key: return ""
                import google.generativeai as genai
                gemini_keys = [k for k in [
                    os.getenv("GEMINI_API_KEY_1"),
                    os.getenv("GEMINI_API_KEY_2"),
                    gemini_key,
                ] if k]
                for mn in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]:
                    for key in gemini_keys:
                        try:
                            genai.configure(api_key=key)
                            model = genai.GenerativeModel(mn)
                            resp = model.generate_content(
                                p,
                                generation_config={"max_output_tokens": 8192}
                            )
                            if resp and resp.text:
                                print(f"[Schema AI] Success with {mn} (key ...{key[-6:]})")
                                return resp.text
                        except Exception as e:
                            err = str(e)
                            print(f"[Schema AI] {mn} (key ...{key[-6:]}) failed: {err[:80]}")
                            if any(x in err.lower() for x in ["quota", "rate", "429", "resource"]):
                                continue
                            break
                return ""

            def _call_openrouter(p):
                import requests
                or_key = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENROUTER_API')
                if not or_key: return ""
                try:
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                                         headers={"Authorization": f"Bearer {or_key}"},
                                         json={
                                             "model": "google/gemini-2.0-flash-lite-preview-02-05:free",
                                             "max_tokens": 8192,
                                             "messages": [{"role": "user", "content": p}]
                                         }).json()
                    if 'error' in resp:
                        return ""
                    return resp['choices'][0]['message']['content']
                except Exception:
                    return ""

            try:
                ai_resp = ""

                # ── 1. Gemini (primary — both keys) ───────────────────
                if gemini_key:
                    ai_resp = _call_gemini(prompt)

                # ── 2. Claude (fallback if Gemini returned nothing) ───
                if not ai_resp and claude_key:
                    try:
                        import anthropic
                        client = anthropic.Anthropic(api_key=claude_key)
                        msg = client.messages.create(
                            model="claude-3-5-sonnet-20241022",
                            max_tokens=4096,
                            system="You are a financial data engineer. Return a valid JSON array only. No markdown fences.",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        ai_resp = msg.content[0].text
                        print("[Schema AI] Claude succeeded as fallback.")
                    except Exception as ce:
                        print(f"[Schema AI] Claude also failed ({str(ce)[:80]})")

                # ── 3. OpenRouter (last resort) ───────────────────────
                if not ai_resp and (os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENROUTER_API')):
                    print("[Schema AI] All primary models failed. Falling back to OpenRouter...")
                    ai_resp = _call_openrouter(prompt)

                # ── Parse the JSON array response ─────────────────────
                ai_resp = re.sub(r'```(?:json)?', '', ai_resp).strip('`').strip()

                def _extract_array(text):
                    """Extract JSON array from AI response, repair if truncated."""
                    # 1. Direct parse
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            return parsed
                    except Exception:
                        pass
                    # 2. Find array start
                    start = text.find('[')
                    if start == -1:
                        return None
                    fragment = text[start:]
                    # 3. Repair truncation: close last incomplete object then close array
                    open_b = fragment.count('{') - fragment.count('}')
                    open_q = fragment.count('"') % 2
                    repaired = fragment
                    if open_q:
                        repaired += '"'
                    if open_b > 0:
                        repaired += '}' * open_b
                    if not repaired.rstrip().endswith(']'):
                        repaired = repaired.rstrip().rstrip(',') + ']'
                    try:
                        parsed = json.loads(repaired)
                        if isinstance(parsed, list):
                            return parsed
                    except Exception:
                        pass
                    return None

                holdings_array = _extract_array(ai_resp)

                if holdings_array:
                    from core.parser import clean_numeric, clean_stock_name, should_skip_row, detect_asset_type
                    result_data = []
                    for item in holdings_array:
                        if not isinstance(item, dict):
                            continue
                        raw_name = item.get('stock_name', '')
                        qty      = clean_numeric(item.get('quantity', 0))
                        inv      = clean_numeric(item.get('invested_amount', 0))
                        curr     = clean_numeric(item.get('current_value', 0))
                        avg_px   = clean_numeric(item.get('avg_price', 0))
                        sector   = str(item.get('sector', 'Unknown')).strip() or 'Unknown'

                        # ── Derive missing fields from available data ──
                        # Case 1: qty missing but we have inv + avg_price
                        if qty == 0 and inv > 0 and avg_px > 0:
                            qty = round(inv / avg_px, 2)

                        # Case 2: invested_amount missing (Zerodha/Upstox give avg_cost only)
                        if inv == 0 and qty > 0 and avg_px > 0:
                            inv = round(qty * avg_px, 2)

                        # Case 3: current_value missing — use avg_price as placeholder
                        if curr == 0 and qty > 0 and avg_px > 0:
                            curr = round(qty * avg_px, 2)

                        # Log derivation status for debugging
                        if inv == 0 and qty > 0:
                            st.toast(f"⚠️ {raw_name}: avg_price={avg_px}, inv still 0 after derivation", icon="⚠️")

                        if should_skip_row(raw_name, qty, inv):
                            continue
                        name = clean_stock_name(str(raw_name))
                        if not name:
                            continue

                        isin = str(item.get('isin', '')).strip()
                        if isin.lower() in ('none', 'null', 'nan', ''):
                            isin = ''
                        if isin and (len(isin) != 12 or not isin.upper().startswith('IN')):
                            isin = ''

                        result_data.append({
                            'stock_name': name, 'isin': isin,
                            'quantity': max(0, int(round(qty))),
                            'invested_amount': round(inv, 2),
                            'current_value': round(curr, 2),
                            '_avg_price': round(avg_px, 2),
                            'sector': sector,
                        })

                    if result_data:
                        import numpy as np
                        df_p = pd.DataFrame(result_data)
                        # Derive ltp from avg_price if current_value is 0
                        # Market data fetch will overwrite this later with real LTP
                        df_p['_avg_price'] = df_p.get('_avg_price', 0)
                        df_p['symbol']       = df_p['stock_name']
                        df_p['qty']          = df_p['quantity']
                        df_p['invested_val'] = df_p['invested_amount']
                        df_p['current_val']  = df_p['current_value']
                        # If current_value=0 but we have qty+avg_price, set a placeholder
                        mask_no_curr = (df_p['current_val'] == 0) & (df_p['qty'] > 0) & (df_p['_avg_price'] > 0)
                        df_p['ltp'] = (df_p['current_value'] / df_p['quantity'].replace(0, np.nan)).fillna(0).round(2)
                        df_p.loc[mask_no_curr, 'ltp'] = df_p.loc[mask_no_curr, '_avg_price']
                        df_p['pnl']     = (df_p['current_val'] - df_p['invested_val']).round(2)
                        df_p['pnl_pct'] = ((df_p['pnl'] / df_p['invested_val'].replace(0, np.nan)) * 100).fillna(0).round(2)
                        df_p['asset_type'] = df_p['stock_name'].apply(detect_asset_type)
                        # Preserve AI-returned sector — only fill 'Unknown' where missing/empty
                        if 'sector' not in df_p.columns:
                            df_p['sector'] = 'Unknown'
                        else:
                            df_p['sector'] = df_p['sector'].replace('', 'Unknown').fillna('Unknown')

                        # Drop internal helper column
                        df_p.drop(columns=['_avg_price'], errors='ignore', inplace=True)
                        valid_isins = df_p['isin'].str.match(r'^IN[A-Z]{2}[0-9]{10}$')
                        df_p.attrs['isin_coverage'] = f"{valid_isins.sum()}/{len(df_p)}"
                        processed_dfs.append(df_p)
                        status.update(label=f"✅ AI Parsed {len(df_p)} holdings successfully", state="complete")
                    else:
                        status.update(label="⚠️ AI returned data but all rows were filtered.", state="error")
                else:
                    if not ai_resp:
                        fail_reason = "Empty response — all AI APIs unavailable or rate-limited"
                    else:
                        print(f"[Schema AI] Could not extract JSON array. Full response:\n{ai_resp[:500]}")
                        fail_reason = "AI response was not a valid JSON array. Check terminal."
                    status.update(label=f"⚠️ {fail_reason}", state="error")

            except Exception as e:
                status.update(label=f"❌ AI Decoding Failed: {e}", state="error")




    # ── GUARD: Nothing parsed ─────────────────────────────────────
    if not processed_dfs:
        st.error("⚠️ Forensic Engine could not decode the schema. Here's what was detected:")
        for i, df in enumerate(all_dfs):
            with st.expander(f"Sheet/File {i+1} — first 10 rows"):
                st.dataframe(df.head(10))
        st.info("""
            **Tips to resolve:**
            - Ensure the file has clear column headers like `Script Name`, `ISIN`, `Quantity`, `Valuation`
            - Add a valid `GEMINI_API_KEY` or `CLAUDE_API_KEY` to `.env` for AI-powered decoding
        """)
        st.stop()

    # ── MERGE ─────────────────────────────────────────────────────
    processed_df = (
        pd.concat(processed_dfs, ignore_index=True)
        .drop_duplicates(subset=['stock_name', 'quantity'])
        .reset_index(drop=True)
    )
    processed_df = processed_df[processed_df['stock_name'].str.strip() != '']

    # ── STEP 5: ISIN & SECTOR ENRICHMENT (SUPABASE + AI) ───────────
    missing_isin_mask = processed_df['isin'].str.len() < 5
    if missing_isin_mask.any():
        stocks = processed_df.loc[missing_isin_mask, 'stock_name'].unique().tolist()
        
        # 1. Supabase Fast Lookup
        if db_service.is_configured():
            with st.status("🗄️ Querying Global Database...", expanded=False) as status:
                cached_data = db_service.resolve_instruments(stocks)
                
                # ------ DEBUG OUTPUT TO SCREEN ------
                st.write("🔍 **Debug — Stocks Sent to Database:**", stocks)
                st.write("🔍 **Debug — Database Response:**", cached_data)
                if not cached_data:
                    st.warning("⚠️ The Supabase table `isin` returned ZERO matches for these stocks. Double check if the `nseTicker` or `name` columns contain exact matches in your database, or if the table is empty!")
                # ------------------------------------

                for name, data in cached_data.items():
                    mask = processed_df['stock_name'] == name
                    if data.get("isin"):
                        processed_df.loc[mask, 'isin'] = data["isin"]
                    if data.get("sector") and data["sector"] != 'Unknown':
                        processed_df.loc[mask, 'sector'] = data["sector"]
                    if data.get("ticker"):
                        processed_df.loc[mask, '_ticker_hint'] = data["ticker"]
                status.update(label=f"✅ {len(cached_data)} Instruments found in Database", state="complete")

        # 2. AI Fallback for Remaining
        missing_isin_mask = processed_df['isin'].str.len() < 5
        if missing_isin_mask.any() and ai_service.is_configured():
            with st.status("🔍 Resolving Missing ISINs via AI...", expanded=False) as status:
                remaining_stocks = processed_df.loc[missing_isin_mask, 'stock_name'].unique().tolist()
                isin_map = ai_service.lookup_isins(remaining_stocks, model_choice=llm_choice)
                for name, isin in isin_map.items():
                    processed_df.loc[processed_df['stock_name'] == name, 'isin'] = isin
                status.update(label=f"✅ {len(isin_map)} ISINs Resolved via AI", state="complete")

    # ── MARKET DATA ENRICHMENT ─────────────────────────────────────
    with st.status("📡 Analysing Portfolio", expanded=False) as status:
        try:
            processed_df = market_service.enrich_portfolio(processed_df)
            status.update(label="✅ Live Prices Loaded", state="complete")
        except Exception as e:
            status.update(label=f"⚠️ Market data partial: {e}", state="error")

    # ── METRICS ───────────────────────────────────────────────────
    stats = calculate_portfolio_metrics(processed_df)
    health = analyze_portfolio_health(stats)

    # ── SAVE TO DB ────────────────────────────────────────────────
    portfolio_record = None
    if db_service.is_configured():
        try:
            portfolio_record = db_service.save_portfolio(uploaded_file.name, stats, health)
            if portfolio_record:
                db_service.save_holdings(portfolio_record["id"], processed_df)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # DASHBOARD LAYOUT
    # ─────────────────────────────────────────────────────────────

    # Header
    pnl_color = "#10b981" if stats['total_pnl'] >= 0 else "#f43f5e"
    st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;flex-wrap:wrap;gap:12px;'>
            <div>
                <div style='font-size:11px;font-weight:800;letter-spacing:.25em;color:#475569;text-transform:uppercase;'>
                    📊 Portfolio Forensic Snapshot
                </div>
                <h1 style='font-size:40px;font-weight:900;margin:4px 0 0;'>
                    {uploaded_file.name.replace("_"," ").replace(".csv","").replace(".xlsx","").title()}
                </h1>
            </div>
            <div style='display:flex;gap:8px;'>
                <span class='badge badge-{'green' if health >= 70 else 'gold' if health >= 50 else 'red'}'>
                    Health: {health}/100
                </span>
                <span class='badge badge-blue'>{len(processed_df)} Holdings</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # KPI Row
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Invested Capital", fmt_inr(stats['total_invested']))
    with c2: kpi("Current Valuation", fmt_inr(stats['total_current']))
    with c3:
        sign = "+" if stats['total_pnl'] >= 0 else ""
        kpi("Unrealised P&L", fmt_inr(stats['total_pnl']),
            delta=f"{sign}{stats['total_pnl_pct']:.2f}%",
            color=pnl_color)
    with c4:
        kpi("Holdings", str(len(processed_df)),
            delta=f"{processed_df['asset_type'].value_counts().index[0]} dominant")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # ── TABS LAYOUT ───────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📊 Matrix & Stats", "📈 Visuals", "🧠 AI Forensics"])

    # ─────────────────────────────────────────────────────────────
    # TAB 1: MATRIX & EXPORT
    # ─────────────────────────────────────────────────────────────
    with tab1:
        st.markdown("<br><div class='kpi-label'>📋 Universal Audit Matrix</div>", unsafe_allow_html=True)
        display_cols = ['stock_name', 'isin', 'quantity', 'ltp', 'invested_amount',
                        'current_value', 'pnl', 'pnl_pct', 'asset_type', 'sector']
        available_cols = [c for c in display_cols if c in processed_df.columns]
        styled = processed_df[available_cols].rename(columns={
            'stock_name': 'Stock', 'isin': 'ISIN', 'quantity': 'Qty',
            'ltp': 'LTP (₹)', 'invested_amount': 'Invested (₹)',
            'current_value': 'Market Value (₹)', 'pnl': 'P&L (₹)',
            'pnl_pct': 'P&L %', 'asset_type': 'Asset Type', 'sector': 'Sector'
        })
        st.dataframe(styled, height=400)

        st.markdown("---")
        ecols = ['stock_name', 'isin', 'quantity', 'invested_amount', 'current_value']
        ecols = [c for c in ecols if c in processed_df.columns]
        json_out = processed_df[ecols].to_json(orient='records', indent=2)
        csv_out  = processed_df[available_cols].to_csv(index=False)

        e1, e2 = st.columns(2)
        with e1:
            st.download_button("⬇️ Download Holdings JSON", data=json_out,
                               file_name="portfolio_holdings.json", mime="application/json")
        with e2:
            st.download_button("⬇️ Download Audit CSV", data=csv_out,
                               file_name="portfolio_audit.csv", mime="text/csv")

    # ─────────────────────────────────────────────────────────────
    # TAB 2: VISUALS
    # ─────────────────────────────────────────────────────────────
    with tab2:
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            st.markdown("<div class='kpi-label'>Asset Class Distribution</div>", unsafe_allow_html=True)
            if 'asset_type' in processed_df.columns:
                fig = px.pie(processed_df, values='current_val', names='asset_type', hole=0.65,
                             color_discrete_sequence=['#38bdf8','#818cf8','#10b981','#fbbf24','#f43f5e','#fb923c'])
                fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), showlegend=True,
                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                  font_color='white', legend=dict(font_size=11))
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, key='asset_pie_chart', use_container_width=True)

        with c2:
            st.markdown("<div class='kpi-label'>Sector Allocation</div>", unsafe_allow_html=True)
            known_sectors = processed_df[processed_df['sector'] != 'Unknown']
            if not known_sectors.empty:
                sec = known_sectors.groupby('sector')['current_val'].sum().reset_index()
                fig = px.bar(sec.sort_values('current_val', ascending=True), x='current_val', y='sector',
                             orientation='h', color='current_val',
                             color_continuous_scale='Blues')
                fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),
                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                  font_color='white', coloraxis_showscale=False, yaxis_title='', xaxis_title='₹')
                st.plotly_chart(fig, key='sector_chart', use_container_width=True)
            else:
                st.info("Sector data available after market data fetch.", icon="📡")

        with c3:
            st.markdown("<div class='kpi-label'>Top 10 Holdings by Value</div>", unsafe_allow_html=True)
            top10 = processed_df.nlargest(10, 'current_val')[['stock_name', 'current_val', 'pnl_pct']]
            fig = go.Figure(go.Bar(
                x=top10['current_val'],
                y=top10['stock_name'].str[:20],
                orientation='h',
                marker_color=['#10b981' if p >= 0 else '#f43f5e' for p in top10['pnl_pct']],
                text=[f"{p:+.1f}%" for p in top10['pnl_pct']],
                textposition='outside',
            ))
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              font_color='white', xaxis_title='₹', yaxis_title='',
                              yaxis=dict(autorange='reversed'))
            st.plotly_chart(fig, key='top10_chart', use_container_width=True)

        st.markdown("<div class='kpi-label' style='margin-top:16px;'>P&L Distribution</div>", unsafe_allow_html=True)
        pnl_df = processed_df.nlargest(20, 'pnl').copy()
        pnl_bot = processed_df.nsmallest(10, 'pnl')
        pnl_display = pd.concat([pnl_df, pnl_bot]).drop_duplicates()
        pnl_display = pnl_display.sort_values('pnl', ascending=False)
        fig = px.bar(pnl_display, x='stock_name', y='pnl',
                     color='pnl', color_continuous_scale=['#f43f5e', '#1e293b', '#10b981'],
                     text='pnl_pct')
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='auto')
        fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='white', coloraxis_showscale=False,
                          xaxis_title='', yaxis_title='P&L (₹)',
                          xaxis_tickangle=-35)
        st.plotly_chart(fig, key='pnl_dist_chart', use_container_width=True)

    # ─────────────────────────────────────────────────────────────
    # TAB 3: AI FORENSICS
    # ─────────────────────────────────────────────────────────────
    with tab3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔬 Generate AI Forensic Report", type='primary'):
            with st.spinner("Decoding behavioral signatures and capital allocation patterns..."):
                report = ai_service.generate_portfolio_report(processed_df, stats, model_choice=llm_choice)
                if 'error' not in report:
                    if db_service.is_configured() and portfolio_record:
                        try:
                            # Using 'behavioral_signature' safely with get
                            db_service.save_ai_report(portfolio_record["id"], report, llm_choice)
                        except Exception:
                            pass
                    st.success(f"### {report.get('behavioral_signature', 'Researcher Diagnostic')}")
                    st.info(f"**Verdict:** {report.get('strategic_verdict', 'This is a reliable setup. It balances safety with performance.')}")
                    
                    st.warning(f"**Concentration Risk:** {report.get('concentration_risk', 'Holdings are distributed relatively safely.')}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.error("**Tactical Rebalancing Advice**")
                        for advice in report.get('rebalancing_advice', []):
                            st.write(f"- {advice}")
                    with col2:
                        st.success("**Grandparent's Health Scan**")
                        st.write(report.get('simple_summary', 'Scanning...'))
                    
                else:
                    st.error(f"AI Report Failed: {report['error']}")


except Exception as e:
    st.error(f"❌ Error processing portfolio: {e}")
    with st.expander("🔍 Debug Traceback"):
        st.exception(e)
