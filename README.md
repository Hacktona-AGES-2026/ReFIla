# ReFila

**A fila mede o tempo de espera. A ReFila mede como a pessoa está agora.**

Solução do **Desafio 1 — Priorização Inteligente da Fila Cirúrgica** · 9ª Hackatona de Engenharia de Software 2026 · Fin-x · PUCRS · Hospital São Lucas.
Dados 100% sintéticos (nenhum paciente real). Data de referência: 23/10/2026.

> **Em uma frase:** a *classe* de urgência (A1 a D, adaptada do SWALIS) é decidida por **regras clínicas legíveis**; os *pontos* de tempo, gravidade e risco previsto só **ordenam dentro da classe**. O sistema propõe, **o regulador decide**, e o motivo fica registrado.

📄 **Decisões, números e limitações: [`DECISOES.md`](DECISOES.md)** · 🧹 Limpeza dos dados: [`api/dataset_limpo/LIMPEZA.md`](api/dataset_limpo/LIMPEZA.md) · 📚 Dataset original: [`README_DATASET.md`](README_DATASET.md)

---

## Rodar em 3 passos

Requisitos: **Python 3.9+** e **Node 18+**. Não precisa de chave de API nem de arquivo `.env`.

**1. API** (terminal 1, porta 8000). Os resultados já vêm calculados no repositório.

```bash
cd api
pip install -r requirements.txt
uvicorn api:app --port 8000
```

**2. Front-end** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

**3. Abra** o endereço que o Vite mostrar (normalmente <http://localhost:5173>). Se a tela mostrar "Não foi possível falar com a API", o passo 1 não está rodando.

### O que testar na demonstração

| Quero ver | Como |
|---|---|
| A fila do regulador | Tela inicial → **Médico ou regulador** → aba **Fila**. Alterne **Com risco previsto** e **Só regras** (a caixa azul explica a diferença). |
| Buscar um paciente | Lupa no topo: nome, protocolo (`SOL-...`), cirurgia ou CID. |
| A decisão com motivo | Abra um paciente → registre a decisão (motivo obrigatório) → aba **Auditoria**. |
| A fila como fluxo | No paciente, lance um **evento** (ex.: pronto-socorro) e veja a nova posição e se mudou de classe. |
| A área do paciente | Tela inicial → **Paciente** → protocolo `SOL-2025-00118` e primeiro nome `Salete`. O paciente **nunca vê a posição**. |
| O relato do paciente | Escreva um relato na caixa "Conte com as suas palavras" → ele aparece no paciente, na tela do regulador, como **pendente** (aceitar como evento ou descartar). |
| Voltar ao zero | Aba **Auditoria** → **Reiniciar demonstração**. |

---

## O que a solução faz

```
dados limpos → sinais de piora (eventos) → CLASSE (regras) → score 0–1000 → fila + justificativa → regulador decide
```

1. **Limpeza dos dados** sem apagar nada por julgamento (CID sem ponto, duplicatas, eventos órfãos viram avisos).
2. **Classe A1 a D por regras** (câncer pelo CID, angina instável, complicação aguda, 2 sinais de piora, dor e limitação).
3. **Dois scores:** só regras e com **risco previsto de piora** (regressão logística, AUC 0,74). O risco soma no máximo 40 pontos e **nunca troca a classe**.
4. **Justificativa em texto** para cada posição, incluindo `DADO AUSENTE: ...` quando falta informação (nunca lida como ausência de gravidade).
5. **Regulador no controle:** decisão com motivo obrigatório, travas para oncológicos, reavaliação por evento novo, lista de "sem atualização" e **lista de investigação** (quem revisar primeiro).
6. **Análise de sensibilidade:** 13 cenários mostram o quanto a posição de cada paciente depende das nossas hipóteses.
7. **Área do paciente:** pergunta personalizada (redigida por LLM, guardada no repositório), relato livre e alertas de urgência **por regras**. O relato **não muda a fila sozinho**.

**Regra de ouro:** nenhum oncológico (CID `C*`) fica abaixo de um paciente sem urgência clínica. As duas ordens passam no verificador oficial:

```bash
cd api
python verificar_fila_priorizada.py fila_priorizada.csv --dataset ..
python verificar_fila_priorizada.py fila_priorizada_so_regras.csv --dataset ..
# esperado: RESULTADO: OK — regra de ouro respeitada e formato válido
```

O **entregável** é [`api/fila_priorizada.csv`](api/fila_priorizada.csv) (`solicitacao_id, posicao, justificativa`).

---

## Estrutura do repositório

| Pasta ou arquivo | O que é |
|---|---|
| `DECISOES.md` | **Abordagem, decisões conscientes, números e limitações** |
| `api/` | Back-end: regras, scores, regressão, API (FastAPI) e CSVs de resultado. Detalhes em [`api/README.md`](api/README.md) |
| `api/priorizar.py`, `pontos.py` | Classe, pesos e fila (única fonte dos pesos: `pontos.py`) |
| `api/risco_piora.py` | Regressão logística da chance de piora |
| `api/regulador.py` | Ferramentas do regulador em linha de comando |
| `api/sensibilidade.py` | Análise de sensibilidade e lista de investigação |
| `api/acolhimento.py`, `gerar_perguntas.py` | Área do paciente e geração das perguntas com LLM |
| `api/api.py` | API usada pelo front |
| `frontend/` | Front-end (React + Vite): telas do regulador e do paciente |
| `fila_cirurgica.csv`, `eventos_clinicos.csv`, `procedimentos.csv`, `referencias/` | Dataset original, sem alterações |
| `verificar_fila_priorizada.py` | Verificador da regra de ouro (fornecido pela organização) |

---

## Recalcular tudo do zero (opcional)

```bash
cd api
python risco_piora.py      # 1) chance de piora
python priorizar.py        # 2) classes, scores e filas
python sensibilidade.py    # 3) faixa de posições e lista de investigação
```

O resultado é idêntico ao que está no repositório.

## Pergunta personalizada com LLM (opcional)

A pergunta aberta da área do paciente foi redigida por um LLM para o caso de cada pessoa e está **guardada em `api/perguntas_pacientes.csv`**, no repositório. Quem clona o projeto vê as perguntas **sem precisar de chave**. Se um paciente não estiver no arquivo, o sistema usa uma pergunta-modelo por especialidade.

Para gerar de novo com a sua chave:

```bash
cd api
echo "LLM_API_KEY=sua_chave" > .env       # o .env está no .gitignore: NUNCA suba a chave
python gerar_perguntas.py --limite 5      # teste
python gerar_perguntas.py --paralelo 2    # todos (2 em paralelo evita limite de uso da API)
```

Opcionais no `.env`: `LLM_MODEL` (padrão `gpt-4o-mini`) e `LLM_BASE_URL` (outro serviço compatível).

**O LLM só pergunta e resume.** Os sinais de alerta (falta de ar, sangramento, febre...) são detectados por **regras**, e o LLM não pode "tranquilizar" um relato que as regras marcaram.

## Testes

```bash
cd frontend && npm test      # testes de interface (parte deles exige a API rodando em localhost:8000)
```

## Variáveis (todas opcionais)

| Variável | Onde | Para quê |
|---|---|---|
| `CORS_ORIGINS` | API | Origens permitidas, separadas por vírgula. Padrão: `http://localhost:5173,http://127.0.0.1:5173` |
| `VITE_API_URL` | Front | Só se a API estiver em outro endereço. Vazio usa o proxy `/api` |
| `API_URL` | Front (Vite) | Endereço da API para o proxy de desenvolvimento. Padrão: `http://localhost:8000` |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | API | Só para gerar perguntas de novo |

---

## Limites conhecidos (resumo; a lista completa está em [`DECISOES.md`](DECISOES.md))

- **Os pesos e as regras de classe são nossos**, a partir do SWALIS e dos dados. **Não foram validados por equipe clínica.**
- As **perguntas geradas por LLM, as perguntas-modelo e a lista de palavras de alerta ainda não foram revisadas por profissional de saúde.** A lista de alertas é por palavras-chave e pode não pegar sinônimos ou erros de digitação. A tela do paciente sempre mostra o aviso de emergência (192/SAMU).
- O login do paciente é de protótipo (protocolo e primeiro nome, com bloqueio de 5 erros em 10 minutos por IP). Os endpoints do regulador **não têm login**. Em produção, exigir autenticação real.
- O modelo de risco usa dados sintéticos (AUC 0,74); a força do texto do médico provavelmente não se repetiria igual em dados reais.
- Dados 100% sintéticos.

## Equipe

Aline Fassina Acevedo, Amanda Matte, Camile Royer Santos, Gabriela Harumi Matsubarra, Rafaela Aguirre Clamer dos Santos e Sofia Martins Eboli.
