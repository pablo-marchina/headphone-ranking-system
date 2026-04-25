from src.collectors.autoeq import fetch_autoeq_data
from src.collectors.targets import get_harman_target
from src.collectors.rtings import fetch_rtings_metrics
from src.collectors.mercadolivre import fetch_br_price
from pipeline import run_evaluation_pipeline
import numpy as np

def main():
    headphone_name = "Sennheiser HD 600"
    rtings_slug = "sennheiser/hd-600"

    print(f"=== SISTEMA DE RANKING DE AUDIO v1.0 ===")
    
    # 1. Coleta de dados técnicos
    freqs, mags = fetch_autoeq_data(headphone_name)
    target_f, target_m = get_harman_target()
    rtings_data = fetch_rtings_metrics(rtings_slug)
    
    # 2. Coleta de preço
    price = fetch_br_price(headphone_name)

    if freqs is not None:
        # Executa o pipeline para nota técnica
        technical_score = run_evaluation_pipeline(
            name=headphone_name,
            raw_freqs=freqs,
            raw_mags=mags,
            target_freqs=target_f,
            target_mags=target_m,
            thd_data=rtings_data['thd'] if rtings_data else 0.5,
            left_mags=mags,
            right_mags=mags + (rtings_data['matching'] if rtings_data else 0)
        )

        print("-" * 30)
        print(f"RESULTADOS PARA: {headphone_name}")
        print(f"Nota Técnica: {technical_score:.2f}/10")
        
        if price:
            # Cálculo de Custo-Benefício (Score / log10 do preço)
            # Fones caros precisam de notas muito altas para manter o CB
            cb_index = (technical_score**2) / np.log10(price)
            print(f"Preço Estimado: R$ {price}")
            print(f"Índice Custo-Benefício: {cb_index:.2f}")
        else:
            print("Preço não encontrado para cálculo de Custo-Benefício.")
        print("-" * 30)

if __name__ == "__main__":
    main()