import numpy as np
from src.constants import KAPPA, THD_THRESHOLD, JND_THD, EPSILON

def calculate_masking_factor(measured_mags):
    """
    Calcula o fator de mascaramento M_h(b).
    M_h(b) = 1 + KAPPA * E_rel
    
    Onde E_rel é a energia relativa (convertida de dB para escala linear 
    para representar a pressão sonora).
    """
    # Convertemos dB para uma escala linear de pressão (relativa)
    # Usamos 10**(mags/20) para simular a amplitude da onda
    energy_linear = 10 ** (measured_mags / 20)
    
    # Normalizamos a energia pelo valor médio para ter um E_rel equilibrado
    e_rel = energy_linear / (np.mean(energy_linear) + EPSILON)
    
    return 1 + KAPPA * e_rel

def calculate_thd_error(thd_measurements, measured_mags):
    """
    Calcula o erro de distorção (E_THD) considerando o mascaramento.
    
    thd_measurements: Array com os valores de THD em % (ex: 0.5 para 0.5%)
    measured_mags: Resposta de frequência do fone (para calcular o mascaramento)
    """
    # 1. Calcula o Fator de Mascaramento baseado na FR do fone
    masking_factor = calculate_masking_factor(measured_mags)
    
    # 2. Calcula o excesso de distorção acima do limiar (T_THD)
    # max(0, THD_h - T_THD)
    excess_thd = np.maximum(0, thd_measurements - THD_THRESHOLD)
    
    # 3. Aplica a fórmula final: 
    # E_THD = Excesso / (JND * Mascaramento)
    # Quanto maior o mascaramento (mais som na banda), menor a penalidade.
    perceptual_thd_error = excess_thd / (JND_THD * masking_factor + EPSILON)
    
    return np.mean(perceptual_thd_error)

if __name__ == "__main__":
    # Teste: Fone com 1% de THD constante
    mags = np.zeros(500) # FR plana em 0dB
    thd = np.ones(500) * 1.0 # 1% de THD em tudo
    
    erro = calculate_thd_error(thd, mags)
    print(f"Erro de Distorção Percebido: {erro:.2f}")