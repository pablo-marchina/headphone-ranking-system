from src.collectors.autoeq            import fetch_autoeq_data
from src.collectors.targets           import get_harman_target, detect_category
from src.collectors.rtings            import fetch_rtings_metrics
from src.collectors.mercadolivre      import fetch_br_prices_list
from src.preprocessing.price_cleaner import clean_price_data
from pipeline import run_evaluation_pipeline


def evaluate(headphone_name, rtings_slug=''):
    print(f"\n{'='*55}")
    print(f"  AVALIAÇÃO: {headphone_name}")
    print(f"{'='*55}")

    sources  = fetch_autoeq_data(headphone_name)
    category = detect_category(headphone_name)
    t_f, t_m = get_harman_target(category)
    rtings   = fetch_rtings_metrics(rtings_slug) if rtings_slug else None
    prices   = fetch_br_prices_list(headphone_name)
    price    = clean_price_data(prices, headphone_name)

    result = run_evaluation_pipeline(
        name=headphone_name,
        sources_data=sources,
        target_freqs=t_f,
        target_mags=t_m,
        thd_data=rtings['thd'] if rtings else None,
        price=price,
    )

    if not result:
        print("  Sem dados suficientes para avaliação.\n")
        return

    thd_tag   = "com THD"   if result['thd_available']   else "sem THD"
    match_tag = "com L/R"   if result['match_available'] else "sem L/R"

    print(f"\n  Categoria      : {category}")
    print(f"  Fontes AutoEQ  : {result['n_sources']}  ({thd_tag} / {match_tag})")
    if price:
        print(f"  Preço (BR)     : R$ {price:.2f}")
    else:
        print(f"  Preço          : não encontrado")

    print(f"\n  ── Erros (unidades JND) ──")
    print(f"  E_FR           : {result['e_fr']:.4f}")
    print(f"  E_THD          : {result['e_thd']:.4f}")
    print(f"  E_match        : {result['e_match']:.4f}")
    print(f"  ─────────────────────────")
    print(f"  E_total        : {result['e_total']:.4f}")
    print(f"\n  ── Confiança ──")
    print(f"  E_unc          : {result['e_unc']:.4f}")
    print(f"  w_conf         : {result['w_conf']:.4f}")

    if result['score']:
        print(f"\n  SCORE  =  w_conf / (max(E_total,ε) · P)")
        print(f"         =  {result['w_conf']:.4f} / (max({result['e_total']:.4f}, 0.1) · {price:.2f})")
        print(f"         =  {result['score']:.6f}")
    else:
        print(f"\n  SCORE  : n/a — preço não disponível no Mercado Livre")
    print()


if __name__ == "__main__":
    evaluate("Sennheiser HD 600", rtings_slug="sennheiser/hd-600")