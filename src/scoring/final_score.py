import numpy as np

def calculate_total_error(e_fr, e_thd, e_match, e_unc):
    """
    Soma todos os componentes de erro.
    E_total = E_FR + E_THD + E_match + E_unc
    """
    return e_fr + e_thd + e_match + e_unc

def convert_error_to_score(e_total):
    """
    Converte o erro total em uma nota de 0 a 10.
    Usamos uma função exponencial decrescente para que o score
    não fique negativo e para que pequenas melhoras em fones já bons 
    sejam mais difíceis de conquistar.
    """
    # Se o erro for 0, a nota é 10.
    # Se o erro for 10 (muito alto), a nota cai drasticamente.
    score = 10 * np.exp(-0.15 * e_total)
    return np.clip(score, 0, 10)

if __name__ == "__main__":
    e_total = 2.5 # Exemplo de erro acumulado
    print(f"Nota Final: {convert_error_to_score(e_total):.2f}/10")