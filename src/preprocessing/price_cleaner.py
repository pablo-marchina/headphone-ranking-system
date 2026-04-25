import numpy as np

def clean_price_data(price_list, headphone_name):
    """
    Remove outliers e preços que provavelmente são de acessórios.
    """
    if not price_list:
        return None

    # 1. Filtro de Piso (Hard Floor)
    # Dificilmente um fone de alta fidelidade custa menos de R$ 150
    # (Ajuste este valor conforme a categoria do fone)
    prices = [p for p in price_list if p > 150]
    
    if not prices:
        return None

    # 2. Filtro Estatístico (IQR - Interquartile Range)
    # Remove anúncios muito caros ou muito baratos em relação à média da busca
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    filtered_prices = [p for p in prices if p >= lower_bound and p <= upper_bound]

    # Retorna a mediana (mais robusta que a média para preços)
    return np.median(filtered_prices) if filtered_prices else np.median(prices)