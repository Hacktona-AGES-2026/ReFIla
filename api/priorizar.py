"""Priorizacao simples: 1) classe SWALIS por regras claras  2) pontos (pontos.py)  3) ordena.

Uso (na pasta com dataset_limpo/): python priorizar.py
Gera: fila_priorizada.csv (com risco de piora, se existir risco_piora.csv) e fila_priorizada_so_regras.csv
(solicitacao_id, posicao, justificativa). Rode antes: python risco_piora.py
"""
import os

import pandas as pd
import pontos as P
import texto as T

f = pd.read_csv("dataset_limpo/fila_cirurgica_limpa.csv")
e = pd.read_csv("dataset_limpo/eventos_clinicos_limpo.csv")
if os.path.exists("eventos_novos.csv"):          # eventos lancados depois (reavaliacao a cada evento novo)
    e = pd.concat([e, pd.read_csv("eventos_novos.csv")], ignore_index=True)
e = e.drop_duplicates(["solicitacao_id", "tipo_evento", "resultado", "data_evento"])

# ---- sinais de piora: eventos que mostram agravamento durante a espera ----
piora = (
    ((e.tipo_evento == "consulta_reavaliacao") & (e.resultado == "piora"))
    | ((e.tipo_evento == "exame_imagem") & (e.resultado == "progressao"))
    | ((e.tipo_evento == "contato_telefonico") & (e.resultado == "relata_piora"))
    | (e.tipo_evento == "pronto_socorro")
    | (e.tipo_evento == "internacao")
)
f["n_sinais"] = f.solicitacao_id.map(e[piora].groupby("solicitacao_id").size()).fillna(0).astype(int)

# ---- diabetes descompensando: ultima HbA1c > 8,5% e subiu >= 1 ponto desde a primeira medida ----
h = e[e.tipo_evento == "hba1c"].sort_values("data_evento").groupby("solicitacao_id").valor_numerico
f["diabetes_descomp"] = f.solicitacao_id.map(((h.last() > 8.5) & (h.last() - h.first() >= 1.0))).fillna(False).astype(bool)

# ---- texto livre: so o 'pedido do medico' (+3 de gravidade) por enquanto ----
f["pedido_medico"] = [T.ler_texto(j, o)[2] for j, o in zip(f.justificativa_clinica, f.observacoes)]

N_SINAIS_CLASSE = 2   # quantos sinais de piora sao necessarios para subir de classe

# CIDs cuja propria descricao ja indica complicacao (os mesmos que o verificador trata como "nao calmos"):
# K40.0/K40.3 hernia inguinal com obstrucao, K42.0 umbilical com obstrucao, K43.0 incisional com obstrucao,
# K80.0 colecistite aguda, N13.2 hidronefrose por calculo, I83.2 varizes com ulcera e inflamacao
CID_COMPLICACAO = {"K400", "K403", "K420", "K430", "K800", "N132", "I832"}

# ---- classe SWALIS ----
onc = f.oncologico_pelo_cid | f.oncologico_confirmado          # CID C* ou biopsia positiva
incerto = f.cid_normalizado.str.match(r"^(D3[7-9]|D4[0-8]|R91)")


def classe(r):
    if r.cid_normalizado == "I200":     # angina instavel: exemplo de A1 no proprio swalis.csv
        return "A1", "angina instavel (CID I20.0, exemplo de A1 no SWALIS)"
    if r.onc and r.n_sinais >= N_SINAIS_CLASSE:
        return "A1", "oncologico com sinal de piora"
    if r.onc:
        return "A2", "oncologico"
    if r.incerto:
        return "B", "lesao de comportamento incerto"
    if r.cid_normalizado in CID_COMPLICACAO:
        return "B", "CID com complicacao aguda (obstrucao, colecistite aguda, ulcera...)"
    if r.n_sinais >= N_SINAIS_CLASSE:
        return "B", f"{r.n_sinais} sinais de piora na espera"
    if r.intensidade_dor_eva >= 7 or r.limitacao_funcional == "grave":
        return "B", "dor forte ou limitacao grave"
    if r.intensidade_dor_eva >= 4 or r.limitacao_funcional == "moderada":
        return "C", "dor ou limitacao moderada"
    return "D", "sem urgencia clinica"


f["onc"], f["incerto"] = onc, incerto
f[["classe", "motivo"]] = f.apply(lambda r: pd.Series(classe(r)), axis=1)

# ---- AVISO: biopsia positiva com CID nao oncologico (tratado como cancer por decisao nossa) ----
bx = f.biopsia_positiva_cid_nao_oncologico
f.loc[bx, "motivo"] = (f.motivo + " | ATENCAO: biopsia positiva, mas o CID " + f.cid_principal
                       + " NAO e oncologico (tratado como cancer; conferir cadastro)")
f[bx | f.flag_oncologico_diverge][["solicitacao_id", "cid_principal", "cid_descricao", "flag_oncologico",
                                    "oncologico_pelo_cid", "biopsia_positiva_cid_nao_oncologico",
                                    "flag_oncologico_diverge"]].to_csv("alertas_cadastro.csv", index=False)

# ---- pontos ----
f["pts_base"] = f.classe.map(P.BASE)
f["pts_tempo"] = f.apply(lambda r: P.pontos_tempo(r.dias_em_fila, r.classe), axis=1)
f["pts_grav"] = f.apply(lambda r: P.pontos_gravidade(
    r.intensidade_dor_eva, r.limitacao_funcional, r.n_sinais, r.asa, r.diabetes_descomp, r.pedido_medico), axis=1)
f["pts_esquecido"] = f.apply(lambda r: P.pontos_esquecido(r.dias_em_fila, r.classe), axis=1)
f["esquecido"] = f.apply(lambda r: P.esquecido(r.dias_em_fila, r.classe), axis=1)   # alerta: > 3x o prazo
f["score_regras"] = (f.pts_base + f.pts_tempo + f.pts_esquecido + f.pts_grav).round(1)

# ---- SEGUNDO SCORE: soma os pontos do risco previsto de piora (risco_piora.py) ----
COM_RISCO = os.path.exists("risco_piora.csv")
if COM_RISCO:
    f["prob_piora"] = f.solicitacao_id.map(pd.read_csv("risco_piora.csv").set_index("solicitacao_id").prob_piora)
else:
    f["prob_piora"] = float("nan")
f["piora_observada"] = f.n_sinais >= 1                                   # (informativo) piora ja observada: conta nas REGRAS
f["pts_risco"] = f.prob_piora.fillna(0).map(P.pontos_risco) if COM_RISCO else 0.0   # so a PREVISAO do modelo
f["score_risco"] = (f.score_regras + f.pts_risco).round(1)

# ---- fora da fila: duplicatas / saidas provaveis (nunca oncologicos) ----
fora = f.sugestao_retirar_da_fila & ~f.onc
f[fora].to_csv("fora_da_fila_para_confirmacao.csv", index=False)
fila = f[~fora].copy()
for col, pos in [("score_regras", "pos_regras"), ("score_risco", "pos_risco")]:
    ordem = fila.sort_values([col, "dias_em_fila"], ascending=False).solicitacao_id
    fila[pos] = fila.solicitacao_id.map({sid: i + 1 for i, sid in enumerate(ordem)})
fila["mudanca_pelo_risco"] = fila.pos_regras - fila.pos_risco            # positivo = subiu com o risco
fila["posicao"] = fila.pos_risco if COM_RISCO else fila.pos_regras
fila["score"] = fila.score_risco if COM_RISCO else fila.score_regras
fila = fila.sort_values("posicao").reset_index(drop=True)


def justificar(r, com_risco):
    sc = r.score_risco if com_risco else r.score_regras
    txt = (f"{r.classe} (prazo {P.PRAZO[r.classe]} d): {r.motivo} | {r.dias_em_fila} d em fila "
           f"= {r.dias_em_fila / P.PRAZO[r.classe]:.1f}x o prazo | score {sc:.0f}/1000")
    if com_risco and r.pts_risco:
        txt += f" | risco previsto de piora {r.prob_piora:.0%} (+{r.pts_risco:.0f})"
    if r.pedido_medico:
        txt += " | pedido do medico no texto (+3)"
    if r.diabetes_descomp:
        txt += " | diabetes descompensando (+3)"
    # dados ausentes: dizemos que faltou e o que foi feito (ausencia NUNCA e lida como "sem gravidade")
    faltas = []
    if r.dor_eva_imputada:
        faltas.append(f"dor nao informada (usada a mediana do mesmo CID: {int(r.intensidade_dor_eva)}/10)")
    if r.limitacao_imputada:
        faltas.append(f"limitacao nao informada (usado o valor mais comum do mesmo CID: {r.limitacao_funcional})")
    if pd.isna(r.asa):
        faltas.append("ASA nao informado (sem pontos de ASA; ausencia nao significa baixo risco)")
    if (r.flag_diabetico == "sim" or r.diabetes_evidenciado) and pd.isna(r.hba1c_ultima):
        faltas.append("diabetes sem HbA1c (descompensacao nao avaliada)")
    if faltas:
        txt += " | DADO AUSENTE: " + "; ".join(faltas)
    if r.esquecido:
        txt += f" | ALERTA ESQUECIDO: espera ha {r.dias_em_fila / P.PRAZO[r.classe]:.0f}x o prazo" + (f" (+{r.pts_esquecido:.0f} pts)" if r.pts_esquecido else "")
    return txt


fila["justificativa"] = fila.apply(lambda r: justificar(r, COM_RISCO), axis=1)
fila[["solicitacao_id", "posicao", "justificativa"]].to_csv("fila_priorizada.csv", index=False)

# ordem so com regras (para o regulador comparar as duas)
sr = fila.sort_values("pos_regras")[["solicitacao_id", "pos_regras"]].rename(columns={"pos_regras": "posicao"})
sr["justificativa"] = fila.set_index("solicitacao_id").loc[sr.solicitacao_id].apply(lambda r: justificar(r, False), axis=1).values
sr.to_csv("fila_priorizada_so_regras.csv", index=False)
fila.to_csv("fila_priorizada_detalhada.csv", index=False)

print(fila.classe.value_counts().sort_index().to_string())
print("na fila:", len(fila), "| fora (confirmar):", int(fora.sum()), "| com risco de piora:", COM_RISCO)
print("alerta esquecido (>3x prazo):", int(fila.esquecido.sum()), "| com bonus (>5x):", int((fila.pts_esquecido > 0).sum()))
if COM_RISCO:
    print("pontos de risco: +40:", int((fila.pts_risco == 40).sum()), "| +20:", int((fila.pts_risco == 20).sum()),
          "| mudam de posicao (>=10):", int((fila.mudanca_pelo_risco.abs() >= 10).sum()))
