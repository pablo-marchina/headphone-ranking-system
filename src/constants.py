import numpy as np

# --- Constantes de Frequência ---
FS = 44100
MIN_FREQ = 20
MAX_FREQ = 20000

# --- Constantes de Distorção ---
THD_THRESHOLD = 0.1  # T_THD: Limiar de 0.1% (o que for abaixo disso é ignorado)
JND_THD = 0.05       # JND_THD: Sensibilidade à variação de distorção

# --- Constante de Matching ---
JND_MATCH = 0.5  # JND_match: 0.5 dB de diferença já afeta o palco sonoro

# --- Constante de Incerteza ---
W_UNC = 0.5  # Peso da incerteza no erro total

# --- Escala ERB (Equivalent Rectangular Bandwidth) ---
# Conversão de Hz para ERB-rate (Glasberg & Moore)
def hz_to_erb(f):
    return 21.4 * np.log10(0.00437 * f + 1.0)

def erb_to_hz(e):
    return (10**(e / 21.4) - 1.0) / 0.00437

# --- Limiares de Percepção (JND - Just Noticeable Difference) ---
# Aproximações baseadas em estudos psicoacústicos para erro de FR
JND_FR = 1.0  # 1 dB de variação costuma ser o limiar em banda larga

# Fator de mascaramento para THD (Constante kappa do PDF)
KAPPA = 0.5 

# Constante de regularização para evitar divisão por zero
EPSILON = 1e-10

print("Constantes carregadas com sucesso.")