# 🎧 Sistema de Ranking de Fones — Custo-Benefício Perceptual

Avalia fones de ouvido cruzando dados acústicos (AutoEQ), distorção (RTINGS) e preço (Mercado Livre), produzindo um ranking de custo-benefício baseado em psicoacústica.

---

## Configuração inicial

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar GITHUB_TOKEN (obrigatório para rodar o dataset completo)

Sem token: limite de 60 requisições/hora → quebra no meio do dataset.  
Com token: 5.000 requisições/hora → suficiente para rodar tudo de uma vez.

**Como gerar o token:**
1. Acesse https://github.com/settings/tokens
2. Clique em **"Generate new token (classic)"**
3. Dê um nome (ex: `headphone-ranking`)
4. **Não precisa marcar nenhum escopo** — acesso público é suficiente
5. Clique em **"Generate token"** e copie o valor

**Como configurar:**
```bash
# Linux / macOS
export GITHUB_TOKEN=ghp_seuTokenAqui

# Windows CMD
set GITHUB_TOKEN=ghp_seuTokenAqui

# Windows PowerShell
$env:GITHUB_TOKEN="ghp_seuTokenAqui"
```

---

## Executar o ranking completo

Execute os scripts **na ordem abaixo** em um único terminal (o token precisa estar configurado):

```bash
# Passo 1 — Indexar todos os fones disponíveis no AutoEQ
python get_all_headphones.py

# Passo 2 — Buscar slugs do RTINGS para cruzamento de THD
python get_rtings_urls.py

# Passo 3 — Mapear nomes AutoEQ ↔ RTINGS (fuzzy match)
python generate_mapping.py

# Passo 4 — Gerar o ranking completo
python dataset_generator.py
```

O resultado final estará em **`output/ranking.csv`**.

---

## Testar com poucos fones antes

Para validar o pipeline sem esperar o dataset inteiro, edite a última linha de `dataset_generator.py`:

```python
build_dataset(limit=10)   # roda apenas os 10 primeiros
```

Ou rode diretamente um fone específico:

```bash
python main.py
```

---

## Estrutura do projeto

```
headphone_ranking/
├── main.py                      # Avalia um único fone (teste manual)
├── dataset_generator.py         # Gera o ranking completo → output/ranking.csv
├── pipeline.py                  # Orquestra o pipeline de avaliação
├── get_all_headphones.py        # Indexa fones do AutoEQ via GitHub API
├── get_rtings_urls.py           # Busca slugs de fones no RTINGS
├── generate_mapping.py          # Mapeia AutoEQ ↔ RTINGS (fuzzy match)
├── requirements.txt
├── data/
│   ├── headphone_library.json   # gerado por get_all_headphones.py
│   ├── rtings_library.json      # gerado por get_rtings_urls.py
│   └── name_mapping.json        # gerado por generate_mapping.py
├── src/
│   ├── constants.py             # κ, ε, JND, τ_THD e constantes ERB
│   ├── collectors/
│   │   ├── autoeq.py            # Busca FR raw no AutoEQ (com suporte a GITHUB_TOKEN)
│   │   ├── rtings.py            # Scraper THD do RTINGS
│   │   ├── mercadolivre.py      # API oficial ML para preços
│   │   └── targets.py           # Curvas Harman OE 2018 e IEM 2019
│   ├── preprocessing/
│   │   ├── erb.py               # Interpolação ERB-rate (Glasberg & Moore 1990)
│   │   ├── alignment.py         # Alinhamento de ganho L1-ótimo (200–2 kHz)
│   │   ├── smoothing.py         # Suavização gaussiana ~1/12 oitava
│   │   ├── combination.py       # Média ponderada por consistência inter-fonte
│   │   └── price_cleaner.py     # Filtro IQR para preços do ML
│   └── scoring/
│       ├── frequency_response.py  # E_FR — erro tonal em JND
│       ├── distortion.py          # E_THD — distorção com mascaramento
│       ├── matching.py            # E_match — desequilíbrio L/R ponderado por energia
│       ├── uncertainty.py         # E_unc → w_conf (confiança, não erro aditivo)
│       └── final_score.py         # Score = w_conf / (max(E_total, ε) · P)
└── output/
    └── ranking.csv              # Resultado final
```

---

## Colunas do ranking.csv

| Coluna | Descrição |
|---|---|
| `rank` | Posição no ranking geral |
| `name` | Nome do fone |
| `category` | `over-ear` ou `in-ear` |
| `score` | Score final (maior = melhor custo-benefício) |
| `percentile` | Percentil dentro do dataset |
| `e_total` | Erro total (soma E_FR + E_THD + E_match) em JND |
| `e_fr` | Erro de resposta em frequência |
| `e_thd` | Erro de distorção harmônica |
| `e_match` | Erro de matching L/R |
| `e_unc` | Incerteza das fontes |
| `w_conf` | Peso de confiança (0–1) |
| `price_brl` | Preço mediano no Mercado Livre (R$) |
| `n_sources` | Número de fontes AutoEQ usadas |
| `thd_available` | Se THD foi obtido do RTINGS |
| `match_available` | Se dados L/R reais estavam disponíveis |
