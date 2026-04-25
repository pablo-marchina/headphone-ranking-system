import numpy as np


def clean_price_data(price_list, headphone_name=''):
    """
    Remove outliers from a raw list of prices (BRL).

    Steps:
      1. Hard floor at R$150 — accessories and obviously wrong values
      2. IQR filter — removes statistical outliers (blown-up or stale stock)
      3. Return median of clean set (robust to remaining skew)
    """
    if not price_list:
        return None

    prices = [p for p in price_list if p > 150]
    if not prices:
        return None

    q1, q3 = np.percentile(prices, 25), np.percentile(prices, 75)
    iqr     = q3 - q1
    lb, ub  = q1 - 1.5 * iqr, q3 + 1.5 * iqr

    clean = [p for p in prices if lb <= p <= ub]
    return float(np.median(clean if clean else prices))