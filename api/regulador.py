"""regulador.py — ferramentas do regulador (versao hackathon, linha de comando).

  python regulador.py fila [--especialidade X] [--apoio endocrinologia] [--ordem so_regras] [--top 15]
  python regulador.py decidir SOL-... --motivo "..." [--posicao N] [--regulador NOME] [--ordem com_risco]
  python regulador.py fila-final [--ordem com_risco]
  python regulador.py evento SOL-... --tipo pronto_socorro --resultado atendido_liberado [--descricao "..."]
  python regulador.py revisao [--top 15]
  python regulador.py investigacao [--top 10]     (quem precisa de REVISAO HUMANA primeiro; nao e a ordem cirurgica)
  python regulador.py mensagens [--top 10]        (relatos dos pacientes pendentes; os com sinal de alerta aparecem primeiro)
  python regulador.py mensagem-resolver MSG-0001 --aceitar|--descartar [--regulador NOME]
  python regulador.py reiniciar

Rode antes:  python risco_piora.py  e  python priorizar.py
O sistema PROPOE; o regulador DECIDE e o motivo fica registrado em decisoes_regulador.csv.
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import unicodedata

import pandas as pd

import pontos as P

REF = pd.Timestamp("2026-10-23")
DET = "fila_priorizada_detalhada.csv"
ARQ_ORDEM = {"com_risco": "fila_priorizada.csv", "so_regras": "fila_priorizada_so_regras.csv"}
POS = {"com_risco": "pos_risco", "so_regras": "pos_regras"}
SCORE = {"com_risco": "score_risco", "so_regras": "score_regras"}

# Especialidades de APOIO (quem "precisa" de cada servico): regra nossa, a partir das comorbidades registradas.
APOIO = {
    "endocrinologia": r"dm2|diabet|hipotireoid|obesidade|e11|e66|e03",
    "cardiologia": r"icc|cardiopatia isquemica|fibrilacao|anticoagula|i25|i50|i48",
    "pneumologia": r"dpoc|asma|j44|j45",
    "nefrologia": r"\bdrc\b|n18",
}
EVENTOS = {   # tipo -> resultados validos (dicionario de dados)
    "biopsia": ["positivo", "negativo", "inconclusivo"], "pronto_socorro": ["atendido_liberado", "observacao"],
    "internacao": ["alta"], "exame_imagem": ["estavel", "progressao"], "consulta_reavaliacao": ["piora", "estavel", "melhora"],
    "contato_telefonico": ["atendeu", "nao_atendeu", "relata_piora", "relata_melhora"], "hba1c": ["resultado"], "falta": ["consulta", "exame"]}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).lower()


def detalhada():
    if not os.path.exists(DET):
        sys.exit("Rode antes: python risco_piora.py && python priorizar.py")
    return pd.read_csv(DET)


def rodar_priorizar():
    subprocess.run([sys.executable, "priorizar.py"], check=True, stdout=subprocess.DEVNULL)


# ------------------------------------------------------------------ fila (com filtros)
def cmd_fila(a):
    d = detalhada()
    pos, sc = POS[a.ordem], SCORE[a.ordem]
    if a.especialidade:
        k = sem_acento(a.especialidade)
        d = d[d.especialidade.map(sem_acento).str.contains(k) | d.procedimento.map(sem_acento).str.contains(k)]
    if a.apoio:
        if a.apoio not in APOIO:
            sys.exit(f"apoio invalido. Opcoes: {', '.join(APOIO)}")
        txt = (d.comorbidades.fillna("") + " " + d.cid_secundario.fillna("")).map(sem_acento)
        m = txt.str.contains(APOIO[a.apoio])
        if a.apoio == "endocrinologia":
            m |= d.diabetes_descomp
        if a.apoio == "cardiologia":
            m |= d.asa.fillna(0) >= 3
        d = d[m]
    d = d.sort_values(pos).head(a.top)
    out = pd.DataFrame({"pos": d[pos], "solicitacao": d.solicitacao_id, "classe": d.classe, "especialidade": d.especialidade.str[:26],
                        "procedimento": d.procedimento.str[:30], "score": d[sc].round(0).astype(int),
                        "alerta": d.apply(lambda r: ("ESQUECIDO " if r.esquecido else "") + ("DESCOMPENSADO" if r.diabetes_descomp else ""), axis=1)})
    print(f"Ordem: {a.ordem} | {len(out)} pacientes mostrados (posicao = na fila inteira)\n")
    print(out.to_string(index=False))


# ------------------------------------------------------------------ decisao do regulador
def cmd_decidir(a):
    d = detalhada().set_index("solicitacao_id")
    if a.solicitacao not in d.index:
        sys.exit("solicitacao nao esta na fila")
    if not a.motivo or not a.motivo.strip():
        sys.exit("RECUSADO: o motivo e obrigatorio (o humano decide, mas justifica).")
    r, pos = d.loc[a.solicitacao], POS[a.ordem]
    proposta = int(r[pos])
    final = int(a.posicao) if a.posicao else proposta                   # sem --posicao = aceita a proposta
    if not 1 <= final <= len(d):
        sys.exit(f"posicao deve estar entre 1 e {len(d)}")
    if r.onc and final > proposta:
        sys.exit("RECUSADO: nunca se rebaixa um paciente oncologico (regra do desafio).")
    ultimo_onc = int(d[d.onc][pos].max())
    if (not r.onc) and r.classe in ("C", "D") and final <= ultimo_onc:
        sys.exit(f"RECUSADO: paciente sem urgencia (classe {r.classe}) nao pode ficar acima de um oncologico (ultimo na posicao {ultimo_onc}).")
    reg = pd.DataFrame([{"data_hora": dt.datetime.now().isoformat(timespec="seconds"), "regulador": a.regulador, "solicitacao_id": a.solicitacao,
                         "ordem_usada": a.ordem, "classe": r.classe, "posicao_proposta": proposta, "posicao_final": final, "motivo": a.motivo.strip()}])
    reg.to_csv("decisoes_regulador.csv", mode="a", header=not os.path.exists("decisoes_regulador.csv"), index=False)
    acao = "aceitou a proposta" if final == proposta else f"moveu de {proposta} para {final}"
    print(f"Registrado: {a.regulador} {acao} ({a.solicitacao}). Motivo: {a.motivo.strip()}")


def cmd_fila_final(a):
    if not os.path.exists("decisoes_regulador.csv"):
        sys.exit("Ainda nao ha decisoes em decisoes_regulador.csv")
    base = pd.read_csv(ARQ_ORDEM[a.ordem]).sort_values("posicao")
    dec = pd.read_csv("decisoes_regulador.csv")
    dec = dec[dec.ordem_usada == a.ordem].drop_duplicates("solicitacao_id", keep="last").sort_values("data_hora")
    ordem, just = list(base.solicitacao_id), dict(zip(base.solicitacao_id, base.justificativa))
    for _, x in dec.iterrows():
        if x.posicao_final != x.posicao_proposta:
            ordem.remove(x.solicitacao_id)
            ordem.insert(int(x.posicao_final) - 1, x.solicitacao_id)
        just[x.solicitacao_id] += f" | DECISAO DO REGULADOR ({x.regulador}): {x.motivo} [proposta pos {x.posicao_proposta} -> final {x.posicao_final}]"
    out = pd.DataFrame({"solicitacao_id": ordem, "posicao": range(1, len(ordem) + 1), "justificativa": [just[s] for s in ordem]})
    out.to_csv("fila_final_regulador.csv", index=False)
    v = subprocess.run([sys.executable, "verificar_fila_priorizada.py", "fila_final_regulador.csv"], capture_output=True, text=True)
    print(f"fila_final_regulador.csv gerada com {len(dec)} decisao(oes) do regulador.")
    print("Verificador:", [l for l in v.stdout.splitlines() if l.startswith(("RESULTADO", "ERRO"))])


# ------------------------------------------------------------------ reavaliacao a cada evento novo
def cmd_evento(a):
    d = detalhada()
    if a.solicitacao not in set(d.solicitacao_id):
        sys.exit("solicitacao nao esta na fila")
    if a.tipo not in EVENTOS or a.resultado not in EVENTOS[a.tipo]:
        sys.exit("tipo/resultado invalidos. Validos: " + "; ".join(f"{t}: {'/'.join(r)}" for t, r in EVENTOS.items()))
    antes = d[["solicitacao_id", "classe", "posicao"]].rename(columns={"classe": "classe_antes", "posicao": "pos_antes"})
    n = len(pd.read_csv("eventos_novos.csv")) if os.path.exists("eventos_novos.csv") else 0
    ev = pd.DataFrame([{"evento_id": f"EVT-NOVO-{n + 1:04d}", "solicitacao_id": a.solicitacao,
                        "paciente_id": d.loc[d.solicitacao_id == a.solicitacao, "paciente_id"].iloc[0], "data_evento": a.data,
                        "tipo_evento": a.tipo, "resultado": a.resultado, "valor_numerico": a.valor, "descricao": a.descricao, "origem": "regulador"}])
    ev.to_csv("eventos_novos.csv", mode="a", header=not os.path.exists("eventos_novos.csv"), index=False)
    rodar_priorizar()
    novo = detalhada()
    x = novo.merge(antes, on="solicitacao_id")
    x["delta"] = x.pos_antes - x.posicao                                      # positivo = subiu
    p = x[x.solicitacao_id == a.solicitacao].iloc[0]
    print(f"EVENTO REGISTRADO: {a.tipo}/{a.resultado} em {a.solicitacao}\n")
    print(f"{a.solicitacao}: posicao {p.pos_antes} -> {p.posicao} | classe {p.classe_antes} -> {p.classe}")
    if p.classe != p.classe_antes:
        print(f"  ALERTA: mudou de classe ({p.classe_antes} -> {p.classe})")
    print(f"  Justificativa: {p.justificativa}\n")
    outros = x[x.solicitacao_id != a.solicitacao]
    print(f"Outros pacientes que mudaram de posicao: {int((outros.delta != 0).sum())} (descem 1 posicao quem foi ultrapassado)")
    print(f"Mudaram de classe: {int((x.classe != x.classe_antes).sum())}")


# ------------------------------------------------------------------ relatos do paciente (area do paciente)
def cmd_mensagens(a):
    if not os.path.exists("mensagens_paciente.csv"):
        return print("Nenhuma mensagem de paciente ainda. (python acolhimento.py relato SOL-... \"texto\")")
    m = pd.read_csv("mensagens_paciente.csv")
    p = m[m.status == "pendente"].sort_values(["sinal_de_alerta", "data_hora"], ascending=[False, True])
    print(f"Mensagens pendentes: {len(p)} (relato do paciente, NAO validado; nao altera a fila ate voce aceitar)\n")
    for r in p.head(a.top).itertuples():
        print(f"{r.mensagem_id} | {r.solicitacao_id} | {r.data_hora} | tendencia: {r.tendencia}" + ("  << SINAL DE ALERTA" if r.sinal_de_alerta else ""))
        print(f"    resumo ({r.origem_resumo}): {r.resumo}\n    texto original: {r.texto_original}\n    evento sugerido se aceitar: contato_telefonico/{r.evento_sugerido}\n")


def cmd_mensagem_resolver(a):
    if not os.path.exists("mensagens_paciente.csv"):
        sys.exit("nao ha mensagens")
    m = pd.read_csv("mensagens_paciente.csv")
    i = m.index[m.mensagem_id == a.mensagem]
    if len(i) == 0 or m.loc[i[0], "status"] != "pendente":
        sys.exit("mensagem nao encontrada ou ja resolvida")
    i = i[0]
    if a.aceitar:
        resumo = str(m.loc[i, "resumo"])[:120]
        cmd_evento(argparse.Namespace(solicitacao=m.loc[i, "solicitacao_id"], tipo="contato_telefonico", resultado=m.loc[i, "evento_sugerido"],
                                      descricao=f"relato do paciente validado por {a.regulador}: {resumo}", valor=None, data=dt.date.today().isoformat()))
        m.loc[i, "status"] = "aceita"
    else:
        m.loc[i, "status"] = "descartada"
        print(f"{a.mensagem} descartada (a fila nao mudou).")
    m.to_csv("mensagens_paciente.csv", index=False)


def cmd_reiniciar(a):
    for f in ("eventos_novos.csv", "decisoes_regulador.csv", "fila_final_regulador.csv", "mensagens_paciente.csv"):
        if os.path.exists(f):
            os.remove(f)
    rodar_priorizar()
    print("Reiniciado: eventos novos e decisoes apagados; fila recalculada so com o dataset.")


# ------------------------------------------------------------------ lista de revisao ("sem atualizacao")
def cmd_revisao(a):
    d = detalhada()
    e = pd.read_csv("dataset_limpo/eventos_clinicos_limpo.csv", parse_dates=["data_evento"])
    if os.path.exists("eventos_novos.csv"):
        e = pd.concat([e, pd.read_csv("eventos_novos.csv", parse_dates=["data_evento"])])
    ref = max(REF, e.data_evento.max())
    d["ult"] = pd.concat([d.solicitacao_id.map(e.groupby("solicitacao_id").data_evento.max()),
                          pd.to_datetime(d.data_ultima_revisao_prioridade), pd.to_datetime(d.data_entrada_fila)], axis=1).max(axis=1)
    d["dias_sem_atualizar"] = (ref - d.ult).dt.days
    d["intervalo"] = d.classe.map(P.PRAZO) / 2                          # revisar a cada metade do prazo da classe
    d["vezes_acima"] = (d.dias_sem_atualizar / d.intervalo).round(1)
    d["alerta"] = d.vezes_acima.map(lambda v: "ATRASADO" if v > 1 else "")
    print(f"Pacientes atrasados na atualizacao: {int((d.vezes_acima > 1).sum())} de {len(d)} (intervalo = metade do prazo SWALIS da classe)\n")
    t = d.sort_values(["vezes_acima", "posicao"], ascending=[False, True]).head(a.top)
    print(pd.DataFrame({"solicitacao": t.solicitacao_id, "classe": t.classe, "pos_fila": t.posicao, "dias_sem_atualizar": t.dias_sem_atualizar,
                        "intervalo_d": t.intervalo, "vezes_acima": t.vezes_acima, "alerta": t.alerta}).to_string(index=False))


# ------------------------------------------------------------------ lista de investigacao (quem revisar primeiro)
def cmd_investigacao(a):
    subprocess.run([sys.executable, "sensibilidade.py"], check=True, stdout=subprocess.DEVNULL)   # recalcula com o estado atual
    l = pd.read_csv("lista_investigacao.csv")
    print("LISTA DE INVESTIGACAO: quem precisa de revisao humana primeiro (NAO e a ordem cirurgica).")
    print("Faixa de posicoes = analise de sensibilidade, nao probabilidade.\n")
    for r in l.head(a.top).itertuples():
        print(f"{r.rank_revisao:>2}. {r.solicitacao_id} | fila oficial: pos {r.posicao_oficial} ({r.classe_oficial}) | faixa {r.pos_min}-{r.pos_max} "
              f"| classe possivel: {r.classe_mais_grave_possivel} a {r.classe_menos_grave_possivel} | {r.vezes_acima}x acima do intervalo de revisao")
        print(f"    maior fator: {r.fator_que_mais_move}\n    pergunta: {r.pergunta_pendente}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("fila"); s.add_argument("--especialidade"); s.add_argument("--apoio")
    s.add_argument("--ordem", choices=ARQ_ORDEM, default="com_risco"); s.add_argument("--top", type=int, default=15); s.set_defaults(f=cmd_fila)
    s = sub.add_parser("decidir"); s.add_argument("solicitacao"); s.add_argument("--motivo", default=""); s.add_argument("--posicao", type=int)
    s.add_argument("--regulador", default="regulador"); s.add_argument("--ordem", choices=ARQ_ORDEM, default="com_risco"); s.set_defaults(f=cmd_decidir)
    s = sub.add_parser("fila-final"); s.add_argument("--ordem", choices=ARQ_ORDEM, default="com_risco"); s.set_defaults(f=cmd_fila_final)
    s = sub.add_parser("evento"); s.add_argument("solicitacao"); s.add_argument("--tipo", required=True); s.add_argument("--resultado", required=True)
    s.add_argument("--descricao", default="evento lancado pelo regulador"); s.add_argument("--valor", type=float)
    s.add_argument("--data", default=dt.date.today().isoformat()); s.set_defaults(f=cmd_evento)
    s = sub.add_parser("revisao"); s.add_argument("--top", type=int, default=15); s.set_defaults(f=cmd_revisao)
    s = sub.add_parser("investigacao"); s.add_argument("--top", type=int, default=10); s.set_defaults(f=cmd_investigacao)
    s = sub.add_parser("mensagens"); s.add_argument("--top", type=int, default=10); s.set_defaults(f=cmd_mensagens)
    s = sub.add_parser("mensagem-resolver"); s.add_argument("mensagem"); s.add_argument("--regulador", default="regulador")
    g = s.add_mutually_exclusive_group(required=True); g.add_argument("--aceitar", action="store_true"); g.add_argument("--descartar", action="store_true")
    s.set_defaults(f=cmd_mensagem_resolver)
    s = sub.add_parser("reiniciar"); s.set_defaults(f=cmd_reiniciar)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
