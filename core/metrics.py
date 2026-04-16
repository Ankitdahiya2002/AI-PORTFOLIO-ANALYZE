def calculate_portfolio_metrics(df):
    """
    Calculates weighted portfolio metrics (Beta, PE, etc.).
    Returns a dictionary of summary statistics.
    """
    # Filter for Equity assets (where Beta and PE make sense)
    equity_df = df[df['asset_type'] == 'Equity'].copy()
    total_invested = df['invested_val'].sum()
    total_current = df['current_val'].sum()
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested != 0 else 0

    # Calculate Weights
    df['weight'] = df['current_val'] / total_current if total_current != 0 else 0

    # Portfolio Stats
    stats = {
        'total_invested': total_invested,
        'total_current': total_current,
        'total_pnl': total_pnl,
        'total_pnl_pct': total_pnl_pct,
        'holdings_count': len(df),
    }

    # Optional: Weighted metrics (Weighted Average PE, Weighted Average Beta)
    # Note: Values like Beta and PE will mostly be fetched via API and merged into the DataFrame
    # If the DataFrame already has 'pe' or 'beta' columns:
    if 'pe' in df.columns:
        valid_pe = df[df['pe'] > 0]
        valid_weight = valid_pe['current_val'].sum() / total_current if total_current != 0 else 0
        stats['weighted_pe'] = (valid_pe['pe'] * (valid_pe['current_val'] / valid_pe['current_val'].sum())).sum() if valid_weight > 0 else 0

    if 'beta' in df.columns:
        stats['weighted_beta'] = (df['beta'] * df['weight']).sum()

    return stats

def analyze_portfolio_health(stats):
    """
    Determines a Health Score based on diversification, risk, and returns.
    """
    score = 50  # Base score

    # Diversification (e.g. at least 5-10 holdings)
    if stats['holdings_count'] >= 10: score += 15
    elif stats['holdings_count'] >= 5:  score += 10

    # Beta — only apply if real weighted_beta was calculated from live data
    # (absence of this key means no market data was fetched, so we skip it)
    if 'weighted_beta' in stats:
        beta = stats['weighted_beta']
        if 0.8 <= beta <= 1.2: score += 15   # Balanced
        elif beta < 0.8:        score += 10   # Low risk
        else:                   score -= 5    # Higher risk
    # When no beta data: give a small neutral bonus for having a real portfolio
    else:
        score += 5

    # Profitability — most important real signal
    pnl = stats.get('total_pnl_pct', 0)
    if pnl > 20:   score += 20
    elif pnl > 10: score += 15
    elif pnl > 0:  score += 10
    elif pnl < -20: score -= 15
    elif pnl < -10: score -= 8
    elif pnl < 0:   score -= 4

    return min(100, max(0, score))
