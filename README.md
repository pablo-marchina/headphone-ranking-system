# 🎧 Sistema de Ranking Profissional de Headphones

Este projeto automatiza a avaliação técnica de fones de ouvido cruzando dados de psicoacústica (AutoEQ), qualidade de construção (RTINGS) e valor de mercado (Mercado Livre).

## 🚀 Como usar
1. Instale as dependências: `pip install requests beautifulsoup4 pandas numpy lxml`
2. Gere a biblioteca: `python get_all_headphones.py` e `python get_rtings_urls.py`
3. Crie o mapeamento: `python generate_mapping.py`
4. Gere o ranking: `python dataset_generator.py`

## 🧠 Lógica de Cálculo
O sistema utiliza a escala **ERB (Equivalent Rectangular Bandwidth)** para pesar erros de frequência de forma similar ao ouvido humano, penalizando distorções (THD) e desequilíbrio entre os canais (Matching).
