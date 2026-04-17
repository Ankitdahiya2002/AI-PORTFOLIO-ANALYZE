import time
import warnings
import logging
import pandas as pd
import re

# Silence yfinance 404 errors from polluting the terminal
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    yf = None
    _YF_AVAILABLE = False

# Known ticker corrections for commonly misresolved Indian stocks
NSE_OVERRIDES = {
    'SHILCHAR': '531169', 'CAPLIN': 'CAPLIPOINT', 'NATCO': 'NATCOPHARM',
    'GREAT': 'GESHIP', 'DATA': 'DATAPATTNS', 'BALAJI': 'BALAMINES',
    'APOLLO': 'APOLLOHOSP', 'HDFC': 'HDFCBANK', 'BAJAJ': 'BAJFINANCE',
    'TATA': 'TATASTEEL', 'SBI': 'SBIN', 'ICICI': 'ICICIBANK',
    'AXIS': 'AXISBANK', 'KOTAK': 'KOTAKBANK', 'INFOSYS': 'INFY',
    'WIPRO': 'WIPRO', 'HCL': 'HCLTECH', 'TECH': 'TCS',
}


class MarketDataService:
    def __init__(self, fmp_keys=[], av_key=None):
        self.fmp_keys = fmp_keys
        self.av_key   = av_key
        self.cache    = {}

    def _build_ticker_candidates(self, stock_name, isin=None):
        """
        Build a prioritized list of ticker symbols to try for a given stock name.
        Strategy:
        1. If ISIN is known, use yfinance ISIN lookup
        2. Try known NSE abbreviation overrides
        3. Try common Indian ticker patterns
        """
        name = str(stock_name).strip().upper()

        # Strip common noise
        name = re.sub(r'\s*-\s*(EQ|BE|N[0-9])\s*$', '', name).strip()
        name = re.sub(r'\s+(LIMITED|LTD|INDUSTRIES|TECHNOLOGIES|ENTERPRISE|SERVICES|SOLUTIONS|CORPORATION|COMPANY|CHEMICALS|PHARMACEUTICALS|PHARMA|FINANCE|FINANCIAL|BANK|TRADING|HOLDINGS|INTERNATIONAL)\s*$', '', name, flags=re.IGNORECASE).strip()

        # Words of the cleaned name
        words = name.split()
        first = words[0] if words else name
        first2 = ''.join(words[:2])[:12] if len(words) > 1 else first

        # Check override table
        override = NSE_OVERRIDES.get(first)

        candidates = []

        # Highest priority: known override
        if override:
            candidates += [f"{override}.NS", f"{override}.BO"]

        # Next: try joined first-2-words (common NSE pattern e.g., SHILCHARTEC)
        if first2 != first:
            candidates += [f"{first2}.NS", f"{first2}.BO"]

        # Next: try first word only
        candidates += [f"{first}.NS", f"{first}.BO"]

        # Next: try full name (no spaces, truncated to 20 chars)
        fullname = re.sub(r'[^A-Z0-9]', '', name)[:20]
        if fullname not in (first, first2):
            candidates += [f"{fullname}.NS", f"{fullname}.BO"]

        # Deduplicate while preserving order
        seen, unique = set(), []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return unique

    def _fetch_ticker(self, sym):
        """Safely fetch yfinance ticker info, returning None on any error."""
        if not _YF_AVAILABLE:
            return None
        try:
            t = yf.Ticker(sym)
            info = t.info
            # yfinance returns a minimal dict on 404 — check for a real price
            price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('navPrice')
            if not price:
                return None
            return {
                'price':        float(price),
                'pe':           float(info.get('trailingPE') or 0),
                'beta':         float(info.get('beta') or 1.0),
                'mkt_cap':      float(info.get('marketCap') or 0),
                'sector':       info.get('sector') or 'Unknown',
                'industry':     info.get('industry') or 'Unknown',
                'company_name': info.get('longName') or sym,
                'ticker':       sym,
                'source':       'Yahoo Finance',
            }
        except Exception:
            return None

    def fetch_yf_data(self, stock_name, isin=''):
        """
        Fetches live market data for a stock using smart ticker resolution.
        Never crashes — always returns None on failure.
        """
        cache_key = isin if isin and len(isin) == 12 else stock_name
        if cache_key in self.cache:
            return self.cache[cache_key]

        candidates = self._build_ticker_candidates(stock_name, isin)

        for sym in candidates:
            result = self._fetch_ticker(sym)
            if result:
                self.cache[cache_key] = result
                return result
            time.sleep(0.02)  # gentle pacing

        # All attempts failed — cache None to avoid retry
        self.cache[cache_key] = None
        return None

    def enrich_portfolio(self, df):
        """
        Enriches the portfolio DataFrame with live Yahoo Finance data.
        Silently skips stocks where tickers cannot be resolved.
        """
        if df.empty:
            return df

        # Ensure required columns exist
        for col in ['ltp', 'pe', 'beta', 'sector', 'mkt_cap']:
            if col not in df.columns:
                df[col] = 0 if col != 'sector' else 'Unknown'

        for index, row in df.iterrows():
            stock  = row.get('stock_name', row.get('symbol', ''))
            isin   = row.get('isin', '')
            data   = self.fetch_yf_data(stock, isin)

            if data and data['price'] > 0:
                current_ltp = df.at[index, 'ltp']
                if pd.isna(current_ltp) or float(current_ltp) == 0:
                    df.at[index, 'ltp'] = data['price']
                df.at[index, 'pe']      = data.get('pe', 0)
                df.at[index, 'beta']    = data.get('beta', 1.0)
                df.at[index, 'sector']  = data.get('sector', 'Unknown')
                df.at[index, 'mkt_cap'] = data.get('mkt_cap', 0)

            time.sleep(0.03)  # gentle pacing — ~33 stocks/sec

        # Recalculate P&L using live prices where available (or preserved broker prices)
        ltp_col = df['ltp'].astype(float)
        qty_col = df['qty'].astype(float) if 'qty' in df.columns else df['quantity'].astype(float)

        # Update current_val ONLY if missing
        missing_val_mask = (df['current_val'] == 0) | df['current_val'].isna()
        live_mask = (ltp_col > 0) & missing_val_mask
        df.loc[live_mask, 'current_val'] = (ltp_col * qty_col)[live_mask]

        # Sync display columns with calculated values
        df['current_value']   = df['current_val']
        df['invested_amount'] = df['invested_val']

        df['pnl']     = (df['current_val'] - df['invested_val']).round(2)
        df['pnl_pct'] = ((df['pnl'] / df['invested_val'].replace(0, float('nan'))) * 100).fillna(0).round(2)

        return df
