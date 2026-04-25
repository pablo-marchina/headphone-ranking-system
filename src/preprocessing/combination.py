import numpy as np

def combine_sources(list_of_magnitudes, weights=None):
    """
    Combina múltiplas curvas de resposta em frequência em uma só.
    
    Parâmetros:
    - list_of_magnitudes: Lista de arrays (cada array é uma curva FR).
    - weights: Pesos de confiança para cada fonte (ex: [0.8, 1.2]).
               Se None, assume pesos iguais.
    """
    if not list_of_magnitudes:
        return None
    
    if weights is None:
        weights = np.ones(len(list_of_magnitudes))
    
    # Normaliza os pesos para que a soma seja 1
    weights = np.array(weights) / np.sum(weights)
    
    # Calcula a média ponderada
    combined = np.average(list_of_magnitudes, axis=0, weights=weights)
    
    # Calcula a variância (incerteza entre as fontes)
    # Isso será usado depois para o cálculo do Erro de Incerteza (E_unc)
    uncertainty = np.var(list_of_magnitudes, axis=0)
    
    return combined, uncertainty