"""
Supabase REST API client — bypasses supabase-py entirely.
Uses raw HTTP requests to avoid all Client.__init__() compatibility issues.
"""
import os
import json
import requests
import pandas as pd


class SupabaseService:
    def __init__(self, url: str = None, key: str = None):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key  = key or os.getenv("SUPABASE_KEY", "")
        self._ok  = bool(self.url and self.key and self.url.startswith("http"))

    # ── internal helpers ──────────────────────────────────────────

    @property
    def _headers(self):
        return {
            "apikey":        self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type":  "application/json",
            "Prefer":        "return=representation",
        }

    def _insert(self, table: str, payload):
        """POST a row (or list of rows) to a Supabase table via REST."""
        if not self._ok:
            return None
        try:
            r = requests.post(
                f"{self.url}/rest/v1/{table}",
                headers=self._headers,
                data=json.dumps(payload),
                timeout=10,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return data if isinstance(data, list) else [data]
            else:
                print(f"Supabase insert error ({table}): {r.status_code} {r.text[:200]}")
                return None
        except Exception as e:
            print(f"Supabase network error ({table}): {e}")
            return None

    # ── public API ────────────────────────────────────────────────

    def is_configured(self):
        return self._ok

    def save_portfolio(self, name: str, stats: dict, health_score):
        data = {
            "name":          str(name),
            "total_invested": float(stats.get("total_invested", 0)),
            "total_current":  float(stats.get("total_current", 0)),
            "total_pnl":      float(stats.get("total_pnl", 0)),
            "total_pnl_pct":  float(stats.get("total_pnl_pct", 0)),
            "health_score":   int(health_score),
            "holdings_count": int(stats.get("holdings_count", 0)),
        }
        result = self._insert("portfolios", data)
        return result[0] if result else None

    def save_holdings(self, portfolio_id, df: pd.DataFrame):
        if df.empty:
            return

        def _f(v):
            try: return round(float(v), 4) if pd.notna(v) else 0.0
            except: return 0.0

        def _i(v):
            try: return int(float(v)) if pd.notna(v) else 0
            except: return 0

        rows = []
        for _, row in df.iterrows():
            rows.append({
                "portfolio_id": portfolio_id,
                "symbol":       str(row.get("stock_name", row.get("symbol", ""))),
                "qty":          _i(row.get("qty", row.get("quantity", 0))),
                "ltp":          _f(row.get("ltp", 0)),
                "current_val":  _f(row.get("current_val", row.get("current_value", 0))),
                "invested_val": _f(row.get("invested_val", row.get("invested_amount", 0))),
                "pnl":          _f(row.get("pnl", 0)),
                "pnl_pct":      _f(row.get("pnl_pct", 0)),
                "sector":       str(row.get("sector", "Unknown")),
                "asset_type":   str(row.get("asset_type", "Equity")),
            })

        # Batch insert in chunks of 100
        for i in range(0, len(rows), 100):
            self._insert("holdings", rows[i:i+100])

    def save_ai_report(self, portfolio_id, report: dict, model_used: str):
        data = {
            "portfolio_id":         portfolio_id,
            "behavioral_signature": str(report.get("behavioral_signature", "")),
            "strategic_verdict":    str(report.get("strategic_verdict", "")),
            "rebalancing_advice":   report.get("rebalancing_advice", []),
            "simple_summary":       str(report.get("simple_summary", "")),
            "model_used":           model_used,
        }
        self._insert("ai_reports", data)
