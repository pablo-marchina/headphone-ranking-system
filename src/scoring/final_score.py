import numpy as np
from src.constants import EPSILON


def calculate_total_error(e_fr, e_thd, e_match):
    """
    E_total = E_FR + E_THD + E_match
    E_unc is intentionally excluded — it enters as w_conf, not as additive error.
    """
    return float(e_fr + e_thd + e_match)


def calculate_w_conf(e_unc):
    """
    w_conf(h) = 1 / (1 + E_unc) ∈ (0, 1]

    High uncertainty discounts the score without treating the headphone as "bad".
    Fones with E_unc=0 receive w_conf=1 (full confidence).
    """
    return 1.0 / (1.0 + float(e_unc))


def calculate_score(e_total, w_conf, price, epsilon=EPSILON):
    """
    Score(h) = w_conf / (max(E_total, ε) · P)

    Answers: most perceptual fidelity per BRL spent.
    ε prevents score explosion for near-perfect headphones
    (below ε JND the difference is perceptually irrelevant).
    """
    return w_conf / (max(float(e_total), epsilon) * float(price))


def rank_scores(results):
    """
    Sort result dicts by Score (descending), add 'rank' and 'percentile' fields.
    Only dicts with a non-None score are ranked.
    Returns the ranked list (mutates in place).
    """
    scored = [r for r in results if r.get('score') is not None]
    scored.sort(key=lambda x: x['score'], reverse=True)
    n = len(scored)
    for i, r in enumerate(scored):
        r['rank']       = i + 1
        r['percentile'] = round(100.0 * (n - i) / n, 1)
    return scored