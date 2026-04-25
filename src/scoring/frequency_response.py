import numpy as np
from src.constants import JND_FR

def calculate_fr_error(measured_mags, target_mags):
    """
    Calcula o erro de resposta em frequência (E_FR).
    
    A fórmula implementada é: 
    E_FR = média( |Medição - Alvo| / JND )
    
    Parâmetros:
    - measured_mags: Array de magnitudes do fone (já alinhadas e suavizadas).
    - target_mags: Array de magnitudes da curva-alvo (Harman, Diffuse Field, etc).
    
    Retorna:
    - Um valor escalar onde 0 é a perfeição. 
      Quanto maior o valor, pior a fidelidade tonal.
    """
    
    if len(measured_mags) != len(target_mags):
        raise ValueError("A medição e o alvo precisam ter o mesmo número de pontos (ERB grid).")

    # Calcula a diferença absoluta ponto a ponto
    absolute_diff = np.abs(measured_mags - target_mags)
    
    # Normaliza pelo JND (limiar de percepção)
    # Se JND_FR for 1.0, 1dB de erro = 1 ponto de penalidade por banda.
    perceptual_error = absolute_diff / JND_FR
    
    # Retorna a média do erro ao longo de todo o espectro
    return np.mean(perceptual_error)

if __name__ == "__main__":
    # Teste rápido: Fone com desvio constante de 2dB em relação ao alvo
    fone = np.array([12, 12, 12, 12])
    alvo = np.array([10, 10, 10, 10])
    
    erro = calculate_fr_error(fone, alvo)
    print(f"Erro FR (E_FR): {erro:.2f}") 
    # Com JND=1.0, o resultado deve ser 2.0