import numpy as np
from src.preprocessing.erb import interpolate_to_erb
from src.preprocessing.alignment import align_gain
from src.preprocessing.smoothing import apply_smoothing
from src.scoring.frequency_response import calculate_fr_error
from src.scoring.distortion import calculate_thd_error
from src.scoring.matching import calculate_matching_error
from src.scoring.uncertainty import calculate_uncertainty_error
from src.scoring.final_score import calculate_total_error, convert_error_to_score

def run_evaluation_pipeline(name, raw_freqs, raw_mags, target_freqs, target_mags, thd_data, left_mags=None, right_mags=None):
    print(f"--- Avaliando Fone: {name} ---")

    # 1. Pré-processamento: Interpolação ERB
    erb_freqs, erb_mags = interpolate_to_erb(raw_freqs, raw_mags)
    _, target_erb_mags = interpolate_to_erb(target_freqs, target_mags)

    # 2. Pré-processamento: Alinhamento de Ganho
    aligned_mags, _ = align_gain(erb_freqs, erb_mags, erb_freqs, target_erb_mags)

    # 3. Pré-processamento: Suavização
    final_mags = apply_smoothing(aligned_mags)

    # 4. Cálculo de Erros
    e_fr = calculate_fr_error(final_mags, target_erb_mags)
    
    # Simulação de THD (se thd_data for escalar, expandimos para o grid)
    thd_grid = np.full(len(erb_freqs), thd_data)
    e_thd = calculate_thd_error(thd_grid, final_mags)

    # Erro de Matching (L/R)
    if left_mags is not None and right_mags is not None:
        e_match = calculate_matching_error(left_mags, right_mags)
    else:
        e_match = 0.0 # Caso não existam dados L/R

    # Erro de Incerteza (Simulado como 0 por enquanto)
    e_unc = 0.0

    # 5. Score Final
    e_total = calculate_total_error(e_fr, e_thd, e_match, e_unc)
    score = convert_error_to_score(e_total)

    print(f"Erro FR: {e_fr:.2f} | Erro THD: {e_thd:.2f} | Erro Match: {e_match:.2f}")
    print(f"ERRO TOTAL: {e_total:.2f}")
    print(f"SCORE FINAL: {score:.2f}/10\n")
    
    return score

if __name__ == "__main__":
    # Dados de Teste (Mock)
    freqs_mock = np.array([20, 100, 1000, 5000, 20000])
    mags_mock = np.array([10, 12, 10, 15, 5])   # Resposta do fone
    target_mock = np.array([10, 10, 10, 10, 10]) # Alvo plano (flat)
    
    run_evaluation_pipeline("Fone Teste 101", freqs_mock, mags_mock, freqs_mock, target_mock, thd_data=0.5)