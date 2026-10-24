"""acolhimento.py — area do paciente: pergunta direcionada + relato simples para o medico.

O paciente NAO ve posicao nem score. Ele recebe UMA pergunta curta, adaptada ao caso dele, e escreve
com as proprias palavras se melhorou ou piorou. O relato vira um resumo para o regulador e entra como
mensagem PENDENTE (mensagens_paciente.csv): NAO altera a fila sozinho; o regulador aceita ou descarta.

A pergunta vem de (nesta ordem):
  1. perguntas_pacientes.csv  -> gerado por LLM com  python gerar_perguntas.py  (vai no repo; rodar o front NAO precisa de chave)
  2. LLM na hora, se houver chave (variavel LLM_API_KEY) e o caso nao estiver no arquivo
  3. pergunta-modelo por especialidade (plano B, sem LLM e sem internet)

O LLM so PERGUNTA e RESUME. Nao diagnostica, nao da conselho e nao decide urgencia.
Os sinais de alerta (falta de ar, sangramento...) sao detectados por REGRAS, nunca so pelo LLM.

Uso:
  python acolhimento.py pergunta SOL-2026-00489
  python acolhimento.py relato SOL-2026-00489 "a dor aumentou e tive febre ontem"
"""
import datetime as dt
import json
import os
import sys
import unicodedata
import urllib.request

import pandas as pd

DET = "fila_priorizada_detalhada.csv"
PERGUNTAS = "perguntas_pacientes.csv"
MENSAGENS = "mensagens_paciente.csv"

AVISO_EMERGENCIA = ("Se você estiver com dor muito forte, falta de ar, dor no peito, febre alta, vômitos que não param "
                    "ou sangramento, não espere: procure o pronto-socorro ou ligue 192 (SAMU).")

# ------------------------------------------------------------------ plano B: perguntas-modelo por especialidade
# (rascunho nosso: em producao, um profissional de saude reveria estes textos)
SINAIS = {
    "Cirurgia Geral": "a regiao ficou mais dolorida, dura ou inchada; vomitos; febre; dificuldade para evacuar; pele ou olhos amarelados",
    "Cirurgia Oncologica": "perda de peso sem querer; sangramento; dor nova; dificuldade para engolir ou se alimentar; caroco que cresceu",
    "Ortopedia": "dor em repouso ou a noite; mais dificuldade para andar ou apoiar o peso; queda recente",
    "Urologia": "dor nas costas ou na lateral; febre; dificuldade para urinar; sangue na urina",
    "Oftalmologia": "visao mais embacada; dor no olho; olho vermelho; luzes ou manchas novas",
    "Mastologia": "nodulo que cresceu; secrecao; dor ou vermelhidao na mama",
    "Cirurgia Vascular": "dor ou inchaco na perna; ferida que nao cicatriza; vermelhidao; sangramento de varizes",
    "Ginecologia": "sangramento fora do normal; dor na barriga ou na pelve; febre",
    "Cirurgia de Cabeca e Pescoco": "caroco que cresceu; rouquidao; dificuldade para engolir ou respirar",
    "Coloproctologia": "sangramento; dor forte; dificuldade para evacuar",
    "Cirurgia Cardiaca": "dor ou aperto no peito; falta de ar; desmaio ou tontura; inchaco nas pernas",
    "Cirurgia Bariatrica": "diabetes, pressao ou sono pior; falta de ar; dor na barriga",
    "Cirurgia Toracica": "falta de ar; tosse com sangue; dor no peito; perda de peso sem querer",
    "Otorrinolaringologia": "mais dificuldade para respirar pelo nariz; dor de ouvido; febre; sangramento",
}
SINAIS_PADRAO = "dor mais forte; febre; sangramento; piora para fazer as atividades do dia a dia"


def pergunta_modelo(procedimento, especialidade):
    sinais = SINAIS.get(especialidade, SINAIS_PADRAO)
    proc = str(procedimento).strip().lower()
    return (f"Desde a ultima atualizacao do seu cadastro, algo mudou em relacao a sua cirurgia ({proc})? "
            f"Por exemplo: {sinais}. Pode contar tambem se melhorou. Escreva com as suas palavras.")


# ------------------------------------------------------------------ regras de alerta e tendencia (NAO dependem de LLM)
def _sa(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).lower()


ALERTA = ["falta de ar", "dor no peito", "aperto no peito", "desmai", "sangramento", "sangrando", "sangue", "vomit",
          "febre", "dor muito forte", "dor forte", "insuportavel", "nao consigo urinar", "nao consigo evacuar",
          "perdi a visao", "perda de visao", "pus", "ferida aberta", "nao consigo respirar"]
PIORA = ["piorou", "pior", "aumentou", "mais dor", "inchou", "inchaco", "mais forte", "cresceu", "dificuldade", "nao consigo"]
MELHORA = ["melhorou", "melhor", "diminuiu", "passou", "sem dor", "estou bem", "aliviou"]
NEGA = ["sem febre", "nao tive febre", "nao tem febre", "sem sangramento", "nao tive sangramento", "nao sangrou"]


def analisar_regras(texto):
    t = _sa(texto)
    for n in NEGA:                               # "sem febre" nao pode acender o alerta de febre
        t = t.replace(n, " ")
    alertas = [a for a in ALERTA if a in t]
    p = sum(w in t for w in PIORA)
    m = sum(w in t for w in MELHORA)
    tendencia = "piora" if (alertas or p > m) else ("melhora" if m > p else "sem_mudanca")
    return alertas, tendencia


# ------------------------------------------------------------------ LLM (opcional, so com chave)
def carregar_env():
    """Le .env (se existir) para as variaveis de ambiente. A chave NUNCA vai para o GitHub."""
    if os.path.exists(".env"):
        for ln in open(".env", encoding="utf-8"):
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.strip().split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def tem_chave():
    carregar_env()
    return bool(os.environ.get("LLM_API_KEY"))


def chamar_llm(system, user, json_mode=False, timeout=40):
    """Chat Completions (OpenAI). Modelo em LLM_MODEL; endereco em LLM_BASE_URL (para trocar de servico)."""
    carregar_env()
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    corpo = {"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"), "temperature": 0.3,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        corpo["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(corpo).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["LLM_API_KEY"]})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()


SYS_PERGUNTA = (
    "Voce ajuda a equipe de uma fila de cirurgias eletivas. Escreva UMA pergunta curta (ate 60 palavras), em portugues "
    "simples e acolhedor, para o paciente contar se algo mudou (melhora ou piora) desde a ultima atualizacao do cadastro. "
    "Cite 2 ou 3 sinais de alerta especificos para a condicao dele, como exemplos. REGRAS: nao faca diagnostico; nao de "
    "conselho medico; nunca diga se algo e grave ou nao; NAO cite o nome do diagnostico (o paciente pode nao ter sido informado): fale da cirurgia ou da regiao do corpo; nao peca dados pessoais; termine convidando o paciente a escrever "
    "com as proprias palavras. Responda apenas com a pergunta.")

SYS_RESUMO = (
    "Voce resume o relato de um paciente de uma fila cirurgica para o regulador (profissional de saude). Nao diagnostique, "
    "nao interprete alem do texto e nao invente nada. Responda em JSON com as chaves: resumo (ate 40 palavras, fiel ao que "
    "o paciente disse), sinais (lista de sintomas citados), tendencia (um de: piora, melhora, sem_mudanca, incerto).")


def contexto_paciente(r, eventos=None):
    """So o necessario ao LLM: SEM nome, id, municipio ou qualquer dado que identifique."""
    c = {"procedimento": r.procedimento, "especialidade": r.especialidade, "diagnostico": r.cid_descricao,
         "tempo_na_fila": f"{int(r.dias_em_fila // 30)} meses", "dor_0_a_10": int(r.intensidade_dor_eva),
         "limitacao": r.limitacao_funcional}
    if eventos is not None:
        c["ultimos_eventos"] = eventos
    return c


def gerar_pergunta_llm(r, eventos=None):
    p = chamar_llm(SYS_PERGUNTA, json.dumps(contexto_paciente(r, eventos), ensure_ascii=False))
    if not (15 <= len(p) <= 600) or "SOL-" in p:      # trava simples contra resposta estranha
        raise ValueError("pergunta fora do esperado")
    return p


# ------------------------------------------------------------------ pergunta para um paciente (usada pelo front)
def _det():
    if not os.path.exists(DET):
        sys.exit("Rode antes: python risco_piora.py && python priorizar.py")
    return pd.read_csv(DET)


def pergunta_para(solicitacao_id, usar_llm_na_hora=True):
    """Devolve (pergunta, origem). origem: 'llm' (arquivo ou na hora) ou 'modelo' (plano B)."""
    if os.path.exists(PERGUNTAS):
        c = pd.read_csv(PERGUNTAS)
        c = c[c.solicitacao_id == solicitacao_id]
        if len(c):
            return c.iloc[0].pergunta, c.iloc[0].origem
    d = _det()
    r = d[d.solicitacao_id == solicitacao_id]
    if r.empty:
        raise KeyError("solicitacao nao esta na fila")
    r = next(r.itertuples())
    if usar_llm_na_hora and tem_chave():
        try:
            return gerar_pergunta_llm(r), "llm"
        except Exception:
            pass                                    # qualquer falha cai no plano B, sem tela de erro
    return pergunta_modelo(r.procedimento, r.especialidade), "modelo"


# ------------------------------------------------------------------ relato do paciente -> mensagem pendente
def resumir_relato(texto, pergunta=""):
    """Devolve (resumo, sinais, tendencia, origem). Os alertas vem SEMPRE das regras."""
    alertas, tend_regras = analisar_regras(texto)
    if tem_chave():
        try:
            j = json.loads(chamar_llm(SYS_RESUMO, json.dumps({"pergunta": pergunta, "relato": texto}, ensure_ascii=False), json_mode=True, timeout=20))
            tend = j.get("tendencia", "incerto")
            if alertas and tend in ("melhora", "sem_mudanca"):
                tend = "piora"                      # se as regras acharam alerta, o LLM nao pode "tranquilizar"
            return str(j.get("resumo", "")).strip(), "; ".join(map(str, j.get("sinais", []))), tend, "llm"
        except Exception:
            pass
    sinais = "; ".join(alertas)
    return (texto.strip()[:200] + ("..." if len(texto.strip()) > 200 else "")), sinais, tend_regras, "regras"


def registrar_relato(solicitacao_id, texto):
    texto = texto.strip()
    if not texto:
        raise ValueError("relato vazio")
    pergunta, _ = pergunta_para(solicitacao_id, usar_llm_na_hora=False)   # a mesma pergunta que o paciente viu
    resumo, sinais, tend, origem = resumir_relato(texto, pergunta)
    alertas, _ = analisar_regras(texto)
    n = len(pd.read_csv(MENSAGENS)) if os.path.exists(MENSAGENS) else 0
    ev = {"piora": "relata_piora", "melhora": "relata_melhora"}.get(tend, "atendeu")
    m = pd.DataFrame([{"mensagem_id": f"MSG-{n + 1:04d}", "data_hora": dt.datetime.now().isoformat(timespec="seconds"),
                       "solicitacao_id": solicitacao_id, "pergunta": pergunta, "texto_original": texto, "resumo": resumo,
                       "sinais": sinais, "tendencia": tend, "sinal_de_alerta": bool(alertas), "origem_resumo": origem,
                       "evento_sugerido": ev, "status": "pendente"}])
    m.to_csv(MENSAGENS, mode="a", header=not os.path.exists(MENSAGENS), index=False)
    return m.iloc[0]


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "pergunta":
        p, o = pergunta_para(sys.argv[2])
        print(f"[{o}] {p}\n\n{AVISO_EMERGENCIA}")
    elif len(sys.argv) >= 4 and sys.argv[1] == "relato":
        m = registrar_relato(sys.argv[2], " ".join(sys.argv[3:]))
        print(f"Recebemos. Sua mensagem ({m.mensagem_id}) foi encaminhada para analise da equipe de saude.\n"
              "Ela NAO muda a sua posicao automaticamente: um profissional vai avaliar.\n\n" + AVISO_EMERGENCIA)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
