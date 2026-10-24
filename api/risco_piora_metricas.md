# Modelo de risco de piora durante a espera (regressao logistica)

- Solicitacoes (sem duplicatas): 919; com piora apos a entrada: 199 (21.7%).
- AUC em validacao cruzada (5 folds x 5 repeticoes): 0.738 (±0.005 entre repeticoes; a incerteza real com 199 positivos e maior, ~±0.04). Acaso = 0.50.
- Idade NAO e usada (decisao do projeto: nenhum dado demografico entra na priorizacao).

## Efeito de cada caracteristica (razao de chances por +1 desvio-padrao; >1 aumenta o risco)

- texto do médico com sinal de gravidade: 2.22
- tempo na fila (controle): 1.56
- CID oncológico (C*): 1.50
- dor (EVA): 1.24
- distância do hospital: 1.12
- nº de comorbidades: 1.01
- texto cita PS/internação: 0.97
- ASA: 0.95
- limitação funcional: 0.94
- risco cirúrgico do procedimento: 0.87

## Calibracao (5 faixas de risco previsto; previsto x observado)

| faixa | n | previsto | observado |
|---|---|---|---|
| 1 | 184 | 10% | 13% |
| 2 | 184 | 13% | 11% |
| 3 | 183 | 17% | 16% |
| 4 | 184 | 25% | 20% |
| 5 | 184 | 54% | 48% |

Probabilidades previstas com tempo de fila fixado em 365 dias para todos. Faixa de risco previsto: min 6% · mediana 16% · max 85%.
Pontos de risco: >=30% = +20 · >=40% = +40 (ver pontos.py). Acima de 30%: 198 solicitacoes; acima de 40%: 135.