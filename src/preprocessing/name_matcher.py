from fuzzywuzzy import fuzz
from accidents import RTINGS_SLUGS # Supondo que você tenha uma lista de slugs do RTINGS

def find_best_rtings_match(autoeq_name, rtings_slugs):
    """
    Compara o nome do AutoEQ com todos os slugs do RTINGS e retorna o mais provável.
    """
    best_match = None
    highest_score = 0
    
    # Normalização básica do nome original
    clean_name = autoeq_name.lower().replace(" ", "-")

    for slug in rtings_slugs:
        # O slug do RTINGS geralmente é 'marca/modelo'
        # Removemos a barra para comparar o texto puro
        clean_slug = slug.replace("/", "-")
        
        # Ratio calcula a similaridade de 0 a 100
        score = fuzz.token_set_ratio(clean_name, clean_slug)
        
        if score > highest_score:
            highest_score = score
            best_match = slug

    # Só aceitamos se a confiança for maior que 85%
    return best_match if highest_score > 85 else None