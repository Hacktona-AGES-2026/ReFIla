# Relatório de limpeza do dataset

Gerado por `limpar_dataset.py`. Todos os números abaixo foram **medidos nos dados**, não estimados. Dados sintéticos; data de referência 23/10/2026.

**Princípio:** o que é *defeito de formato* foi corrigido no próprio valor. O que é *julgamento* (ex.: "isso parece duplicata") **não apaga nada**: vira uma coluna nova, para o regulador decidir. A fila continua com **941 linhas**; a fila passou de 31 para 47 colunas.

## A. Corrigido no próprio valor (formato)
| # | Onde | Problema | Correção | Linhas afetadas |
|---|---|---|---|---|
| 1 | `fila.cid_principal` | CID às vezes sem ponto (`K409` e `K40.9` são o mesmo código); 26 códigos apareciam com 2 grafias | Padronizado como `K40.9` (ponto depois do 3º caractere). Coluna nova `cid_normalizado` (sem ponto) para comparar | 32 |
| 2 | `fila.prioridade_regulacao` | `Alta`, `Baixa`, `Média` (caixa/acento) | Tudo em minúsculas e sem acento: `alta`, `media`, `baixa` | 23 |
| 3 | `fila.prioridade_regulacao` | Valor vazio | Preenchido com `nao informada` (**não** foi chutada uma prioridade) | 11 |
| 4 | `fila.municipio` | Mesma cidade em grafias diferentes (`VIAMAO`, `osorio`, `Sapucaia do Sul`, `SAPUCAIA DO SUL`) | Uma grafia canônica por município: 62 → 38 nomes distintos | 50 |
| 5 | `fila.nome_paciente` | Mesma pessoa (mesmo `paciente_id`) com nome em MAIÚSCULAS num registro e normal em outro | Uma grafia por `paciente_id` | 5 linhas (5 pacientes) |
| 6 | `eventos` | Eventos **duplicados** (mesma solicitação, tipo, resultado, data e valor; ids diferentes): 6 são cópias exatas e 2 são o mesmo evento registrado com texto/origem diferente | Removida a segunda ocorrência | 8 |
| 7 | `eventos` | Eventos de solicitações que **não estão mais na fila** | Movidos para `eventos_orfaos.csv` (não apagados). Nenhum deles pertence a paciente que ainda tem solicitação na fila | 9 |

## B. Valores ausentes preenchidos (sempre com coluna que avisa)
| Coluna | Como foi preenchida | Coluna-aviso | Linhas |
|---|---|---|---|
| `intensidade_dor_eva` | Mediana de pacientes com o mesmo CID (se o CID não tiver nenhum valor, mediana geral) | `dor_eva_imputada` | 38 |
| `limitacao_funcional` | Valor mais comum entre pacientes com o mesmo CID (senão `leve`) | `limitacao_imputada` | 20 |

## C. Colunas novas (julgamento explícito; nenhuma coluna original foi sobrescrita por elas)
| Coluna | O que diz | Linhas `True`/preenchidas |
|---|---|---|
| `oncologico_pelo_cid` | CID começa com `C` (a regra do desafio, **sem usar a flag manual**) | 177 |
| `biopsia_ultima` | Resultado da última biópsia nos eventos (`positivo`/`negativo`/`inconclusivo`/vazio) | com biópsia registrada |
| `oncologico_confirmado` | CID `C*` **ou** biópsia positiva | 200 |
| `biopsia_positiva_cid_nao_oncologico` | Biópsia positiva, mas o CID não é `C*` (CID provavelmente desatualizado; alguns laudos nem combinam com o CID) | 23 |
| `flag_oncologico_diverge` | `flag_oncologico` diverge do CID: 21 com CID `C*` e flag `nao`; 23 com flag `sim` e CID não `C*` | 44 |
| `piora_observada_nos_eventos` | PS nos últimos 180 d, internação nos últimos 12 meses, progressão em imagem, reavaliação com piora ou piora relatada ao call center | 193 |
| `flag_piora_diverge` | `flag_piora_clinica` desatualizada: 140 com `nao` mas com eventos de piora; 35 com `sim` sem evento registrado | 175 |
| `diabetes_evidenciado` / `flag_diabetico_subnotificado` | Texto, comorbidade ou HbA1c ≥ 6,5 indicam diabetes, mas `flag_diabetico` = `nao` | 32 |
| `duplicata_de` | `solicitacao_id` da solicitação **mais antiga** do mesmo paciente e procedimento (preserva o tempo de espera) | 22 (5 oncológicas) |
| `saida_provavel` | Call center ou observação indicam desistência / cirurgia em outro serviço / convênio (nenhuma é oncológica; 1 delas também é duplicata) | 25 |
| `sem_contato` | Número inexistente ou mudou de endereço | 14 |
| `sugestao_retirar_da_fila` | Duplicata ou saída provável, **nunca para oncológico** (oncológico só gera alerta). É sugestão: o regulador confirma | 41 |

## D. Conferido e **sem problema** (nada a corrigir)
- `dias_em_fila` = 23/10/2026 − `data_entrada_fila` em todas as linhas (0 divergências).
- `cid_descricao` é 1:1 com o CID (1 descrição por código).
- Nenhum evento com data depois de 23/10/2026 (0).
- `paciente_id` dos eventos bate com o da fila (0 divergências).
- `sexo` (F/M) e `uf` (RS) sem valores estranhos (0).
- Mesmo nome em `paciente_id` diferentes: 0 (possível pessoa duplicada em ids diferentes).
- Conflito de município entre linhas do mesmo paciente depois da limpeza: 0.

## E. De propósito **não alterado**
- `asa` (26 vazias) e `distancia_hospital_km` (20 vazias): continuam vazias (não há base para estimar sem inventar). O modelo de risco usa a mediana só internamente.
- **Texto livre** (`justificativa_clinica`, `observacoes`, `descricao`): mantido como veio; os sinais de gravidade são lidos pelo `priorizar.py`, sem alterar o texto.
- **Campos de preparo pré-operatório** (`hba1c_ultima`, `data_hba1c_ultima`, `avaliacao_pre_anestesica`, `exames_pre_op_validos`) e as flags manuais originais: preservados; o desafio os trata como opcionais.
- `eventos.origem` (13 valores como `PS municipal` e `Emergencia HPS`): são origens diferentes, não erros de grafia.
- `procedimentos.csv` (23 linhas) e `referencias/swalis.csv` (5 linhas): sem defeitos encontrados, copiados como vieram.

## Resultado
- `fila_cirurgica_limpa.csv`: 941 linhas, 47 colunas.
- `eventos_clinicos_limpo.csv`: 1488 linhas (de 1505): −8 duplicados, −9 órfãos (em `eventos_orfaos.csv`).
