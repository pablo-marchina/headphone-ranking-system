# IMPLEMENTATION_PLAN.md
# Sistema de Ranking de Fones — Custo-Benefício Perceptual

## Objetivo do Projeto

Gerar um ranking único e definitivo de fones de ouvido para o mercado brasileiro,
cruzando qualidade acústica perceptual (medida por psicoacústica computacional)
com preço real de compra. O output é um CSV rankeado por custo-benefício real.
O projeto roda uma vez — não precisa de manutenção, automação ou deploy.

---

## Arquitetura Atual

```
headphone_ranking/
├── autoeq_repo/measurements/     ← clone local do AutoEQ (git clone)
├── data/
│   ├── headphone_library.json    ← gerado por get_all_headphones.py
│   ├── rtings_library.json       ← gerado por get_rtings_urls.py
│   ├── name_mapping.json         ← gerado por generate_mapping.py
│   └── price_cache.json          ← cache de preços ML
├── output/
│   ├── ranking.csv               ← resultado final
│   └── ranking_partial.csv       ← checkpoint durante run
├── src/
│   ├── constants.py              ← κ, ε, JND, σ e constantes ERB
│   ├── collectors/
│   │   ├── autoeq.py             ← lê CSVs locais do autoeq_repo/
│   │   ├── rtings.py             ← scraper THD do RTINGS
│   │   ├── mercadolivre.py       ← preços via scraping ML
│   │   └── targets.py            ← curvas Harman OE 2018 e IEM 2019
│   ├── preprocessing/
│   │   ├── erb.py                ← grid ERB (Glasberg & Moore 1990)
│   │   ├── alignment.py          ← alinhamento L1-ótimo 200-2kHz
│   │   ├── smoothing.py          ← gaussiana ~1/12 oitava
│   │   ├── combination.py        ← média ponderada inter-fonte
│   │   └── price_cleaner.py      ← filtro IQR de preços
│   └── scoring/
│       ├── frequency_response.py ← E_FR em JND
│       ├── distortion.py         ← E_THD com mascaramento
│       ├── matching.py           ← E_match L/R ponderado
│       ├── uncertainty.py        ← E_unc → w_conf
│       └── final_score.py        ← Score = w_conf / (E_total · P)
├── pipeline.py                   ← orquestra um fone
├── dataset_generator.py          ← roda todos os fones
├── get_all_headphones.py         ← indexa fones do autoeq_repo/ local
├── get_rtings_urls.py            ← busca slugs RTINGS
└── generate_mapping.py           ← fuzzy match AutoEQ ↔ RTINGS
```

### Contratos que NÃO podem mudar entre fases

**fetch_autoeq_data(name, library_entry)** retorna:
```python
[{
    'freqs': np.array,      # frequências Hz
    'mags': np.array,       # magnitude dB (mono ou média L+R)
    'left_mags': np.array,
    'right_mags': np.array,
    'source': str           # label do reviewer
}]
```

**run_evaluation_pipeline(name, sources_data, target_freqs, target_mags, thd_data, price)** retorna:
```python
{
    'name': str,
    'e_fr': float, 'e_thd': float, 'e_match': float,
    'e_unc': float, 'w_conf': float, 'e_total': float,
    'n_sources': int,
    'thd_available': bool, 'match_available': bool,
    'price_brl': float | None,
    'score': float | None,
    'confidence_interval': tuple | None   # (lower, upper) — adicionado na Fase 3
}
```

---

## Lista Completa de Melhorias por Fase

### FASE 1 — Arquitetura Base (implementar PRIMEIRO)

Nada das fases seguintes funciona sem isso.

1. **Fix deduplicação multi-source**
   - Problema: `get_all_headphones.py` usa `if name not in seen` → descarta medições duplicadas entre reviewers
   - Fix: `headphone_library.json` passa a ter lista de entradas por nome: `{'name': '...', 'sources': [{path_prefix, nested, reviewer}, ...]}`
   - Impacto: `fetch_autoeq_data()` passa a retornar múltiplas fontes para ~200 fones
   - Arquivos: `get_all_headphones.py`, `src/collectors/autoeq.py`

2. **Fix múltiplos rigs Crinacle**
   - Problema: mesmo fone em rigs diferentes (GRAS, B&K 5128, IEC) é deduplicado
   - Fix: rigs diferentes do mesmo fone tratados como fontes distintas no mesmo entry
   - Arquivos: `get_all_headphones.py`

3. **Dois passes separados**
   - Passe 1: coleta acústica → salva `data/acoustic_cache.json` com erros calculados por fone
   - Passe 2: coleta preços + aplica score final
   - Motivo: permite re-rodar só o scoring sem re-processar medições (horas de diferença)
   - Arquivos: `dataset_generator.py` (refatoração completa)

4. **Paralelismo com múltiplos workers**
   - Implementar sobre a nova arquitetura de dois passes
   - Passe 1 (acústico, local): `concurrent.futures.ProcessPoolExecutor`, 4 workers
   - Passe 2 (preços, rede): `ThreadPoolExecutor`, 8 workers (I/O bound)
   - Arquivos: `dataset_generator.py`

---

### FASE 2 — Fontes de Dados

Implementar cada coletor como classe herdando de `BaseCollector`:
```python
class BaseCollector:
    def fetch(self, name: str, **kwargs) -> list[dict]: ...
    def is_available(self) -> bool: ...
```

#### Fontes Acústicas (ordem de impacto)

5. **Squig.link** (+~3.000 IEMs)
   - URL base: `https://squig.link/`
   - API de dados: `https://squig.link/data/{name}.json` (verificar endpoint real)
   - Formato: frequência + magnitude, mesmo contrato do AutoEQ
   - Arquivo: `src/collectors/squig.py`

6. **InnerFidelity (arquivo Tyll Hertsens)** (+~600 clássicos)
   - Repositório GitHub: `github.com/markalex/innerfidelity` ou similar
   - Formato CSV igual ao AutoEQ
   - Arquivo: `src/collectors/innerfidelity.py`

7. **Headphones.com / Revel** (+~300 over-ears)
   - Verificar se têm API pública ou requer scraping
   - Arquivo: `src/collectors/headphonescom.py`

8. **Audio Science Review** (+~400 com THD estruturado real)
   - Scraping das páginas de review com Selenium ou Playwright (JavaScript necessário)
   - Capturar: FR data + THD data em formato estruturado
   - Arquivo: `src/collectors/asr.py`

9. **Reviewers independentes** (HypetheSonics, Antdroid, Super* Review, Bad Guy Good Audio, Precogvision)
   - Verificar se têm repositórios GitHub com CSVs ou APIs
   - Implementar coletores individuais apenas para os que tiverem dados estruturados acessíveis
   - Arquivos: `src/collectors/{reviewer}.py`

#### Fontes de Preço (ordem de viabilidade)

10. **JáCotei / Zoom / Buscapé como agregador**
    - Consultar preço mínimo brasileiro de todas as lojas em uma chamada
    - URL exemplo: `https://www.zoom.com.br/search?q={nome}`
    - Arquivo: `src/collectors/price_aggregator.py`

11. **Shopee**
    - Scraping: `https://shopee.com.br/search?keyword={nome}`
    - Filtro: vendedores com avaliação > 4.5, volume mínimo de vendas
    - Arquivo: integrar em `src/collectors/shopee.py`

12. **Amazon Brasil**
    - Scraping ou Product Advertising API (gratuita com conta)
    - Arquivo: integrar em `src/collectors/amazon.py`

13. **MSRP USD × câmbio como proxy**
    - API gratuita de câmbio: `https://api.exchangerate-api.com/v4/latest/USD`
    - MSRP a ser coletado do RTINGS ou Headphones.com durante coleta acústica
    - Usado apenas quando nenhuma fonte brasileira encontra preço
    - Arquivo: `src/collectors/msrp_proxy.py`

14. **Filtros de qualidade no ML**
    - Disponibilidade mínima: só rankear fones com ≥5 listagens ativas
    - Tipo de vendedor: score separado para vendedor oficial vs CPF
    - Implementar nos filtros do `src/collectors/mercadolivre.py` existente

---

### FASE 3 — Modelo Matemático

Implementar na ordem abaixo — cada item depende do anterior.

15. **Loudness model Moore-Glasberg (substitui ERB simples)**
    - Paper: Moore & Glasberg 2002, "A Revision of Zwicker's Loudness Model"
    - Biblioteca Python: `loudness` (PyPI) ou implementação manual dos filtros gammatone
    - Substitui `src/preprocessing/erb.py` — muda o grid de frequências base
    - ATENÇÃO: todos os módulos que usam `interpolate_to_erb` precisam ser atualizados
    - Arquivo: `src/preprocessing/loudness_model.py` (substitui `erb.py`)

16. **JND_FR variável com frequência (ISO 226)**
    - Dados: tabela ISO 226:2003 de equal loudness contours
    - Implementar como array `JND_FR(f)` que substitui escalar `JND_FR=1.0` em `constants.py`
    - Efeito: desvios em 3-4kHz pesam ~10x mais que em 100Hz ou 16kHz
    - Arquivo: `src/constants.py` + `src/scoring/frequency_response.py`

17. **Sean Olive Preference Score**
    - Paper: Olive 2004, "A Multiple Regression Model for Predicting Loudspeaker Preference"
    - Coeficientes publicados: bass (80-200Hz), mid-bass (200-400Hz), midrange (400-2kHz), treble (2-20kHz)
    - Implementar como score alternativo que complementa E_FR — não substitui
    - Arquivo: `src/scoring/olive_score.py`

18. **Peakiness metric / penalização de ressonâncias**
    - Desvio padrão da primeira derivada da curva ERB
    - Picos estreitos são mais audíveis que desvios graduais equivalentes em dB
    - Adicionar como componente em E_FR ou como penalidade separada
    - Arquivo: `src/scoring/frequency_response.py`

19. **Variância da distribuição do erro (L2 em vez de L1 puro)**
    - Adicionar penalidade para picos: `E_FR = alpha * mean(|dev|) + (1-alpha) * percentile_95(|dev|)`
    - Alpha calibrado empiricamente (sugestão inicial: 0.7)
    - Arquivo: `src/scoring/frequency_response.py`

20. **A-weighting na distorção**
    - Aplicar curva A-weighting ao array de THD antes de calcular E_THD
    - THD a 10kHz é muito menos audível que THD a 1kHz
    - Dados: tabela IEC 61672 de A-weighting por frequência
    - Arquivo: `src/scoring/distortion.py`

21. **THD+N além de THD puro**
    - Capturar THD+N do RTINGS na mesma passagem do scraper
    - Para fones com circuitos ativos (ANC), noise floor importa
    - Usar THD+N quando disponível, THD quando não
    - Arquivo: `src/collectors/rtings.py` + `src/scoring/distortion.py`

22. **IMD via RTINGS**
    - Capturar dados de IMD do RTINGS no scraper existente
    - Disponível para subset dos fones — tratar como THD quando disponível
    - Implementar métrica de IMD separada ou combinar com E_THD
    - Arquivo: `src/collectors/rtings.py` + `src/scoring/distortion.py`

23. **Mascaramento entre E_FR e E_THD**
    - Regiões com E_FR alto (erro tonal grande) devem penalizar E_THD menos
    - Física: distorção é menos audível onde o erro tonal já domina a percepção
    - Implementar como fator de mascaramento cruzado no cálculo de E_total
    - Arquivo: `src/scoring/final_score.py`

24. **Sensibilidade/eficiência como fator de usabilidade**
    - Dados: disponíveis no RTINGS (dB SPL/mW) e oratory1990
    - Fones < 85dB/mW recebem flag de "necessita amplificação"
    - Impacto no score: ajuste no denominador de preço (custo total = fone + amp estimado)
    - Arquivo: `src/collectors/rtings.py` + `src/scoring/final_score.py`

25. **Variação unit-to-unit no E_unc**
    - Dados: oratory1990 frequentemente mede múltiplas unidades e documenta variação
    - Extrair informação de variância unit-to-unit do texto das reviews quando disponível
    - Inflar `SIGMA_SINGLE_SOURCE` para modelos conhecidos por alta variação (HIFIMAN, Audeze early)
    - Arquivo: `src/scoring/uncertainty.py`

26. **Interação impedância × fonte**
    - Dados: curva de impedância do RTINGS
    - IEMs de BA com impedância variável mudam FR quando conectados a fontes com Z_out > 0
    - Implementar como flag/ajuste para IEMs BA com variação de impedância > 10 ohms
    - Arquivo: `src/collectors/rtings.py` + `src/scoring/frequency_response.py`

27. **Normalização cross-rig entre reviewers**
    - Calcular offset sistemático entre rigs usando ~30 fones medidos por oratory1990 E Crinacle
    - Aplicar correção antes do `combine_sources()` para não inflar variância artificialmente
    - Arquivo: `src/preprocessing/rig_normalization.py` (novo)

---

### FASE 4 — Output

28. **Confidence intervals por fone**
    - Método: bootstrap sobre os ERB bands disponíveis
    - Para n_sources=1: CI baseado em `SIGMA_SINGLE_SOURCE` histórico
    - Para n_sources>1: CI calculado da variância real entre fontes
    - Output no CSV: colunas `score_lower_95`, `score_upper_95`
    - Arquivo: `src/scoring/confidence.py` (novo) + `pipeline.py`

---

## Parâmetros Atuais do Modelo (NÃO alterar sem documentar motivo)

```python
JND_FR    = 1.0     # dB — será substituído por array na Fase 3
JND_THD   = 0.05    # % THD
JND_MATCH = 0.5     # dB L/R
THD_THRESHOLD = 0.1 # % — abaixo disso é inaudível
KAPPA     = 0.07    # coeficiente de mascaramento espectral
EPSILON   = 0.1     # regularização do score
SIGMA_SINGLE_SOURCE  = 0.5
SIGMA_THD_EXPECTED   = 0.3
SIGMA_MATCH_EXPECTED = 0.2
ERB_SMOOTHING_SIGMA  = 3
```

---

## Regras para a Ferramenta de AI

1. Nunca alterar os contratos de entrada/saída das funções sem documentar
2. Cada novo coletor herda de BaseCollector
3. Falhas em coletores externos nunca propagam exceção — retornam [] ou None
4. Rodar `python dataset_generator.py --limit 20` após cada fase para validar
5. O acoustic_cache.json do Passe 1 nunca é deletado automaticamente
6. Logs estruturados em output/run_log.jsonl — uma linha JSON por fone processado