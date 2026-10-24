"""gerar_perguntas.py — gera com LLM uma pergunta personalizada para cada paciente e grava em perguntas_pacientes.csv.

Rode UMA vez, na maquina de quem tem a chave. O CSV gerado vai para o repositorio: quem clonar o repo
ve as perguntas SEM precisar de chave.

Chave: variavel de ambiente LLM_API_KEY (ou arquivo .env, que esta no .gitignore). Nunca coloque no codigo.
Opcional: LLM_MODEL (padrao gpt-4o-mini) e LLM_BASE_URL (outro servico compativel com a API de chat).

Uso:
  python gerar_perguntas.py --limite 5      # teste com 5 pacientes
  python gerar_perguntas.py                 # todos (so os que ainda nao tem pergunta de LLM)
  python gerar_perguntas.py --refazer       # regera tudo

So o necessario vai ao LLM: procedimento, especialidade, diagnostico, tempo na fila, dor, limitacao e tipos dos
ultimos eventos. NAO vai nome, id, municipio nem datas.
"""
import argparse
import concurrent.futures as cf
import os
import sys
import time

import pandas as pd

import acolhimento as A


def ultimos_eventos(sid, e, n=3):
    x = e[e.solicitacao_id == sid].sort_values("data_evento").tail(n)
    return [f"{t}: {r}" for t, r in zip(x.tipo_evento, x.resultado)]


def gerar(r, eventos):
    ultimo = None
    for tentativa in range(3):
        try:
            return A.gerar_pergunta_llm(r, eventos), "llm"
        except Exception as ex:                              # rede, limite, resposta estranha
            ultimo = ex
            time.sleep(2 * (tentativa + 1))
    return A.pergunta_modelo(r.procedimento, r.especialidade), "modelo:" + type(ultimo).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int)
    ap.add_argument("--refazer", action="store_true")
    ap.add_argument("--paralelo", type=int, default=6)
    a = ap.parse_args()

    if not A.tem_chave():
        sys.exit("Defina LLM_API_KEY (variavel de ambiente ou arquivo .env). Sem chave, o sistema usa as perguntas-modelo.")
    d = pd.read_csv(A.DET)
    e = pd.read_csv("dataset_limpo/eventos_clinicos_limpo.csv")
    feito = pd.DataFrame(columns=["solicitacao_id", "pergunta", "origem"])
    if os.path.exists(A.PERGUNTAS) and not a.refazer:
        feito = pd.read_csv(A.PERGUNTAS)
    ja = set(feito[feito.origem == "llm"].solicitacao_id)
    alvo = d[~d.solicitacao_id.isin(ja)]
    if a.limite:
        alvo = alvo.head(a.limite)
    print(f"{len(alvo)} pacientes para gerar ({len(ja)} ja tinham pergunta de LLM)")

    linhas = list(alvo.itertuples())
    with cf.ThreadPoolExecutor(a.paralelo) as ex:
        futs = {ex.submit(gerar, r, ultimos_eventos(r.solicitacao_id, e)): r for r in linhas}
        novos = []
        for i, f in enumerate(cf.as_completed(futs), 1):
            r = futs[f]
            p, o = f.result()
            novos.append({"solicitacao_id": r.solicitacao_id, "pergunta": p, "origem": o})
            if i % 25 == 0:
                print(f"  {i}/{len(linhas)}")
    out = pd.concat([feito[~feito.solicitacao_id.isin([n["solicitacao_id"] for n in novos])], pd.DataFrame(novos)], ignore_index=True)
    out.to_csv(A.PERGUNTAS, index=False)
    falhas = int((~out.origem.eq("llm")).sum())
    print(f"Gravado {A.PERGUNTAS}: {len(out)} perguntas ({int(out.origem.eq('llm').sum())} de LLM, {falhas} do plano B).")
    print("REVISE as perguntas antes de publicar: um profissional de saude deve ler o arquivo.")


if __name__ == "__main__":
    main()
