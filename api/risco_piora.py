"""risco_piora.py — Regressao logistica: "este paciente tem chance alta de PIORAR enquanto espera?"

Modulo SEPARADO do motor de regras. Produz uma probabilidade por solicitacao (risco_piora.csv);
o priorizar.py transforma essa probabilidade em pontos (+20 ou +40) no segundo score.

Alvo (y): teve algum evento de deterioracao DEPOIS de entrar na fila
          (pronto-socorro, internacao, progressao em imagem, reavaliacao com piora, piora relatada ao call center).
Entradas: SO o que se sabia na ENTRADA (ASA, comorbidades, dor, limitacao, distancia, CID, risco cirurgico, texto da justificativa).
          NAO entram: idade (decisao do projeto), eventos, observacoes da regulacao, flags manuais, prioridade manual
          (seria "colar": o modelo veria o futuro ou repetiria o erro do sistema atual).
Tempo:    quanto mais na fila, mais chance de ja ter piorado. O tempo entra no treino como CONTROLE (log dos dias),
          mas na hora de PREVER e fixado em 365 dias para todos, para o risco nao repetir os pontos de tempo de espera.
Honestidade: a probabilidade de cada paciente vem de modelos que NAO viram aquele paciente (validacao cruzada repetida).

Uso (na pasta com dataset_limpo/):  python risco_piora.py
"""
import re
import unicodedata
import warnings

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import texto as T

warnings.filterwarnings("ignore")
EXPOSICAO_DIAS = 365
REPETICOES = 5
NUM = ["asa", "n_comorb", "onco", "dor", "limitacao", "distancia", "risco_cirurgico", "log_dias", "t_grave", "t_ps"]
CAT = ["capitulo_cid"]
NOMES = {"asa": "ASA", "n_comorb": "nº de comorbidades", "onco": "CID oncológico (C*)", "dor": "dor (EVA)",
         "limitacao": "limitação funcional", "distancia": "distância do hospital", "risco_cirurgico": "risco cirúrgico do procedimento",
         "log_dias": "tempo na fila (controle)", "t_grave": "texto do médico com sinal de gravidade", "t_ps": "texto cita PS/internação"}


def sem_acento(s):
    if not isinstance(s, str):
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def montar():
    f = pd.read_csv("dataset_limpo/fila_cirurgica_limpa.csv", parse_dates=["data_entrada_fila"])
    e = pd.read_csv("dataset_limpo/eventos_clinicos_limpo.csv", parse_dates=["data_evento"])
    p = pd.read_csv("procedimentos.csv")
    f["principal_id"] = f.duplicata_de.fillna(f.solicitacao_id)          # duplicatas herdam o risco da principal
    d = f[f.duplicata_de.isna()].merge(p[["procedimento_id", "risco_cirurgico"]], on="procedimento_id", how="left").copy()

    # alvo: deterioracao APOS a entrada na fila
    det = e[(e.tipo_evento.isin(["pronto_socorro", "internacao"]))
            | ((e.tipo_evento == "exame_imagem") & (e.resultado == "progressao"))
            | ((e.tipo_evento == "consulta_reavaliacao") & (e.resultado == "piora"))
            | ((e.tipo_evento == "contato_telefonico") & (e.resultado == "relata_piora"))]
    det = det.merge(d[["solicitacao_id", "data_entrada_fila"]], on="solicitacao_id")
    det = det[det.data_evento >= det.data_entrada_fila]
    d["y"] = d.solicitacao_id.isin(set(det.solicitacao_id)).astype(int)

    # caracteristicas da ENTRADA
    cid = d.cid_normalizado
    d["capitulo_cid"] = cid.str[0]
    d["onco"] = cid.str.startswith("C").astype(int)
    d["asa"] = d.asa.fillna(d.asa.median())
    d["n_comorb"] = d.comorbidades.fillna("nenhuma").map(lambda s: 0 if sem_acento(s).strip() == "nenhuma" else len(s.split(";")))
    d["dor"] = d.intensidade_dor_eva
    d["limitacao"] = d.limitacao_funcional.map({"nenhuma": 0, "leve": 1, "moderada": 2, "grave": 3}).fillna(1)
    d["distancia"] = d.distancia_hospital_km.fillna(d.distancia_hospital_km.median())
    d["log_dias"] = np.log1p(d.dias_em_fila)
    # so a justificativa (escrita na inclusao), nao as observacoes (escritas durante a espera)
    d["t_grave"] = [int(T.ler_texto(j, "")[0] > 0) for j in d.justificativa_clinica]
    t = d.justificativa_clinica.map(sem_acento)
    d["t_ps"] = t.str.contains(r"idas? ao ps|\bps\b|internacao").astype(int)
    return f, d


def pipeline(C=0.3):
    pre = ColumnTransformer([("n", StandardScaler(), NUM), ("c", OneHotEncoder(handle_unknown="ignore"), CAT)])
    return Pipeline([("pre", pre), ("lr", LogisticRegression(C=C, max_iter=2000))])


def main():
    f, d = montar()
    X, y = d[NUM + CAT], d.y.values
    X_prev = X.copy()
    X_prev["log_dias"] = np.log1p(EXPOSICAO_DIAS)         # exposicao fixa na hora de prever

    # ---- validacao cruzada repetida: probabilidade FORA DA AMOSTRA para cada paciente ----
    oof = np.zeros(len(d))
    aucs = []
    for rep in range(REPETICOES):
        pr_real = np.zeros(len(d))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=rep).split(X, y):
            m = pipeline().fit(X.iloc[tr], y[tr])
            pr_real[te] = m.predict_proba(X.iloc[te])[:, 1]                   # com o tempo real (para medir AUC)
            oof[te] += m.predict_proba(X_prev.iloc[te])[:, 1] / REPETICOES    # com exposicao fixa (para pontuar)
        aucs.append(roc_auc_score(y, pr_real))
    d["prob_piora"] = oof
    base = y.mean()

    # ---- modelo final (so para interpretar os coeficientes) ----
    final = pipeline().fit(X, y)
    nomes = NUM + list(final.named_steps["pre"].named_transformers_["c"].get_feature_names_out(CAT))
    coef = pd.Series(final.named_steps["lr"].coef_[0], index=nomes)
    odds = np.exp(coef[NUM]).rename(lambda c: NOMES.get(c, c)).sort_values(ascending=False)

    # ---- calibracao por faixa de risco ----
    d["faixa"] = pd.qcut(d.prob_piora, 5, duplicates="drop")
    cal = d.groupby("faixa", observed=True).agg(n=("y", "size"), previsto=("prob_piora", "mean"), observado=("y", "mean"))

    # ---- saida por solicitacao (duplicatas herdam o risco da principal) ----
    out = f[["solicitacao_id", "principal_id"]].copy()
    out["prob_piora"] = out.principal_id.map(d.set_index("solicitacao_id").prob_piora).round(4)
    out[["solicitacao_id", "prob_piora"]].to_csv("risco_piora.csv", index=False)

    linhas = [
        "# Modelo de risco de piora durante a espera (regressao logistica)", "",
        f"- Solicitacoes (sem duplicatas): {len(d)}; com piora apos a entrada: {int(y.sum())} ({base:.1%}).",
        f"- AUC em validacao cruzada (5 folds x {REPETICOES} repeticoes): {np.mean(aucs):.3f} (±{np.std(aucs):.3f} entre repeticoes; "
        f"a incerteza real com {int(y.sum())} positivos e maior, ~±0.04). Acaso = 0.50.",
        "- Idade NAO e usada (decisao do projeto: nenhum dado demografico entra na priorizacao).",
        "", "## Efeito de cada caracteristica (razao de chances por +1 desvio-padrao; >1 aumenta o risco)", "",
    ] + [f"- {k}: {v:.2f}" for k, v in odds.items()] + [
        "", "## Calibracao (5 faixas de risco previsto; previsto x observado)", "", "| faixa | n | previsto | observado |", "|---|---|---|---|"] + [
        f"| {i + 1} | {int(r.n)} | {r.previsto:.0%} | {r.observado:.0%} |" for i, (_, r) in enumerate(cal.iterrows())] + [
        "", f"Probabilidades previstas com tempo de fila fixado em {EXPOSICAO_DIAS} dias para todos. "
        f"Faixa de risco previsto: min {d.prob_piora.min():.0%} · mediana {d.prob_piora.median():.0%} · max {d.prob_piora.max():.0%}.",
        f"Pontos de risco: >=30% = +20 · >=40% = +40 (ver pontos.py). Acima de 30%: {int((d.prob_piora >= .30).sum())} solicitacoes; "
        f"acima de 40%: {int((d.prob_piora >= .40).sum())}."]
    open("risco_piora_metricas.md", "w", encoding="utf-8").write("\n".join(linhas) + "\n")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()