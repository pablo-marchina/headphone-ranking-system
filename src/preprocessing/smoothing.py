import numpy as np
from scipy.ndimage import gaussian_filter1d

def apply_smoothing(magnitudes, window_size=0.1):
    """
    Aplica uma suavização Gaussiana sobre as magnitudes.
    Como os dados já estão em escala ERB, a suavização é 
    perceptualmente uniforme em todo o espectro.
    
    Parâmetros:
    - magnitudes: Array de amplitudes em dB.
    - window_size: Intensidade da suavização. 
      Valores entre 0.05 e 0.2 são ideais para análise técnica.
    """
    # A suavização Gaussiana é mais natural que a média móvel simples
    smoothed = gaussian_filter1d(magnitudes, sigma=window_size * 100 / 2)
    
    return smoothed

if __name__ == "__main__":
    # Teste rápido de suavização
    test_mags = np.array([10, 12, 10, 11, 10, 30, 10]) # Um pico súbito (ruído)
    smoothed = apply_smoothing(test_mags, window_size=0.1)
    
    print("Original:", test_mags)
    print("Suavizado:", np.round(smoothed, 1))