import numpy as np
from scipy.optimize import minimize

def calculate_l1_offset(magnitudes, target_mags):
    """
    Encontra o valor constante 'c' (offset em dB) que deve ser 
    somado às magnitudes para minimizar a diferença absoluta média (L1) 
    em relação ao alvo.
    """
    # Função objetivo: Soma das diferenças absolutas
    def objective(c):
        return np.mean(np.abs((magnitudes + c) - target_mags))

    # Chute inicial: a diferença entre as médias
    initial_guess = np.mean(target_mags) - np.mean(magnitudes)
    
    # Otimização
    res = minimize(objective, initial_guess, method='Nelder-Mead')
    return res.x[0]

def align_gain(freqs, magnitudes, target_freqs, target_mags, f_min=200, f_max=2000):
    """
    Alinha a curva de magnitude ao alvo, focando o cálculo do offset 
    em uma faixa de frequência específica (geralmente os médios: 200Hz-2kHz).
    """
    # Filtra os dados para a janela de alinhamento (ex: 200Hz a 2000Hz)
    # Isso evita que graves extremos ou agudos muito oscilantes desviem o alinhamento
    mask = (freqs >= f_min) & (freqs <= f_max)
    
    if not np.any(mask):
        # Se as frequências não baterem, usa a curva inteira
        offset = calculate_l1_offset(magnitudes, target_mags)
    else:
        # Calcula o offset baseado apenas na região de interesse
        offset = calculate_l1_offset(magnitudes[mask], target_mags[mask])
    
    return magnitudes + offset, offset

if __name__ == "__main__":
    # Teste rápido
    freqs = np.array([100, 500, 1000, 5000])
    mags = np.array([10, 10, 10, 10])      # Uma linha reta em 10dB
    target = np.array([12, 12, 12, 12])    # Alvo em 12dB
    
    aligned, offset = align_gain(freqs, mags, freqs, target)
    print(f"Offset encontrado: {offset:.2f} dB")
    print(f"Magnitudes alinhadas: {aligned}")