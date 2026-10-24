"""Banco de perguntas da area do paciente (2 a 3 por pessoa, escolhidas pelo caso).

ATENCAO: texto ainda NAO revisado por equipe clinica. Revisar antes de uso real.
Uma resposta marcada como `alerta` so avisa o regulador; ela NAO muda a prioridade sozinha.
Uma resposta `urgente` mostra ao paciente a orientacao de procurar atendimento agora.
"""
SN = [("nao", "Não"), ("sim", "Sim")]


def Q(id, texto, opcoes, alerta=(), urgente=()):
    return {"id": id, "texto": texto, "opcoes": [{"valor": v, "rotulo": r} for v, r in opcoes],
            "alerta": list(alerta), "urgente": list(urgente)}


BANCO = {
    "hernia": Q("hernia", "A região da hérnia ficou dura, muito dolorida e não volta ao lugar, ou veio com vômitos?", SN, ["sim"], ["sim"]),
    "vesicula": Q("vesicula", "Teve febre, pele ou olhos amarelados, ou dor forte na parte de cima da barriga?", SN, ["sim"], ["sim"]),
    "varizes": Q("varizes", "Apareceu ferida, vermelhidão ou inchaço novo na perna?", SN, ["sim"]),
    "visao": Q("visao", "Sua visão piorou nas últimas semanas?", [("igual", "Está igual"), ("pior", "Piorou"), ("perda", "Perdi a visão de repente")], ["pior", "perda"], ["perda"]),
    "articulacao": Q("articulacao", "Sua dificuldade para andar ou usar a articulação mudou?", [("igual", "Está igual"), ("pior", "Piorou"), ("melhor", "Melhorou")], ["pior"]),
    "oncologia": Q("oncologia", "Notou algo novo, como sangramento, caroço que cresce ou perda de peso sem motivo?", SN, ["sim"]),
    "urinario": Q("urinario", "Teve dificuldade para urinar, dor forte nas costas ou febre?", SN, ["sim"], ["sim"]),
    "coracao": Q("coracao", "Teve dor no peito, falta de ar ou inchaço nas pernas que piorou?", [("nao", "Não"), ("falta_ar", "Falta de ar ou inchaço"), ("dor_peito", "Dor no peito")], ["falta_ar", "dor_peito"], ["dor_peito"]),
    "diabetes": Q("diabetes", "Nas últimas semanas, teve muita sede, urinou mais que o normal ou a glicemia ficou muito alta?",
                  [("nao", "Não"), ("as_vezes", "Algumas vezes"), ("sempre", "Com frequência")], ["sempre"]),
    "sintomas": Q("sintomas", "Seus sintomas mudaram desde a última atualização?", [("igual", "Estão iguais"), ("pior", "Pioraram"), ("melhor", "Melhoraram")], ["pior"]),
    "geral_ps": Q("geral_ps", "Desde a última atualização, você foi ao pronto-socorro ou ficou internado(a)?",
                  [("nao", "Não"), ("ps", "Fui ao pronto-socorro"), ("internacao", "Fiquei internado(a)")], ["ps", "internacao"]),
}
POR_PROCEDIMENTO = {"PROC001": "visao", "PROC002": "hernia", "PROC003": "hernia", "PROC004": "vesicula", "PROC006": "varizes",
                    "PROC007": "articulacao", "PROC008": "articulacao", "PROC009": "articulacao", "PROC010": "articulacao",
                    "PROC016": "urinario", "PROC017": "urinario", "PROC022": "coracao"}
ONCOLOGICOS = {"PROC011", "PROC012", "PROC013", "PROC015", "PROC018", "PROC020", "PROC023"}


def escolher(r):
    """r: linha da fila detalhada. Devolve de 2 a 3 perguntas: do caso, de uma comorbidade e a geral."""
    chave = "oncologia" if (r.onc or r.procedimento_id in ONCOLOGICOS) else POR_PROCEDIMENTO.get(r.procedimento_id, "sintomas")
    chaves = [chave]
    com = f"{r.comorbidades} {r.cid_secundario}".lower()
    if "dm2" in com or "diabet" in com or bool(r.diabetes_evidenciado):
        chaves.append("diabetes")
    elif ("cardiopatia" in com or "icc" in com) and chave != "coracao":
        chaves.append("coracao")
    return [BANCO[k] for k in chaves + ["geral_ps"]]
