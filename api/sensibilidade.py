"""sensibilidade.py — quanto a posicao de cada paciente depende das hipoteses adotadas?

Roda a fila varias vezes com variacoes clinicamente defensaveis e guarda, para cada paciente,
a menor e a maior posicao. Depois monta a LISTA DE INVESTIGACAO: quem precisa de revisao humana
primeiro (nao e a ordem cirurgica!).

ATENCAO: isto e ANALISE DE SENSIBILIDADE. A faixa de posicoes NAO e probabilidade de acerto
e as variacoes NAO sao previsoes clinicas: mostram o quanto a decisao depende das hipoteses.

Uso (depois de risco_piora.py e priorizar.py):  python sensibilidade.py
Gera: faixa_posicoes.csv e lista_investigacao.csv   (nao altera nenhum arquivo da fila oficial)
"""
import os

import pandas as pd

import pontos as P

N_SINAIS_BASE = 2
CID_COMPLICACAO = {"K400", "K403", "K420", "K430", "K800", "N132", "I832"}   # igual ao priorizar.py
NIVEL_LIM = ["nenhuma", "leve", "moderada", "grave"]

# ---- cenarios: cada um muda UMA hipotese defensavel (sem empilhar hipoteses extremas) ----
CENARIOS = {
    "base (fila oficial)": {},
    "1 sinal de piora sobe de classe": {"n_sinais": 1},
    "3 sinais de piora sobem de classe": {"n_sinais": 3},
    "biopsia positiva sem cancer no CID: NAO tratar como cancer": {"biopsia": False},
    "flag oncologico do cadastro tambem vale": {"flag_onc": True},
    "dor imputada: 2 pontos a mais": {"dor_imp": +2},
    "dor imputada: 2 pontos a menos": {"dor_imp": -2},
    "limitacao imputada: um nivel acima": {"lim_imp": +1},
    "limitacao imputada: um nivel abaixo": {"lim_imp": -1},
    "sem os pontos da regressao": {"risco": False},
    "tempo e gravidade com peso menor (x0,8)": {"peso": 0.8},
    "tempo e gravidade com peso maior (x1,15)": {"peso": 1.15},
    "sem o 'pedido do medico' do texto": {"pedido": False},
}


def classe(r, n_sinais, onc):
    if r.cid_normalizado == "I200":
        return "A1"
    if onc and r.n_sinais >= n_sinais:
        return "A1"
    if onc:
        return "A2"
    if r.incerto:
        return "B"
    if r.cid_normalizado in CID_COMPLICACAO:
        return "B"
    if r.n_sinais >= n_sinais:
        return "B"
    if r.dor >= 7 or r.lim == "grave":
        return "B"
    if r.dor >= 4 or r.lim == "moderada":
        return "C"
    return "D"


def rodar(d, ajuste):
    """Devolve (posicao, classe) de cada paciente sob um cenario."""
    n_sinais = ajuste.get("n_sinais", N_SINAIS_BASE)
    peso = ajuste.get("peso", 1.0)
    d = d.copy()
    dor, lim = d.intensidade_dor_eva.astype(float), d.limitacao_funcional.copy()
    if "dor_imp" in ajuste:
        dor = (dor + ajuste["dor_imp"] * d.dor_eva_imputada.astype(bool)).clip(0, 10)
    if "lim_imp" in ajuste:
        i = lim.map(NIVEL_LIM.index).fillna(0) + ajuste["lim_imp"] * d.limitacao_imputada.astype(bool)
        lim = i.clip(0, 3).astype(int).map(lambda k: NIVEL_LIM[k])
    d["dor"], d["lim"] = dor, lim
    onc = d.oncologico_pelo_cid.astype(bool).copy()
    if ajuste.get("biopsia", True):
        onc |= d.oncologico_confirmado.astype(bool)
    if ajuste.get("flag_onc", False):
        onc |= d.flag_oncologico.astype(str).str.lower().eq("sim")
    d["classe_c"] = [classe(r, n_sinais, o) for r, o in zip(d.itertuples(), onc)]
    ped = d.pedido_medico.astype(bool) if ajuste.get("pedido", True) else False
    sc = []
    for r, p in zip(d.itertuples(), ped if hasattr(ped, "__iter__") else [False] * len(d)):
        c = r.classe_c
        s = P.BASE[c]
        s += peso * (P.pontos_tempo(r.dias_em_fila, c) + P.pontos_esquecido(r.dias_em_fila, c))
        s += peso * P.pontos_gravidade(r.dor, r.lim, r.n_sinais, r.asa, r.diabetes_descomp, p)
        s = round(s, 1)                                                      # igual ao priorizar.py (desempate igual)
        if ajuste.get("risco", True) and r.prob_piora == r.prob_piora:       # nao e NaN
            s += P.pontos_risco(r.prob_piora)
        sc.append(round(s, 1))
    d["sc"] = sc
    ordem = d.sort_values(["sc", "dias_em_fila"], ascending=False).solicitacao_id
    pos = {sid: i + 1 for i, sid in enumerate(ordem)}
    return d.solicitacao_id.map(pos), d.classe_c


def dias_sem_atualizar(d):
    """Mesma regra da lista 'revisao' do regulador.py."""
    e = pd.read_csv("dataset_limpo/eventos_clinicos_limpo.csv", parse_dates=["data_evento"])
    if os.path.exists("eventos_novos.csv"):
        e = pd.concat([e, pd.read_csv("eventos_novos.csv", parse_dates=["data_evento"])])
    ref = max(pd.Timestamp("2026-10-23"), e.data_evento.max())
    ult = pd.concat([d.solicitacao_id.map(e.groupby("solicitacao_id").data_evento.max()),
                     pd.to_datetime(d.data_ultima_revisao_prioridade), pd.to_datetime(d.data_entrada_fila)], axis=1).max(axis=1)
    return (ref - ult).dt.days


def pergunta(r):
    """A duvida concreta que o regulador precisa esclarecer (so das fontes de incerteza reais)."""
    p = []
    if r.biopsia_positiva_cid_nao_oncologico:
        p.append("confirmar laudo da biopsia (positiva, mas o CID nao e oncologico)")
    if r.flag_oncologico_diverge and not r.biopsia_positiva_cid_nao_oncologico:
        p.append("conferir cadastro oncologico (flag diverge do CID)")
    if r.dor_eva_imputada:
        p.append("registrar a dor real (valor foi estimado)")
    if r.limitacao_imputada:
        p.append("registrar a limitacao real (valor foi estimado)")
    if r.n_sinais == 1:
        p.append("avaliar se o unico sinal de piora ja justifica subir de classe")
    if r.vezes_acima > 1:
        p.append("atualizar o prontuario")
    return "; ".join(p) if p else "sem duvida especifica (so desatualizacao ou sensibilidade a pesos)"


def main():
    d = pd.read_csv("fila_priorizada_detalhada.csv")
    d["dias_sem_atualizar"] = dias_sem_atualizar(d)
    d["intervalo"] = d.classe.map(P.PRAZO) / 2
    d["vezes_acima"] = (d.dias_sem_atualizar / d.intervalo).round(1)

    pos, cls = {}, {}
    for nome, aj in CENARIOS.items():
        pos[nome], cls[nome] = rodar(d, aj)
    pos, cls = pd.DataFrame(pos), pd.DataFrame(cls)

    # confere: o cenario base tem que reproduzir EXATAMENTE a fila oficial (com risco)
    base_nome = "base (fila oficial)"
    ok = (pos[base_nome].values == d.pos_risco.values).all() and (cls[base_nome].values == d.classe.values).all()
    assert ok, "o cenario base nao reproduz a fila oficial: confira se priorizar.py mudou"

    ordem = ["A1", "A2", "B", "C", "D"]
    f = pd.DataFrame({"solicitacao_id": d.solicitacao_id, "classe_oficial": d.classe, "posicao_oficial": d.pos_risco})
    f["pos_min"], f["pos_max"] = pos.min(axis=1), pos.max(axis=1)
    f["amplitude"] = f.pos_max - f.pos_min
    f["classe_mais_grave_possivel"] = cls.apply(lambda c: min(c, key=ordem.index), axis=1)
    f["classe_menos_grave_possivel"] = cls.apply(lambda c: max(c, key=ordem.index), axis=1)
    f["muda_de_classe"] = f.classe_mais_grave_possivel != f.classe_menos_grave_possivel
    dif = pos.sub(pos[base_nome], axis=0).abs().drop(columns=base_nome)
    f["fator_que_mais_move"] = dif.idxmax(axis=1).where(dif.max(axis=1) > 0, "nenhum")
    f["estabilidade"] = pd.cut(f.amplitude, [-1, 20, 100, 10**6], labels=["robusta", "moderada", "instavel"])
    f.to_csv("faixa_posicoes.csv", index=False)

    # ---- lista de investigacao = consequencia x (incerteza + desatualizacao) ----
    conseq = {"A1": 1.0, "A2": 0.9, "B": 0.6, "C": 0.3, "D": 0.15}
    d = d.merge(f, on="solicitacao_id")
    d["incerteza"] = (d.amplitude / len(d)).clip(0, 1)
    d["desatualizacao"] = (d.vezes_acima / 3).clip(0, 1)
    d["consequencia"] = d.classe_mais_grave_possivel.map(conseq)          # o que esta em jogo no pior cenario
    d.loc[d.onc, "consequencia"] = 1.0
    d["prioridade_revisao"] = (100 * d.consequencia * (0.6 * d.incerteza + 0.4 * d.desatualizacao)).round(1)
    d["pergunta_pendente"] = d.apply(pergunta, axis=1)
    cols = ["solicitacao_id", "posicao_oficial", "classe_oficial", "pos_min", "pos_max", "classe_mais_grave_possivel",
            "classe_menos_grave_possivel", "dias_sem_atualizar", "vezes_acima", "prioridade_revisao", "estabilidade",
            "fator_que_mais_move", "pergunta_pendente"]
    out = d.sort_values(["prioridade_revisao", "posicao_oficial"], ascending=[False, True])[cols]
    out.insert(0, "rank_revisao", range(1, len(out) + 1))
    out.to_csv("lista_investigacao.csv", index=False)

    print(f"{len(CENARIOS)} cenarios rodados; cenario base == fila oficial: OK")
    print("estabilidade da posicao:", f.estabilidade.value_counts().reindex(["robusta", "moderada", "instavel"]).to_dict())
    print("pacientes que mudam de classe em algum cenario:", int(f.muda_de_classe.sum()))
    print("lista de investigacao: faixa_posicoes.csv e lista_investigacao.csv gerados")


if __name__ == "__main__":
    main()
