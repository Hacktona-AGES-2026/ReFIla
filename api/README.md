# Priorização Inteligente da Fila Cirúrgica — Hackatona 2026 (Desafio 1)

Sistema que propõe uma ordem para a fila cirúrgica do Hospital São Lucas. **A classe de urgência (A1 a D, adaptada do SWALIS) é decidida por regras clínicas legíveis; os pontos de tempo e gravidade só ordenam os pacientes dentro da mesma classe.** Cada posição vem com uma justificativa em texto. O sistema propõe, e o regulador decide.

Decisões, números e limitações: [`../DECISOES.md`](../DECISOES.md). Relatório da limpeza dos dados: [`dataset_limpo/LIMPEZA.md`](dataset_limpo/LIMPEZA.md).

> Dados 100% sintéticos (nenhum paciente real). A documentação original do dataset está em `README_DATASET.md` e `dicionario_dados.md`. A visão geral e o passo a passo para rodar o projeto inteiro (API + front) estão no [`README.md`](../README.md) da raiz.

## Como rodar

Requisitos: Python 3.9+.

```bash
pip install -r requirements.txt

python risco_piora.py                                     # 1) regressao: chance de piora (risco_piora.csv)
python priorizar.py                                       # 2) classes + os DOIS scores e as filas
python verificar_fila_priorizada.py fila_priorizada.csv --dataset ..           # 3) confere formato e regra de ouro (ordem com risco)
python verificar_fila_priorizada.py fila_priorizada_so_regras.csv --dataset .. # 4) idem para a ordem so com regras
```

O resultado esperado dos verificadores e `RESULTADO: OK — regra de ouro respeitada e formato válido`.

## Ferramentas do regulador (`regulador.py`)

O sistema propoe; **o regulador decide** e o motivo fica registrado.

```bash
# ver a fila, com filtros (especialidade da cirurgia ou especialidade de apoio)
python regulador.py fila --especialidade urologia --top 10
python regulador.py fila --apoio endocrinologia --top 10      # apoio: endocrinologia, cardiologia, pneumologia, nefrologia
python regulador.py fila --ordem so_regras                    # compara com a ordem sem o risco previsto

# decisao do regulador (motivo obrigatorio; sem --posicao = aceita a proposta)
python regulador.py decidir SOL-2025-00394 --posicao 120 --regulador "Dra. Ana" --motivo "ulcera venosa com sangramento"
python regulador.py fila-final                                # aplica as decisoes -> fila_final_regulador.csv (ja confere no verificador)

# reavaliacao: lanca um evento novo e mostra quem subiu e se mudou de classe
python regulador.py evento SOL-2025-00394 --tipo pronto_socorro --resultado observacao

# lista de "sem atualizacao" (alerta quando passa de metade do prazo SWALIS da classe)
python regulador.py revisao --top 15

# lista de investigacao: quem precisa de REVISAO HUMANA primeiro (nao e a ordem cirurgica)
python regulador.py investigacao --top 10

# area do paciente: relatos pendentes (autodeclaracao; so entram na fila se o regulador aceitar)
python regulador.py mensagens
python regulador.py mensagem-resolver MSG-0001 --aceitar --regulador "Dra. Ana"

python regulador.py reiniciar                                 # apaga eventos/decisoes de teste e recalcula
```

## Area do paciente (`acolhimento.py`)

O paciente **nao ve posicao nem score**. Ele recebe uma pergunta curta, adaptada ao caso, e conta com as proprias palavras se melhorou ou piorou. O relato vira uma **mensagem pendente** para o regulador; **nao altera a fila sozinho**.

```bash
python acolhimento.py pergunta SOL-2026-00489                  # a pergunta que o paciente ve (+ aviso de emergencia)
python acolhimento.py relato SOL-2026-00489 "a dor aumentou e tive febre"
```

- **Funciona sem chave de API.** As perguntas vem de `perguntas_pacientes.csv` (geradas por LLM e guardadas no repo). Se o caso nao estiver la, usa uma pergunta-modelo por especialidade.
- **Opcional, para gerar de novo com LLM:** crie um arquivo `.env` (ja no `.gitignore`) com `LLM_API_KEY=sua_chave` (e, se quiser, `LLM_MODEL=...`) e rode `python gerar_perguntas.py --limite 5` para testar, depois `python gerar_perguntas.py`. **Nunca suba a chave para o GitHub.**
- O LLM so **pergunta e resume**. Os sinais de alerta (falta de ar, sangramento, febre...) sao detectados por **regras**, e o LLM nao pode "tranquilizar" um relato que as regras marcaram.

Travas: o motivo e obrigatorio; **nunca se rebaixa um oncologico**; paciente sem urgencia (classe C ou D) nao pode ficar acima de um oncologico.

## Como funciona

```
dataset_limpo/  ->  sinais de piora (eventos)  ->  CLASSE (regras)  ->  score 0-1000  ->  fila + justificativa
```

1. **Dados limpos** (`dataset_limpo/`): CID padronizado, eventos duplicados e órfãos separados, dor e limitação vazias preenchidas pelo mesmo CID (com coluna avisando). Nada é apagado por julgamento: duplicatas e prováveis saídas viram avisos para o regulador.
2. **Classe** (`priorizar.py`): câncer (CID `C*` ou biópsia positiva), angina instável, CIDs com complicação aguda, sinais de piora nos eventos, dor e limitação definem A1, A2, B, C ou D.
3. **Score** (`pontos.py`): base da classe + tempo de espera + bônus de "esquecido" + gravidade, no máximo 1000. O **segundo score** soma até 40 pontos da chance de piora prevista pela regressão (>= 30% dá +20, >= 40% dá +40). Os extras somam no máximo 150 e as classes ficam ≥ 170 pontos distantes, então ninguém muda de classe por pontos extras.
4. **Texto livre** (`texto.py`): lê expressões de alta precisão no texto do médico (hoje soma o "pedido do médico", +3).

## Arquivos

| Arquivo | Para quê |
|---|---|
| `priorizar.py` | Monta a fila: classifica, pontua (dois scores) e ordena |
| `risco_piora.py` | Regressao logistica: chance de piorar durante a espera (sem idade) |
| `regulador.py` | Filtros por especialidade, decisao do regulador, reavaliacao por evento novo e lista de revisao |
| `sensibilidade.py` | Analise de sensibilidade (13 cenarios): faixa de posicoes de cada paciente e lista de investigacao |
| `acolhimento.py` | Area do paciente: pergunta direcionada, relato e resumo para o regulador (funciona sem chave) |
| `gerar_perguntas.py` | Gera com LLM a pergunta de cada paciente em `perguntas_pacientes.csv` (opcional, precisa de chave) |
| `pontos.py` | Tabela de pontos (única fonte dos pesos) |
| `texto.py` | Leitura do texto livre por expressões, com negação |
| `verificar_fila_priorizada.py` | Verificador da regra de ouro (fornecido pela organização) |
| `fila_priorizada.csv` | **Entregável:** `solicitacao_id, posicao, justificativa` (ordem com o risco previsto de piora) |
| `fila_priorizada_so_regras.csv` | A mesma fila sem os pontos do risco previsto, para o regulador comparar |
| `risco_piora.csv`, `risco_piora_metricas.md` | Probabilidade de piora por solicitacao; AUC, efeito de cada variavel, calibracao |
| `faixa_posicoes.csv` | Posicao minima e maxima de cada paciente nos 13 cenarios, classe possivel e fator que mais move |
| `lista_investigacao.csv` | Quem revisar primeiro: consequencia x (incerteza + desatualizacao), com a pergunta pendente para o regulador |
| `fila_priorizada_detalhada.csv` | Classe, pontos de cada parte, alertas e todas as colunas de apoio |
| `fora_da_fila_para_confirmacao.csv` | 41 duplicatas e prováveis saídas que o regulador confirma |
| `alertas_cadastro.csv` | Biópsia positiva com CID não oncológico e flags que divergem do CID |
| `dataset_limpo/` | Dados limpos, eventos órfãos e `LIMPEZA.md` |
| `fila_cirurgica.csv`, `eventos_clinicos.csv`, `procedimentos.csv`, `referencias/swalis.csv` | Dataset original (não alterado) |
| `../DECISOES.md` | Abordagem, decisões conscientes e limitações (na raiz do repositório) |

## Pontos de partida ajustáveis

Todos os pesos estão em `pontos.py` e as regras de classe em `priorizar.py` (função `classe`). Para mudar quantos sinais de piora sobem um paciente de classe, altere `N_SINAIS_CLASSE`. Os pesos são heurísticos e não foram validados por especialista clínico (ver `../DECISOES.md`).