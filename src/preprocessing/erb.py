import numpy as np
from scipy.interpolate import interp1d
from src.constants import MIN_FREQ, MAX_FREQ, hz_to_erb, erb_to_hz

def generate_erb_grid(min_f=MIN_FREQ, max_f=MAX_FREQ, num_points=500):
    """
    Gera um vetor de frequências que estão uniformemente espaçadas 
    na escala perceptual ERB.
    """
    min_erb = hz_to_erb(min_f)
    max_erb = hz_to_erb(max_f)
    erb_grid = np.linspace(min_erb, max_erb, num_points)
    
    return erb_to_hz(erb_grid)

def interpolate_to_erb(freqs, magnitudes, num_points=500):
    """
    Pega uma curva de Resposta em Frequência (FR) crua e a interpola
    para a grade de frequências ERB.
    
    Parâmetros:
    - freqs: array de frequências originais da medição (em Hz)
    - magnitudes: array de amplitude original (em dB)
    - num_points: quantidade de pontos de resolução (padrão 500)
    
    Retorna:
    - erb_freqs: O novo eixo X (frequências em Hz, mas com espaçamento ERB)
    - erb_mags: O novo eixo Y (amplitudes em dB interpoladas)
    """
    # Gera a nova grade de frequências-alvo
    erb_freqs = generate_erb_grid(num_points=num_points)
    
    # Cria a função de interpolação linear
    # bounds_error=False e fill_value garantem que, se a medição original for mais 
    # curta que 20Hz-20kHz, os valores das pontas sejam mantidos em vez de dar erro.
    interpolator = interp1d(
        freqs, 
        magnitudes, 
        kind='linear', 
        bounds_error=False, 
        fill_value=(magnitudes[0], magnitudes[-1])
    )
    
    # Aplica a interpolação
    erb_mags = interpolator(erb_freqs)
    
    return erb_freqs, erb_mags

if __name__ == "__main__":
    # Um pequeno teste para garantir que o módulo funciona
    print("Módulo ERB carregado. Testando geração de grade...")
    grade = generate_erb_grid(num_points=10)
    print(f"10 pontos na escala ERB (Hz): \n{np.round(grade, 1)}")