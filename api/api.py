"""API HTTP da ReFila: leva para o navegador as ferramentas do regulador.py.

Uso (na mesma pasta do priorizar.py):  uvicorn api:app --reload --host 0.0.0.0
"""
import datetime as dt
import os
import time
import unicodedata
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import acolhimento as AC
import perguntas as PG
import pontos as P
import regulador as R

DECISOES = "decisoes_regulador.csv"
EVENTOS_NOVOS = "eventos_novos.csv"
EVENTOS_LIMPOS = "dataset_limpo/eventos_clinicos_limpo.csv"
FILA_LIMPA = "dataset_limpo/fila_cirurgica_limpa.csv"
FORA_DA_FILA = "fora_da_fila_para_confirmacao.csv"
RESPOSTAS = "respostas_paciente.csv"
RELATOS = AC.MENSAGENS          # relatos em texto livre do paciente (pendentes ate o regulador decidir)
INVESTIGACAO = "lista_investigacao.csv"
ORDENS = list(R.ARQ_ORDEM)
LIMITE_REVISAO = 60

app = FastAPI(title="ReFila")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class NovoEvento(BaseModel):
    tipo: str
    resultado: str
    descricao: str = "evento lancado pelo regulador"
    valor: Optional[float] = None


class Decisao(BaseModel):
    motivo: str = Field(min_length=1)
    regulador: str = "regulador"
    posicao: Optional[int] = None
    ordem: str = "com_risco"


def registros(df):
    return df.astype(object).where(df.notna(), None).to_dict("records")


def ler_csv(caminho, **kwargs):
    return pd.read_csv(caminho, **kwargs) if os.path.exists(caminho) else pd.DataFrame()


def detalhada():
    if not os.path.exists(R.DET):
        raise HTTPException(503, "Rode antes: python risco_piora.py && python priorizar.py")
    return pd.read_csv(R.DET)


def validar_ordem(ordem):
    if ordem not in ORDENS:
        raise HTTPException(422, f"ordem invalida. Opcoes: {', '.join(ORDENS)}")


def paciente(d, solicitacao_id):
    linha = d[d.solicitacao_id == solicitacao_id]
    if linha.empty:
        raise HTTPException(404, "solicitacao nao esta na fila")
    return linha.iloc[0]


def eventos():
    e = pd.concat([ler_csv(EVENTOS_LIMPOS), ler_csv(EVENTOS_NOVOS)], ignore_index=True)
    e["data_evento"] = pd.to_datetime(e.data_evento)
    return e


def filtrar(d, especialidade, apoio):
    if especialidade:
        k = R.sem_acento(especialidade)
        d = d[d.especialidade.map(R.sem_acento).str.contains(k) | d.procedimento.map(R.sem_acento).str.contains(k)]
    if not apoio:
        return d
    if apoio not in R.APOIO:
        raise HTTPException(422, f"apoio invalido. Opcoes: {', '.join(R.APOIO)}")
    comorbidades = (d.comorbidades.fillna("") + " " + d.cid_secundario.fillna("")).map(R.sem_acento)
    precisa = comorbidades.str.contains(R.APOIO[apoio])
    if apoio == "endocrinologia":
        precisa |= d.diabetes_descomp
    if apoio == "cardiologia":
        precisa |= d.asa.fillna(0) >= 3
    return d[precisa]


def alertas(r):
    lista = []
    if r.biopsia_positiva_cid_nao_oncologico:
        lista.append(f"Biopsia positiva, mas o CID {r.cid_principal} nao e oncologico. Conferir cadastro.")
    if r.flag_oncologico_diverge:
        lista.append(f"Flag oncologico '{r.flag_oncologico}' diverge do CID.")
    if r.flag_piora_diverge:
        lista.append("Flag de piora clinica desatualizada em relacao aos eventos.")
    if r.flag_diabetico_subnotificado:
        lista.append("Diabetes no texto, comorbidade ou HbA1c, mas a flag diz 'nao'.")
    if r.dor_eva_imputada:
        lista.append("Dor (EVA) estava vazia e foi preenchida pela mediana do mesmo CID.")
    if r.limitacao_imputada:
        lista.append("Limitacao funcional estava vazia e foi preenchida pelo valor mais comum do CID.")
    if pd.isna(r.asa):
        lista.append("ASA nao informado: ficou sem pontos de ASA (ausencia nao significa baixo risco).")
    if (r.flag_diabetico == "sim" or r.diabetes_evidenciado) and pd.isna(r.hba1c_ultima):
        lista.append("Diabetes sem HbA1c registrada: descompensacao nao pode ser avaliada.")
    if r.sem_contato:
        lista.append("Sem contato: numero inexistente ou mudou de endereco.")
    return lista


def composicao(r, ordem):
    partes = [
        {"label": f"Base da classe {r.classe}", "points": r.pts_base},
        {"label": f"Tempo de espera ({r.dias_em_fila / P.PRAZO[r.classe]:.1f}x o prazo)", "points": r.pts_tempo},
        {"label": "Bonus de esquecido (mais de 5x o prazo)", "points": r.pts_esquecido},
        {"label": "Gravidade (dor, limitacao, sinais de piora, ASA)", "points": r.pts_grav},
    ]
    if ordem == "com_risco":
        risco = "" if pd.isna(r.prob_piora) else f" ({r.prob_piora:.0%})"
        partes.append({"label": f"Risco previsto de piora{risco}", "points": r.pts_risco})
    return [{**p, "points": round(float(p["points"]), 1)} for p in partes]


@app.get("/opcoes")
def opcoes():
    d = detalhada()
    return {
        "ordens": ORDENS,
        "especialidades": sorted(d.especialidade.dropna().unique()),
        "apoio": list(R.APOIO),
        "eventos": R.EVENTOS,
        "prazos": P.PRAZO,
    }


@app.get("/fila")
def fila(ordem: str = "com_risco", especialidade: str = "", apoio: str = ""):
    validar_ordem(ordem)
    d = filtrar(detalhada(), especialidade, apoio).sort_values(R.POS[ordem])
    return [{
        "id": r.solicitacao_id,
        "posicao": int(r[R.POS[ordem]]),
        "nome": r.nome_paciente,
        "procedimento": r.procedimento,
        "cid": r.cid_principal,
        "classe": r.classe,
        "score": round(float(r[R.SCORE[ordem]])),
        "mudanca_pelo_risco": int(r.mudanca_pelo_risco),
        "oncologico": bool(r.onc),
        "esquecido": bool(r.esquecido),
        "diabetes_descomp": bool(r.diabetes_descomp),
        "conferir_cadastro": bool(r.biopsia_positiva_cid_nao_oncologico),
    } for _, r in d.iterrows()]


@app.get("/pacientes/{solicitacao_id}")
def detalhe(solicitacao_id: str, ordem: str = "com_risco"):
    validar_ordem(ordem)
    r = paciente(detalhada(), solicitacao_id)
    justificativas = pd.read_csv(R.ARQ_ORDEM[ordem]).set_index("solicitacao_id").justificativa
    e = eventos()
    decisoes = ler_csv(DECISOES)
    if not decisoes.empty:
        decisoes = decisoes[decisoes.solicitacao_id == solicitacao_id]
    return {
        "id": r.solicitacao_id,
        "nome": r.nome_paciente,
        "idade": int(r.idade),
        "municipio": r.municipio,
        "procedimento": r.procedimento,
        "especialidade": r.especialidade,
        "cid": r.cid_principal,
        "cid_descricao": r.cid_descricao,
        "classe": r.classe,
        "prazo_dias": P.PRAZO[r.classe],
        "motivo_classe": r.motivo,
        "dias_em_fila": int(r.dias_em_fila),
        "posicao": int(r[R.POS[ordem]]),
        "score": round(float(r[R.SCORE[ordem]])),
        "oncologico": bool(r.onc),
        "prioridade_manual": r.prioridade_regulacao,
        "justificativa": justificativas.get(solicitacao_id, ""),
        "composicao_score": composicao(r, ordem),
        "alertas": alertas(r),
        "justificativa_clinica": None if pd.isna(r.justificativa_clinica) else r.justificativa_clinica,
        "observacoes": None if pd.isna(r.observacoes) else r.observacoes,
        "eventos": registros(e[e.solicitacao_id == solicitacao_id]
                             .sort_values("data_evento", ascending=False)
                             .assign(data_evento=lambda x: x.data_evento.dt.date.astype(str))),
        "decisoes": registros(decisoes),
        "relatos_paciente": registros(ler_csv(RELATOS).query("solicitacao_id == @solicitacao_id").iloc[::-1].head(10)) if os.path.exists(RELATOS) else [],
        "respostas_paciente": registros(ler_csv(RESPOSTAS).query("solicitacao_id == @solicitacao_id").iloc[::-1].head(10)) if os.path.exists(RESPOSTAS) else [],
    }


@app.post("/pacientes/{solicitacao_id}/eventos")
def lancar_evento(solicitacao_id: str, novo: NovoEvento):
    antes = detalhada()
    r = paciente(antes, solicitacao_id)
    if novo.resultado not in R.EVENTOS.get(novo.tipo, []):
        raise HTTPException(422, "tipo/resultado invalidos")
    n = len(ler_csv(EVENTOS_NOVOS))
    pd.DataFrame([{
        "evento_id": f"EVT-NOVO-{n + 1:04d}", "solicitacao_id": solicitacao_id, "paciente_id": r.paciente_id,
        "data_evento": dt.date.today().isoformat(), "tipo_evento": novo.tipo, "resultado": novo.resultado,
        "valor_numerico": novo.valor, "descricao": novo.descricao, "origem": "regulador",
    }]).to_csv(EVENTOS_NOVOS, mode="a", header=n == 0, index=False)
    R.rodar_priorizar()
    depois = detalhada()
    x = depois.merge(antes[["solicitacao_id", "classe", "posicao"]], on="solicitacao_id", suffixes=("", "_antes"))
    p = x[x.solicitacao_id == solicitacao_id].iloc[0]
    return {
        "posicao_antes": int(p.posicao_antes),
        "posicao_depois": int(p.posicao),
        "classe_antes": p.classe_antes,
        "classe_depois": p.classe,
        "ultrapassados": int(max(p.posicao_antes - p.posicao, 0)),
        "mudaram_de_classe": int((x.classe != x.classe_antes).sum()),
    }


@app.post("/pacientes/{solicitacao_id}/decisao")
def decidir(solicitacao_id: str, decisao: Decisao):
    validar_ordem(decisao.ordem)
    d = detalhada()
    r, coluna = paciente(d, solicitacao_id), R.POS[decisao.ordem]
    proposta = int(r[coluna])
    final = decisao.posicao or proposta
    if not 1 <= final <= len(d):
        raise HTTPException(422, f"Posicao deve estar entre 1 e {len(d)}.")
    if r.onc and final > proposta:
        raise HTTPException(422, "Nunca se rebaixa um paciente oncologico.")
    ultimo_onc = int(d[d.onc][coluna].max())
    if not r.onc and r.classe in ("C", "D") and final <= ultimo_onc:
        raise HTTPException(422, f"Paciente sem urgencia (classe {r.classe}) nao pode passar a frente de um "
                                 f"oncologico (o ultimo esta na posicao {ultimo_onc}).")
    registro = {
        "data_hora": dt.datetime.now().isoformat(timespec="seconds"), "regulador": decisao.regulador.strip(),
        "solicitacao_id": solicitacao_id, "ordem_usada": decisao.ordem, "classe": r.classe,
        "posicao_proposta": proposta, "posicao_final": final, "motivo": decisao.motivo.strip(),
    }
    pd.DataFrame([registro]).to_csv(DECISOES, mode="a", header=not os.path.exists(DECISOES), index=False)
    return registro


@app.get("/revisao")
def revisao():
    d = detalhada()
    e = eventos()
    referencia = max(R.REF, e.data_evento.max())
    ultima = pd.concat([d.solicitacao_id.map(e.groupby("solicitacao_id").data_evento.max()),
                        pd.to_datetime(d.data_ultima_revisao_prioridade),
                        pd.to_datetime(d.data_entrada_fila)], axis=1).max(axis=1)
    d["dias_sem_atualizar"] = (referencia - ultima).dt.days
    d["intervalo"] = d.classe.map(P.PRAZO) / 2
    d["vezes_acima"] = (d.dias_sem_atualizar / d.intervalo).round(1)
    atrasados = d[d.vezes_acima > 1].sort_values(["vezes_acima", "posicao"], ascending=[False, True])
    return {
        "total": len(d),
        "atrasados": len(atrasados),
        "lista": [{
            "id": r.solicitacao_id, "nome": r.nome_paciente, "classe": r.classe, "posicao": int(r.posicao),
            "dias_sem_atualizar": int(r.dias_sem_atualizar), "intervalo": r.intervalo, "vezes_acima": r.vezes_acima,
        } for _, r in atrasados.head(LIMITE_REVISAO).iterrows()],
    }


def motivo_fora(r):
    motivos = [f"duplicata de {r.duplicata_de}"] if pd.notna(r.duplicata_de) else []
    if pd.notna(r.saida_provavel):
        motivos.append(r.saida_provavel)
    return "; ".join(motivos)


@app.get("/auditoria")
def auditoria():
    d = detalhada()
    fora = ler_csv(FORA_DA_FILA)
    novos = ler_csv(EVENTOS_NOVOS)
    return {
        "qualidade_dados": {
            "recebidas": len(ler_csv(FILA_LIMPA)),
            "fora_da_fila": len(fora),
            "alertas_cadastro": int((d.biopsia_positiva_cid_nao_oncologico | d.flag_oncologico_diverge).sum()),
            "dor_imputada": int(d.dor_eva_imputada.sum()),
            "esquecidos": int(d.esquecido.sum()),
        },
        "pacientes_na_fila": len(d),
        "classes": d.classe.value_counts().sort_index().to_dict(),
        "fora_da_fila": [{"id": r.solicitacao_id, "nome": r.nome_paciente, "procedimento": r.procedimento,
                          "motivo": motivo_fora(r)} for _, r in fora.iterrows()],
        "decisoes": registros(ler_csv(DECISOES).iloc[::-1]),
        "eventos_novos": registros(novos.iloc[::-1]) if not novos.empty else [],
    }



class ResolverRelato(BaseModel):
    acao: str = Field(pattern="^(aceitar|descartar)$")
    regulador: str = "regulador"


@app.post("/relatos/{mensagem_id}/resolver")
def resolver_relato(mensagem_id: str, r: ResolverRelato):
    """Relato do paciente e autodeclaracao: so vira evento (e mexe na fila) se o regulador aceitar."""
    m = ler_csv(RELATOS)
    i = m.index[m.mensagem_id == mensagem_id] if not m.empty else []
    if len(i) == 0 or m.loc[i[0], "status"] != "pendente":
        raise HTTPException(404, "Relato nao encontrado ou ja resolvido.")
    i = i[0]
    resultado = None
    if r.acao == "aceitar":
        resultado = lancar_evento(m.loc[i, "solicitacao_id"], NovoEvento(
            tipo="contato_telefonico", resultado=m.loc[i, "evento_sugerido"],
            descricao=f"relato do paciente validado por {r.regulador.strip() or 'regulador'}: {str(m.loc[i, 'resumo'])[:120]}"))
    m.loc[i, "status"] = "aceita" if r.acao == "aceitar" else "descartada"
    m.to_csv(RELATOS, index=False)
    return {"status": m.loc[i, "status"], "resultado": resultado}


@app.get("/investigacao")
def investigacao(top: int = 20):
    """Quem precisa de revisao humana primeiro (NAO e a ordem cirurgica). Veja sensibilidade.py."""
    if not os.path.exists(INVESTIGACAO):
        raise HTTPException(503, "Rode antes: python sensibilidade.py")
    return registros(pd.read_csv(INVESTIGACAO).head(max(1, min(top, 200))))


# ---------------- Area do paciente: nunca devolve posicao, classe, score nem prioridade ----------------
def _sa(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn").strip()


class Acesso(BaseModel):
    protocolo: str
    primeiro_nome: str


class Resposta(BaseModel):
    id: str
    valor: str


class Respostas(Acesso):
    respostas: list[Resposta]


class Relato(Acesso):
    texto: str = Field(min_length=3, max_length=1000)


FALHAS, MAX_FALHAS, JANELA_S = {}, 5, 600     # 5 erros em 10 min bloqueiam o IP (em memoria)


def autenticar(acesso, request):
    """Prototipo: protocolo + primeiro nome. Em producao, trocar por login real (ex.: gov.br)."""
    ip, agora = request.client.host if request.client else "?", time.time()
    recentes = [t for t in FALHAS.get(ip, []) if agora - t < JANELA_S]
    if len(recentes) >= MAX_FALHAS:
        raise HTTPException(429, "Muitas tentativas. Aguarde alguns minutos e tente de novo.")
    d = detalhada()
    linha = d[d.solicitacao_id == acesso.protocolo.strip().upper()]
    if linha.empty or _sa(linha.iloc[0].nome_paciente).split(" ")[0] != _sa(acesso.primeiro_nome).split(" ")[0]:
        FALHAS[ip] = recentes + [agora]
        raise HTTPException(401, "Não encontramos uma solicitação com esse protocolo e nome. Confira os dados.")
    FALHAS[ip] = []
    return linha.iloc[0]


@app.post("/paciente/entrar")
def paciente_entrar(acesso: Acesso, request: Request):
    r = autenticar(acesso, request)
    e = eventos()
    ultimo = e[e.solicitacao_id == r.solicitacao_id].data_evento.max()
    revisada = None if r.data_ultima_revisao_prioridade == r.data_entrada_fila else r.data_ultima_revisao_prioridade
    return {
        "protocolo": r.solicitacao_id, "nome": r.nome_paciente, "procedimento": r.procedimento,
        "data_entrada": r.data_entrada_fila, "dias_em_fila": int(r.dias_em_fila), "contado_ate": R.REF.isoformat(),
        "revisada_em": revisada, "ultimo_evento": None if pd.isna(ultimo) else ultimo.date().isoformat(),
        "perguntas": PG.escolher(r),
        "pergunta_aberta": pergunta_aberta(r.solicitacao_id),
    }


def pergunta_aberta(solicitacao_id):
    """Pergunta personalizada (gerada por LLM e guardada em perguntas_pacientes.csv; sem chave cai na pergunta-modelo).
    No login NAO chamamos o LLM na hora: a pagina nao pode ficar lenta nem depender de internet."""
    texto, origem = AC.pergunta_para(solicitacao_id, usar_llm_na_hora=False)
    return {"texto": texto, "origem": origem, "aviso": AC.AVISO_EMERGENCIA}


@app.post("/paciente/relato")
def paciente_relato(env: Relato, request: Request):
    r = autenticar(env, request)
    texto = env.texto.strip()
    if len(texto) < 3:
        raise HTTPException(422, "Escreva um pouco mais para a equipe entender.")
    m = AC.registrar_relato(r.solicitacao_id, texto)
    # "urgente" vem das REGRAS (falta de ar, sangramento...), nunca so do LLM
    return {"recebido": True, "urgente": bool(m.sinal_de_alerta)}


@app.post("/paciente/respostas")
def paciente_respostas(env: Respostas, request: Request):
    r = autenticar(env, request)
    banco = {q["id"]: q for q in PG.escolher(r)}
    linhas, urgente = [], False
    for x in env.respostas:
        q = banco.get(x.id)
        if q is None or x.valor not in [o["valor"] for o in q["opcoes"]]:
            raise HTTPException(422, "Resposta inválida.")
        urgente |= x.valor in q["urgente"]
        rotulo = next(o["rotulo"] for o in q["opcoes"] if o["valor"] == x.valor)
        linhas.append({"data_hora": dt.datetime.now().isoformat(timespec="seconds"), "solicitacao_id": r.solicitacao_id,
                       "pergunta": q["texto"], "resposta": rotulo, "alerta": x.valor in q["alerta"]})
    if not linhas:
        raise HTTPException(422, "Responda pelo menos uma pergunta.")
    pd.DataFrame(linhas).to_csv(RESPOSTAS, mode="a", header=not os.path.exists(RESPOSTAS), index=False)
    return {"recebidas": len(linhas), "alertas": sum(l["alerta"] for l in linhas), "urgente": urgente}


@app.post("/reiniciar")
def reiniciar():
    for arquivo in (EVENTOS_NOVOS, DECISOES, RESPOSTAS, RELATOS, "fila_final_regulador.csv"):
        if os.path.exists(arquivo):
            os.remove(arquivo)
    R.rodar_priorizar()
    return {"ok": True}
