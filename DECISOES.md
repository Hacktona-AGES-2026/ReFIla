# DECISOES.md — Priorização da fila cirúrgica (Desafio 1)

9ª Hackatona de Engenharia de Software · 2026. Dados 100% sintéticos; data de referência 23/10/2026.

> Os arquivos de código e resultado citados abaixo (`priorizar.py`, `regulador.py`, `fila_priorizada.csv`...) ficam na pasta [`api/`](api/). Como rodar: [`README.md`](README.md).

## Abordagem em uma frase
**A classe de urgência (A1 a D, adaptada do SWALIS) é decidida por regras clínicas legíveis; os pontos de tempo e gravidade só ordenam os pacientes dentro da mesma classe.** O sistema propõe, e o regulador decide.

```
dados limpos -> sinais de piora (eventos) -> CLASSE (regras) -> score 0-1000 -> fila ordenada + justificativa
```

## 1. Limpeza dos dados (detalhe e contagens em `dataset_limpo/LIMPEZA.md`)
- **Defeitos de formato corrigidos no valor:** CID sem ponto (32 linhas), prioridade com caixa/acento (23), município (50), nome (5), 8 eventos duplicados.
- **Julgamento não apaga nada:** duplicatas de solicitação e prováveis saídas (desistência, cirurgia em outro serviço) viram **colunas de aviso**; o regulador decide. Eventos de solicitações que saíram da fila foram para `eventos_orfaos.csv`.
- **Dor (EVA) e limitação vazias** (38 e 20 linhas): mediana (dor) e valor mais comum (limitação) **do mesmo CID**, sempre com coluna avisando (`dor_eva_imputada`, `limitacao_imputada`). Testamos a média no lugar da mediana: muda em média 0,44 ponto de dor e não altera classe; mantivemos a mediana (valor inteiro e estável em CIDs com poucos casos).
- **Prioridade manual vazia (11):** marcada `nao informada`, **não preenchida**. Dor é dado clínico que entra no score; prioridade é uma decisão humana que não vamos inventar.

## 2. Classificação SWALIS (primeira regra que casar)
| Ordem | Condição | Classe |
|---|---|---|
| 1 | CID I20.0 (angina instável; é exemplo de A1 no próprio `swalis.csv`) | A1 |
| 2 | Câncer (CID `C*` ou biópsia positiva) **e** ≥ 2 sinais de piora | A1 |
| 3 | Câncer | A2 |
| 4 | CID de comportamento incerto (D37 a D48, R91) | B |
| 5 | CID cuja descrição indica complicação aguda (K40.0, K40.3, K42.0, K43.0, K80.0, N13.2, I83.2) | B |
| 6 | ≥ 2 sinais de piora | B |
| 7 | Dor ≥ 7 ou limitação grave | B |
| 8 | Dor 4 a 6 ou limitação moderada | C |
| 9 | Demais | D |

- **Sinais de piora** (eventos): reavaliação com piora, progressão em imagem, relato de piora ao call center, ida ao pronto-socorro, internação.
- **Oncologia pelo CID, não pela flag** (a flag diverge do CID em 44 casos).
- Um paciente com câncer **nunca** fica em C ou D, o que garante a regra de ouro pela estrutura.

## 3. Score (0 a 1000)
`score = base da classe + tempo de espera + bônus de esquecido + gravidade` (**score só com regras**). O **score com risco** soma ainda os pontos da regressão (seção 3b). As duas ordens são geradas e o regulador escolhe.

| Parte | Pontos |
|---|---|
| Base da classe | A1 850 · A2 680 · B 480 · C 280 · D 80 |
| Tempo de espera | 0 a 45: linear até 3x o prazo da classe (A1 15 d, A2 21, B 60, C 180, D 360) |
| Bônus de esquecido | +15 se esperou mais de 5x o prazo (só reordena dentro da classe) |
| Gravidade (0 a 50) | Dor 2 por ponto (até 20); limitação grave/moderada/leve 12/6/2; sinais de piora 3 cada (até 9); ASA ≥ 3: 3; diabetes descompensando: 3; pedido do médico no texto: 3 |

- **Trava:** os extras (tempo + gravidade + risco reservado) somam no máximo 150, e as classes ficam ≥ 170 pontos distantes. Ninguém muda de classe por pontos extras. Há um `assert` em `pontos.py` que quebra se alguém mexer num peso e violar isso.
- **Alerta "esquecido":** quem espera mais de 3x o prazo da classe é sinalizado na justificativa (378 pacientes).
- **Diabetes descompensando:** última HbA1c > 8,5% e subida ≥ 1 ponto desde a primeira medida.
- **Idade e outros dados demográficos (sexo, município, distância) não entram** na priorização. Em nossos dados a idade quase não se relaciona com piora (correlação 0,04), e priorizar por idade levantaria questões de equidade.

## 3b. Regressão da chance de piora (segundo score)
- **Modelo:** regressão logística (`risco_piora.py`). Alvo: o paciente teve ida ao PS, internação, progressão em imagem, reavaliação com piora ou piora relatada **depois** de entrar na fila (199 de 919, 21,7%).
- **Só informação da entrada:** CID, dor, limitação, ASA, comorbidades, distância, risco cirúrgico e o texto da justificativa. **Não entram:** idade, eventos, observações, prioridade manual e flags (seria "colar" ou repetir o erro do sistema atual).
- **Tempo:** entra no treino como controle e é fixado em 365 dias na previsão, para o risco não repetir os pontos de tempo de espera.
- **Honestidade:** cada probabilidade vem de modelos que **não viram** aquele paciente (validação cruzada 5x5). **AUC 0,74** (acaso = 0,50; incerteza ~±0,04). Calibração: faixa de maior risco previu 54% e observou 48%.
- **O que mais pesa:** expressão de gravidade no texto do médico (59% dos pacientes com ela pioraram, contra 15%), tempo na fila, câncer e dor. **Cuidado:** os dados são sintéticos, então a força do texto provavelmente não se repetiria igual em dados reais.
- **Pontos:** chance prevista >= 30% soma +20; >= 40% soma +40 (136 pacientes com +40 e 65 com +20). Piora **já observada** conta nas regras (classe e gravidade), não no risco previsto, para a comparação entre os dois scores ser limpa.
- **Nunca muda a classe:** os pontos de risco só reordenam dentro da classe. Ambas as ordens passam no verificador.

## 3c. Humano com a última palavra (`regulador.py`)
- O regulador vê as duas ordens, aceita ou **move um paciente** e **escreve o motivo**; tudo vai para `decisoes_regulador.csv` (quem, quando, posição proposta, posição final, motivo). Esse registro é a auditoria.
- **Travas:** motivo obrigatório; nunca se rebaixa um oncológico; paciente sem urgência (C ou D) não passa à frente de um oncológico. A `fila_final_regulador.csv` é conferida pelo verificador.
- **Filtros por especialidade:** da cirurgia (coluna `especialidade`) e **de apoio** (ex.: endocrinologia vê quem tem diabetes, com destaque aos descompensados; cardiologia, pneumologia e nefrologia por comorbidades). É uma visão extra; preparo pré-operatório continua fora do escopo.
- **Reavaliação por evento novo:** `regulador.py evento` lança um evento, recalcula a fila inteira e mostra a nova posição, se mudou de classe e quantos foram ultrapassados. Demonstra a fila como fluxo.
- **Lista de revisão ("sem atualização"):** cada classe tem um intervalo de atualização igual à **metade do prazo SWALIS** (A1 7,5 d, A2 10,5 d, B 30 d, C 90 d, D 180 d). Passou disso, o paciente fica `ATRASADO`; a lista é ordenada por quantas vezes passou do intervalo. Com 7 dias fixos, 93% da fila ficaria em alerta, o que não serve como alerta. Mesmo com o intervalo por classe, 536 de 900 estão atrasados (a prioridade manual nunca foi revisada em 805 casos), o que é um achado sobre o processo atual.

## 3d. E se a posição estiver errada? (`sensibilidade.py`)
- **Análise de sensibilidade, não probabilidade:** a fila é recalculada em 13 cenários, cada um mudando **uma** hipótese defensável: 1 ou 3 sinais de piora para subir de classe; biópsia positiva sem câncer no CID **não** tratada como câncer; flag oncológico do cadastro também valendo; dor e limitação preenchidas por estimativa, um nível acima ou abaixo; sem os pontos da regressão; pesos de tempo e gravidade ×0,8 ou ×1,15; sem o "pedido do médico". O cenário base reproduz exatamente a fila oficial (o script confere isso e para se não bater).
- **Resultado por paciente** (`faixa_posicoes.csv`): posição oficial, menor e maior posição, classe mais e menos grave possíveis e o fator que mais move. Faixa até 20 posições = **robusta**, até 100 = **moderada**, acima disso = **instável**. Nos dados: 116 robustas, 609 moderadas e 175 instáveis; 157 pacientes mudam de classe em algum cenário.
- **O que a faixa significa:** mostra quanto a posição depende das hipóteses adotadas. Não é chance de acerto e as variações não são previsões clínicas.
- **Lista de investigação** (`lista_investigacao.csv`): **não é a ordem cirúrgica.** Diz quem precisa de revisão humana primeiro, por `consequência × (0,6 × incerteza + 0,4 × desatualização)`. A consequência vem da classe mais grave possível (oncológico = máxima), a incerteza da largura da faixa de posições e a desatualização de quantas vezes o paciente passou do intervalo de revisão. Os pesos 0,6 e 0,4 são nossos, heurísticos. Cada linha traz a **pergunta pendente** (ex.: "confirmar laudo da biópsia").
- **Limites:** os cenários são escolhidos por nós e não esgotam as hipóteses possíveis; a análise não cobre eventos com data anterior à entrada na fila.

## 3e. Área do paciente com LLM (`acolhimento.py`, `gerar_perguntas.py`)
- **O paciente não vê posição nem score.** A posição muda a cada evento e não é promessa de data; mostrar o número geraria ansiedade e falsa expectativa. Ele vê o status do acompanhamento, um aviso de emergência (192/SAMU) e perguntas sobre o próprio caso.
- **O LLM só pergunta e resume.** Não diagnostica, não dá conselho, não diz se algo é grave, não cita o nome do diagnóstico e não decide urgência. Cada pergunta é gerada a partir de dados mínimos (procedimento, especialidade, diagnóstico, tempo na fila, dor, limitação e tipos dos últimos eventos), **sem nome, id, município ou datas**.
- **Perguntas geradas antes e guardadas** em `api/perguntas_pacientes.csv` (900 perguntas, modelo `gpt-4o-mini`): o repositório roda sem chave de API e um profissional de saúde pode **revisar** o arquivo antes de ele chegar ao paciente. Sem LLM, há perguntas-modelo por especialidade (rascunho nosso). A tela do paciente informa que a pergunta foi redigida com apoio de inteligência artificial.
- **Alertas por regras, não por LLM:** termos como falta de ar, dor no peito e sangramento acendem o alerta por regras (com tratamento de negação: "sem febre"). Se o LLM classificar como melhora um relato que as regras marcaram, vale a regra. A lista é por palavras-chave: pode não pegar sinônimos nem erros de digitação, e é nossa, sem validação clínica. Por isso a tela sempre mostra o aviso de emergência, tenha alerta ou não.
- **Autodeclaração não muda a urgência sozinha:** o relato entra como mensagem pendente; o regulador aceita (vira evento `contato_telefonico/relata_piora` ou `relata_melhora`) ou descarta. Um único sinal de piora também não muda a classe (são necessários 2).
- **Limites:** não testamos com pacientes reais; **as 900 perguntas, as perguntas-modelo e a lista de termos de alerta ainda não foram revisadas por profissionais de saúde**; um LLM pode errar a linguagem ou os sinais de alerta; a chave de API nunca vai ao repositório.

## 3f. Dados ausentes: o que faltou e o que fizemos
**Regra geral: ausência de informação nunca é lida como ausência de gravidade.** Quando algo falta, o sistema usa um valor típico do mesmo CID (ou não dá pontos, nunca pontos negativos) e **escreve isso na justificativa** (`DADO AUSENTE: ...`) e na tela do regulador (Alertas para conferir). A posição é a mesma com ou sem o aviso; o aviso diz ao humano onde a posição se apoia numa estimativa.

| Dado ausente | Casos na fila | O que fazemos | Onde aparece |
|---|---|---|---|
| Dor (EVA) vazia | 34 | Mediana da dor do mesmo CID (não zero) | Justificativa, alerta no front, coluna `dor_eva_imputada` |
| Limitação funcional vazia | 19 | Valor mais comum do mesmo CID | Justificativa, alerta no front, coluna `limitacao_imputada` |
| ASA vazio | 24 | Sem pontos de ASA (3 pontos no máximo); não se assume "baixo risco" | Justificativa e alerta no front |
| Diabético sem HbA1c | 78 | Não dá para avaliar descompensação: sem os +3 pontos, e o aviso diz isso | Justificativa e alerta no front |
| Prioridade manual vazia | 10 | Marcada `nao informada`; não é usada no score | `LIMPEZA.md` |
| Distância vazia | ~20 | Não entra no score | `LIMPEZA.md` |
| Observações vazias | ~395 | Normal (campo opcional); o texto do médico não tem lacunas | n/d |
| Informação conflitante (biópsia positiva com CID não oncológico; flags que divergem do CID) | 23 e 44 | Caso mais seguro (câncer), com aviso "conferir cadastro" | Justificativa, `alertas_cadastro.csv`, lista de investigação |

- **Quanto isso mexe na fila:** a análise de sensibilidade (seção 3d) testa dor e limitação 2 pontos ou um nível acima e abaixo. As posições que dependem delas aparecem na `lista_investigacao.csv`, com a pergunta "registrar a dor real".
- **Limite:** a mediana do CID é uma estimativa, não uma medida. Em produção, o certo é obter o dado.

## 3g. Front-end (`frontend/`)
- **Duas entradas:** regulador (fila com busca, filtros, revisão, auditoria, decisão com motivo, lançamento de eventos) e paciente (acompanhamento sem posição, perguntas curtas e relato livre).
- **As duas ordens lado a lado:** o regulador alterna entre **com risco previsto** e **só regras**; uma caixa explica cada uma e as setas ▲ e ▼ mostram quem mudou 10 posições ou mais por causa do risco.
- **Busca de paciente** no topo (nome, protocolo, cirurgia ou CID, sem diferenciar acentos).
- **Limites:** o login do paciente é de protótipo (protocolo e primeiro nome, 5 erros em 10 minutos bloqueiam o IP) e os endpoints do regulador não têm login. Em produção, autenticação real nos dois.

## 4. Texto livre (`justificativa_clinica`, `observacoes`)
- Lemos o texto por **expressões de alta precisão**, com tratamento de negação. Palavras soltas como "obstru" foram descartadas porque pegam "sintomas obstrutivos moderados".
- **Hoje o texto só soma o "pedido do médico" (+3, 29 pacientes)**: é uma opinião, não um fato clínico, então não muda a classe.
- Expressões de gravidade (ex.: "encarceramento", "perda ponderal") estão implementadas em `texto.py` (nível 1 e 2), mas **ainda não alteram a classe**. Uma simulação indicou 79 pacientes que mudariam de classe; preferimos não ligar sem revisão clínica.

## 5. Decisões conscientes (onde nos afastamos do óbvio)
- **Biópsia positiva com CID não oncológico (23 pacientes)** é tratada como câncer (A1/A2), porque deixar um caso confirmado em D por causa de um CID desatualizado seria perigoso. A justificativa traz o aviso "conferir cadastro" e a lista está em `alertas_cadastro.csv`. Alguns laudos nem combinam com o CID, então pode ser erro de cadastro.
- **Prioridade manual não é usada** no score, porque ela é justamente o que queremos melhorar: dos 291 pacientes "alta", 104 caíram para C ou D; dos 341 "baixa", 46 subiram para A1 ou A2.
- **2 sinais de piora** (e não 1) para subir de classe: evita que uma ida isolada ao PS mude o bloco.

## 6. O que ficou fora da fila (41 solicitações, `fora_da_fila_para_confirmacao.csv`)
17 duplicatas (mesmo paciente e procedimento; fica a mais antiga, para preservar o tempo de espera) e 25 saídas prováveis (1 delas também duplicada). **Nenhuma é oncológica**: para oncológicos só geramos alerta. O regulador confirma.

## 7. Resultado
- 941 solicitações → **900 posições**: A1 36 · A2 167 · B 229 · C 211 · D 257. As duas ordens (com e sem risco) passam no verificador oficial.
- Verificador oficial: **OK**. Posição mediana dos oncológicos (CID `C*`): 113 de 900; 100% no primeiro terço.
- Pacientes sem urgência clínica no último terço: 95%.

## 8. Limitações (honestidade)
- **Os pesos são heurísticos**: as classes e os prazos vêm do SWALIS, mas os valores de cada ponto foram escolhidos por nós e **não foram validados por especialista clínico**. Em produção seriam calibrados com reguladores e cirurgiões. Como os pontos só ordenam dentro da classe, o impacto de um peso inadequado é limitado.
- **A decisão que mais pesa é a classe**, e as regras de classe também são nossas, a partir do SWALIS e dos dados.
- Eventos anteriores à entrada na fila (22 sinais de PS ou internação) **também contam** como sinal de piora nas regras (a regressão usa só os posteriores à entrada).
- Todo ida ao PS e toda internação contam como piora, mesmo as "atendido_liberado".
- A leitura do texto é por expressões regulares e pode errar em redações incomuns.
- Não há histórico de posições no dataset (é uma foto de um dia), então o conceito de "paciente ultrapassado várias vezes" só pode ser tratado aproximadamente, pelo tempo de espera.

- **Área do paciente:** as 900 perguntas geradas por LLM, as perguntas-modelo e a lista de palavras de alerta não foram revisadas por profissionais de saúde (seção 3e). O login do paciente é de protótipo e os endpoints do regulador não têm login (seção 3g).

## 9. Próximos passos
1. **Revisão clínica** das regras de classe, dos pesos, das perguntas do paciente e da lista de palavras de alerta, e calibração dos pesos com reguladores e cirurgiões (hoje são heurísticos).
2. **Autenticação real** para o regulador e para o paciente.
3. Agente leitor (LLM) para o texto livre, com a evidência citada para o humano confirmar.
4. Ligar as expressões de gravidade do texto à classe, após revisão clínica (hoje elas só entram na regressão).
5. Guardar a posição a cada reordenação e dar bônus a quem foi ultrapassado muitas vezes.
6. Auditoria de equidade da fila (município, distância, sexo).