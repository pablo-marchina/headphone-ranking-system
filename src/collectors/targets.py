import numpy as np

def get_harman_target():
    """
    Retorna uma curva Harman Over-Ear simplificada.
    Em um projeto real, leríamos um arquivo CSV em data/targets/.
    """
    # Frequências principais
    f = np.array([20, 50, 100, 200, 500, 1000, 2000, 3000, 5000, 10000, 20000])
    # Resposta Harman aproximada (Bass boost e ganho de orelha)
    m = np.array([6.5, 6.0, 5.0, 0.0, 0.0, 0.0, 8.0, 12.0, 5.0, -2.0, -10.0])
    
    return f, m