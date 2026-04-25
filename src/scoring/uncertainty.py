import numpy as np
from src.constants import W_UNC

def calculate_uncertainty_error(variance_array):
    """
    Calcula a penalidade por incerteza baseada na variância 
    entre diferentes fontes de medição.
    
    Parâmetros:
    - variance_array: Array de variância calculado no módulo de combinação.
    
    Retorna:
    - Escalar de erro de incerteza.
    """
    if variance_array is None or len(variance_array) == 0:
        return 0.0
    
    # A incerteza é a média da raiz quadrada da variância (desvio padrão médio)
    # multiplicada pelo nosso peso de importância.
    avg_std = np.mean(np.sqrt(variance_array))
    
    return avg_std * W_UNC

if __name__ == "__main__":
    # Exemplo: Variância alta em alguns pontos (dados conflitantes)
    var = np.array([0.1, 4.0, 0.1, 9.0]) # Muita divergência em dois pontos
    erro = calculate_uncertainty_error(var)
    print(f"Erro de Incerteza (E_unc): {erro:.2f}")