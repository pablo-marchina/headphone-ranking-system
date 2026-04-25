import numpy as np
from src.constants import JND_MATCH

def calculate_matching_error(left_mags, right_mags):
    """
    Calcula o erro de matching entre os canais Esquerdo e Direito.
    
    Parâmetros:
    - left_mags: Resposta de frequência do canal esquerdo (suavizada/ERB).
    - right_mags: Resposta de frequência do canal direito (suavizada/ERB).
    
    Retorna:
    - Escalar do erro de matching. 0 é o equilíbrio perfeito.
    """
    if len(left_mags) != len(right_mags):
        raise ValueError("Os canais L e R devem ter o mesmo número de pontos.")

    # Diferença absoluta entre os canais em cada ponto da escala ERB
    diff = np.abs(left_mags - right_mags)
    
    # Normaliza pelo JND de matching
    perceptual_diff = diff / JND_MATCH
    
    # Retorna a média do erro
    return np.mean(perceptual_diff)

if __name__ == "__main__":
    # Teste: Um lado está 1dB acima do outro em todo o espectro
    L = np.array([11, 11, 11])
    R = np.array([10, 10, 10])
    
    erro = calculate_matching_error(L, R)
    print(f"Erro de Matching (E_match): {erro:.2f}")
    # Com JND=0.5, o resultado esperado é 2.0 (pois 1.0dB é o dobro do limiar)