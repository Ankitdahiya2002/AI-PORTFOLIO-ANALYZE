import pandas as pd
import numpy as np
import re
import json

# ─────────────────────────────────────────────────────────────────
# STEP 4 — Data Cleaning Utilities
# ─────────────────────────────────────────────────────────────────

def clean_numeric(val):
    """Safely convert any value to a float. Handles ₹, $, commas, %, parentheses."""
    if pd.isna(val) or str(val).strip() in ['', '-', 'N/A', 'NA', 'nan', 'NaN']:
        return 0.0
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    s = str(val).strip()
    # Remove currency symbols and separators
    s = re.sub(r'[₹$£€,\s%]', '', s)
    # Handle parentheses as negative: (1234) -> -1234
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return round(float(s), 2)
    except (ValueError, TypeError):
        return 0.0

def clean_stock_name(name):
    """
    STEP 4: Cleans a raw stock/fund name per the ETL spec.
    - Strips whitespace
    - Removes exchange suffixes: - EQ, - BE, - N1, etc.
    - Removes face-value patterns: NEW FV RS.2/-, (FV 10), RS. 2/-
    - Preserves LTD, LIMITED
    """
    if not name or pd.isna(name):
        return ""
    name = str(name).strip()
    if not name or name.lower() in ['nan', 'none', '-']:
        return ""
    # Remove exchange suffixes
    name = re.sub(r'\s*-\s*(EQ|BE|N[0-9]|RE|GB|BZ|E1|P1|T1|MF|SM|XT|BL|IL|IV)\s*$', '', name, flags=re.IGNORECASE)
    # Remove Face Value patterns
    name = re.sub(r'\s*NEW\s+FV\s+RS?\.*\s*[0-9/./-]+/?-?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*NEW\s+RE\s*\.?\s*[0-9/./-]+/?-?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\(FV\s*[0-9.]+\/?\-?\)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+RS\.\s*[0-9]+\/?\-?$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+[0-9]+\/-$', '', name)
    return name.strip()

# ─────────────────────────────────────────────────────────────────
# STEP 1 — Dynamic Header Detection
# ─────────────────────────────────────────────────────────────────

# All known column header words from any Indian broker
HEADER_KEYWORDS = {
    # Stock name synonyms
    'name', 'stock name', 'script name', 'scrip name', 'company name',
    'symbol', 'instrument', 'description', 'asset', 'scrip', 'stock',
    'security', 'security name', 'scheme name', 'fund name', 'folio',
    # ISIN
    'isin', 'isin code', 'isin no',
    # Quantity
    'qty', 'quantity', 'units', 'available qty', 'quantity available',
    'no of shares', 'no. of shares', 'shares', 'holdings', 'portfolio holdings',
    'balance units', 'allotted units',
    # Price / Cost
    'avg price', 'average cost', 'average price', 'buy avg rate', 'purchase price',
    'cost price', 'avg cost', 'rate', 'nav',
    # Values
    'buy value', 'invested value', 'invested amount', 'total buying cost',
    'value at cost', 'purchase amount', 'cost value', 'cost',
    'current value', 'closing value', 'valuation', 'market value',
    'present value', 'amount', 'total value',
    # Live price
    'cmp', 'ltp', 'price', 'closing price', 'last price', 'market price',
    # Change
    'change', '% change', 'gain/loss', 'unrealised gain', 'unrealized',
    # Misc
    'sr no', 'sr.no', 'sno', 'sl no', 'no.', 'sector', 'asset type',
    # Additional broker-specific headers (HDFC, IndMoney, NJ Wealth)
    'average cost value', 'avg cost value', 'average cost price',
    'portfolio holdings', 'unrealised p&l', 'unrealized p&l',
    'nav chg', 'nav change', '% chg', '% change',
}

# Strong signals — at least one of these must be present to confirm a header row
STRONG_SIGNALS = {
    'isin', 'qty', 'quantity', 'units', 'cmp', 'ltp', 'nav',
    'invested value', 'invested amount', 'current value', 'valuation',
    'portfolio holdings', 'holdings', 'avg price', 'average price',
    'no of shares', 'shares', 'balance units',
    'average cost value', 'avg cost value',
}

# Meta keywords that indicate a NON-header row (client info sections)
META_EXCLUSIONS = {
    # Client info
    'client name', 'client code', 'client id', 'pan', 'demat acc',
    'account type', 'account no', 'date', 'total valuation',
    # Broker letterhead / company info
    'holdings report', 'portfolio report', 'statement of holdings',
    'nuvama', 'edelweiss', 'zerodha', 'groww', 'hdfc', 'kotak',
    'angel', 'upstox', 'motilal', 'icici', 'sbicap', 'axis',
    'wealth and investment', 'broking limited', 'securities limited',
    # Exchange memberships
    'member: nse', 'member nse', 'nse, bse', 'mcx', 'ncdex',
    'sebi reg', 'sebi registration', 'cin no', 'cin:',
    # Address / contact
    'registered office', 'corporate office', 'address', '8th floor',
    'tel. no', 'tel no', 'email', 'helpdesk', 'phone',
    # Report metadata
    'report', 'statement', 'portfolio as on', 'dear', 'formerly',
    'as on', 'generated on', 'print date',
}

ISIN_RE = re.compile(r'^IN[A-Z]{2}[0-9]{10}$')

def _normalize(text):
    """Lowercase and remove punctuation for keyword matching."""
    return re.sub(r'[^a-z0-9 ]', '', str(text).lower().strip())

def _find_isin_anchor(df_raw):
    """
    Scan the entire DataFrame for the first valid Indian ISIN (IN + 2 letters + 10 digits).
    Returns (first_data_row_idx, isin_col_idx) or (None, None).
    """
    for i in range(min(len(df_raw), 300)):
        try:
            row = df_raw.iloc[i]
        except Exception:
            continue
        for j, val in enumerate(row.values):
            if ISIN_RE.match(str(val).strip().upper()):
                return i, j
    return None, None

def detect_header_row(df_raw):
    """
    STEP 1 — Detect the header row using a two-strategy approach:

    Strategy A (Primary): ISIN-Anchor
      Find the first valid Indian ISIN in the file.
      The header is 1-5 rows ABOVE the first ISIN data row.

    Strategy B (Fallback): Keyword Scan
      Scan top-down for rows with 2+ column keywords including a "strong signal".
    """
    # ── Strategy A: ISIN-Anchor (most reliable) ──────────────────────
    first_data_row, isin_col = _find_isin_anchor(df_raw)
    if first_data_row is not None:
        # Look backward up to 5 rows for the header
        for offset in range(1, 6):
            candidate = first_data_row - offset
            if candidate < 0:
                break
            row = df_raw.iloc[candidate]
            vals = [str(v).strip() for v in row.values
                    if str(v).strip() not in ('', 'nan', 'None', 'none')]
            # A valid header row has at least 2 non-empty text cells
            non_numeric = [v for v in vals if not re.match(r'^[\d.,]+$', v)]
            if len(non_numeric) >= 2:
                return candidate
        # If no good header found above, treat the row just before ISIN as header
        if first_data_row > 0:
            return first_data_row - 1
        return first_data_row  # No header row, data starts at row 0

    # ── Strategy B: Keyword Scan (fallback) ────────────────────────
    max_rows = min(len(df_raw), 200)
    for i in range(max_rows):
        try:
            row = df_raw.iloc[i]
        except Exception:
            continue

        vals = [_normalize(str(v)) for v in row.values
                if str(v).strip() not in ('', 'nan', 'None', 'none')]
        if not vals:
            continue

        row_text = ' | '.join(vals)
        if any(meta in row_text for meta in META_EXCLUSIONS):
            continue

        matched_kw = set()
        has_strong  = False
        for val in vals:
            for kw in HEADER_KEYWORDS:
                if kw == val or (len(kw) > 3 and kw in val):
                    matched_kw.add(kw)
                    if kw in STRONG_SIGNALS:
                        has_strong = True
                    break

        if len(matched_kw) >= 2 and has_strong:
            return i

    return None


# ─────────────────────────────────────────────────────────────────
# STEP 2 — Column Mapping (Aggressive Fuzzy Matching)
# ─────────────────────────────────────────────────────────────────

# Normalized (no spaces/underscores) → standard field name
COLUMN_MAP = {
    # stock_name
    'name': 'stock_name', 'stockname': 'stock_name', 'scriptname': 'stock_name',
    'scripname': 'stock_name', 'companyname': 'stock_name', 'security': 'stock_name',
    'securityname': 'stock_name', 'schemename': 'stock_name', 'fundname': 'stock_name',
    'symbol': 'stock_name', 'instrument': 'stock_name', 'description': 'stock_name',
    'asset': 'stock_name', 'scrip': 'stock_name', 'stock': 'stock_name',
    # isin
    'isin': 'isin', 'isincode': 'isin', 'isinno': 'isin',
    # quantity
    'qty': 'quantity', 'quantity': 'quantity', 'units': 'quantity',
    'availableqty': 'quantity', 'quantityavailable': 'quantity',
    'noofshares': 'quantity', 'shares': 'quantity', 'holdings': 'quantity',
    'portfolioholdings': 'quantity', 'balanceunits': 'quantity',
    'allottedunits': 'quantity', 'currentunits': 'quantity',
    # invested_amount (prefer total over per-unit)
    'investedvalue': 'invested_amount', 'investedamount': 'invested_amount',
    'buyvalue': 'invested_amount', 'totalbuyingcost': 'invested_amount',
    'valueatcost': 'invested_amount', 'purchaseamount': 'invested_amount',
    'costvalue': 'invested_amount', 'totalcost': 'invested_amount',
    'purchasevalue': 'invested_amount', 'bookvalue': 'invested_amount',
    # current_value (prefer total over per-unit)
    'currentvalue': 'current_value', 'closingvalue': 'current_value',
    'valuation': 'current_value', 'marketvalue': 'current_value',
    'presentvalue': 'current_value', 'totalvalue': 'current_value',
    'currentval': 'current_value', 'portfoliovalue': 'current_value',
    # avg_price (per-unit cost, used to derive invested if missing)
    'avgprice': 'avg_price', 'averagecost': 'avg_price',
    'averageprice': 'avg_price', 'buyavgrate': 'avg_price',
    'purchaseprice': 'avg_price', 'costprice': 'avg_price',
    'avgcost': 'avg_price', 'avgbuyprice': 'avg_price',
    'averagecostvalue': 'avg_price', 'avgcostvalue': 'avg_price',
    'averagecostprice': 'avg_price', 'avgcostperunit': 'avg_price',
    # cmp (per-unit live price, used to derive current_value if missing)
    'cmp': 'cmp', 'ltp': 'cmp', 'nav': 'cmp', 'price': 'cmp',
    'closingprice': 'cmp', 'lastprice': 'cmp', 'marketprice': 'cmp',
    'currentprice': 'cmp', 'rate': 'cmp',
    # pnl (optional, for richer output)
    'gainloss': 'pnl', 'unrealisedgain': 'pnl', 'unrealizedgain': 'pnl',
    'profitloss': 'pnl', 'pnl': 'pnl',
}

def _norm_col(col):
    """Remove spaces, underscores, dots, ₹, /, - and lowercase."""
    return re.sub(r'[^a-z0-9]', '', str(col).lower().strip())

def map_columns(df):
    """
    STEP 2 — Map raw column names to standard field names.
    Returns a dict: {standard_name: actual_df_col_name}
    """
    col_map = {}
    for raw_col in df.columns:
        normalized = _norm_col(raw_col)
        std = COLUMN_MAP.get(normalized)
        if std and std not in col_map:
            col_map[std] = raw_col
    return col_map

# ─────────────────────────────────────────────────────────────────
# STEP 3 — Row Filtering
# ─────────────────────────────────────────────────────────────────

SKIP_PATTERNS = re.compile(
    r'^(total|grand total|sub total|subtotal|net total|portfolio total|'
    r'aggregate|summary|overall|consolidated|nil|na|n\.a\.?)$',
    re.IGNORECASE
)

def should_skip_row(name_val, qty, invested):
    """Returns True if a row should be skipped per STEP 3 rules."""
    name_str = str(name_val).strip()
    # Fully empty
    if not name_str or name_str.lower() in ['nan', 'none', '', '-']:
        return True
    # Section label / total rows
    if SKIP_PATTERNS.match(name_str):
        return True
    # Both quantity AND amount are zero after cleaning
    if qty == 0 and invested == 0:
        return True
    return False

# ─────────────────────────────────────────────────────────────────
# Asset Type Detection
# ─────────────────────────────────────────────────────────────────

def detect_asset_type(name):
    s = str(name).upper()
    if any(k in s for k in ['LIQUID', 'GILT', 'BOND', 'DEBT', 'SOV', 'G-SEC', 'T-BILL']): return 'Debt'
    if any(k in s for k in ['GOLD', 'SILVER', 'SGB', 'COMMODITY']): return 'Commodity'
    if any(k in s for k in ['REIT', 'INVIT', 'REAL ESTATE']): return 'Real Estate'
    if any(k in s for k in ['NIFTYBEES', 'BEES', 'ETF', 'INDEX FUND']): return 'ETF'
    if any(k in s for k in ['FUND', 'SCHEME', 'GROWTH', 'IDCW', 'DIRECT', 'REGULAR', 'FOLIO']): return 'Mutual Fund'
    return 'Equity'

# ─────────────────────────────────────────────────────────────────
# MAIN PARSER — universal_smart_parse
# ─────────────────────────────────────────────────────────────────

def universal_smart_parse(df_input):
    """
    Universal ETL Parser for any Indian brokerage holding statement.
    Implements the 7-step forensic pipeline.
    Returns a standardized DataFrame ready for the Institutional Dashboard.
    """
    if df_input.empty:
        return pd.DataFrame()

    # ── STEP 1: Detect Header Row ──────────────────────────────
    header_idx = detect_header_row(df_input)

    if header_idx is not None:
        df = df_input.iloc[header_idx:].copy()
        new_cols = [str(c).strip() for c in df.iloc[0].values]
        df.columns = new_cols
        df = df.iloc[1:].reset_index(drop=True)
    else:
        df = df_input.copy()
        df.columns = [str(c).strip() for c in df.iloc[0].values]
        df = df.iloc[1:].reset_index(drop=True)

    # Drop columns that are entirely empty
    df = df.dropna(axis=1, how='all')
    df = df.loc[:, ~df.columns.duplicated()]

    # ── STEP 2: Map Columns ────────────────────────────────────
    col_map = map_columns(df)

    if 'stock_name' not in col_map:
        return pd.DataFrame()  # Cannot parse without stock name

    # ── STEPS 3-4: Filter & Extract Rows ──────────────────────
    result_data = []

    for _, row in df.iterrows():
        # Skip fully empty rows
        if row.isnull().all():
            continue

        raw_name = row.get(col_map['stock_name'], '')
        qty = clean_numeric(row.get(col_map.get('quantity', '___'), 0)) if 'quantity' in col_map else 0.0

        # Invested Amount derivation (prefer total, fallback to avg_px * qty)
        if 'invested_amount' in col_map:
            inv_amt = clean_numeric(row.get(col_map['invested_amount'], 0))
        elif 'avg_price' in col_map and qty > 0:
            inv_amt = clean_numeric(row.get(col_map['avg_price'], 0)) * qty
        else:
            inv_amt = 0.0

        # Current Value derivation (prefer total, fallback to cmp * qty)
        if 'current_value' in col_map:
            curr_val = clean_numeric(row.get(col_map['current_value'], 0))
        elif 'cmp' in col_map and qty > 0:
            curr_val = clean_numeric(row.get(col_map['cmp'], 0)) * qty
        else:
            curr_val = 0.0

        # STEP 3: Row Filtering
        if should_skip_row(raw_name, qty, inv_amt):
            continue

        # STEP 4: Clean name and ISIN
        name = clean_stock_name(raw_name)
        if not name:
            continue

        isin = ''
        if 'isin' in col_map:
            raw_isin = str(row.get(col_map['isin'], '')).strip()
            if raw_isin.lower() not in ['nan', 'none', '']:
                isin = raw_isin

        # Validate ISIN format (Indian ISINs start with IN and are 12 chars)
        if isin and (len(isin) != 12 or not isin.startswith('IN')):
            isin = ''

        entry = {
            'stock_name': name,
            'isin': isin,
            'quantity': max(0, int(qty)),
            'invested_amount': round(inv_amt, 2),
            'current_value': round(curr_val, 2),
        }
        result_data.append(entry)

    if not result_data:
        return pd.DataFrame()

    res_df = pd.DataFrame(result_data)

    # Add derived columns for the UI
    res_df['symbol'] = res_df['stock_name']
    res_df['qty'] = res_df['quantity']
    res_df['invested_val'] = res_df['invested_amount']
    res_df['current_val'] = res_df['current_value']
    res_df['ltp'] = (res_df['current_value'] / res_df['quantity'].replace(0, np.nan)).fillna(0).round(2)
    res_df['pnl'] = (res_df['current_val'] - res_df['invested_val']).round(2)
    res_df['pnl_pct'] = ((res_df['pnl'] / res_df['invested_val'].replace(0, np.nan)) * 100).fillna(0).round(2)
    res_df['asset_type'] = res_df['stock_name'].apply(detect_asset_type)
    res_df['sector'] = 'Unknown'

    # Prepare schema debugging metadata
    raw_cols = list(df.columns) if 'df' in locals() else []
    mapped_vals = list(col_map.values()) if 'col_map' in locals() else []
    ignored = [c for c in raw_cols if c not in mapped_vals]
    
    res_df.attrs['raw_columns'] = raw_cols
    res_df.attrs['mapped_columns'] = col_map if 'col_map' in locals() else {}
    res_df.attrs['ignored_columns'] = ignored
    valid_isins = res_df['isin'].astype(str).str.match(r'^IN[A-Z]{2}[0-9]{10}$') if 'isin' in res_df.columns else pd.Series(False)
    res_df.attrs['isin_coverage'] = f"{valid_isins.sum()}/{len(res_df)}"

    return res_df
