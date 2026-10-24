"""Leitura do texto livre (justificativa_clinica + observacoes) por expressoes de ALTA PRECISAO.

Principio: so entram expressoes que, no texto do medico, indicam gravidade de verdade.
Palavras soltas como 'obstru' ou 'sangr' NAO entram (pegam 'sintomas obstrutivos moderados').
Cada achado devolve o TRECHO que casou, para o regulador conferir.
"""
import re
import unicodedata


def normalizar(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


# Negacao logo antes do termo ("sem sinais de encarceramento") anula o achado
NEGACAO = re.compile(r"(?:sem|nega|descartad[oa]|ausencia de)\s+(?:sinais? de\s+)?$")

# NIVEL 1 -> risco de vida ou de perda de orgao/funcao  (equivale a A1)
NIVEL1 = re.compile(
    r"estrangul|encarcer|hernia irredutivel|irredutivel nas ultimas|colangite|sepse|hemoptise|"
    r"dessaturacao|angina em repouso|angina instavel|sincope|retencao urinaria aguda|"
    r"retencao de co2|transfund|enterorragia|suboclus|hematemese|melena|pancreatite|"
    r"lesao de tronco|cate: tronco|dano neurologico|perda de funcao|hidronefrose importante|"
    r"anemia grave|glaucoma facomorfico|hipoventilacao")

# NIVEL 2 -> sinais de agravamento  (equivale a pelo menos B; em oncologico, empurra pra A1)
NIVEL2 = re.compile(
    r"linfonodo(?! sentinela)|ulcera de pressao|sangramento espontaneo|crescimento rapido|rouquidao|psa em elevacao|massa palpavel|"
    r"perda ponderal|disfagia(?! leve)|ictericia|coluria|dor em piora|dor incapacitante|"
    r"quedas? de repeticao|celulite recorrente|dor ossea|acamad|dor em repouso|internacao|"
    r"nodulo em crescimento|lesao ulcerada de mama")

# O medico/oncologia pediu prioridade (+3 pontos de gravidade)
PEDIDO_MEDICO = re.compile(
    r"medico assistente (?:pede|solicitou)|medico solicitante pede atencao|"
    r"oncologia solicita agilizar|prioridade alta solicitada|cirurgia com prioridade")


def _achar(padrao, t):
    """Primeiro trecho que casa e NAO esta negado."""
    for m in padrao.finditer(t):
        antes = t[max(0, m.start() - 25):m.start()]
        if not NEGACAO.search(antes):
            return t[max(0, m.start() - 10):m.end() + 25].strip()
    return None


def ler_texto(justificativa, observacoes):
    """-> (nivel 0/1/2, trecho que casou, pedido_do_medico True/False)"""
    t = normalizar(f"{justificativa if justificativa == justificativa else ''} "
                   f"{observacoes if observacoes == observacoes else ''}")
    pedido = bool(PEDIDO_MEDICO.search(t))
    trecho = _achar(NIVEL1, t)
    if trecho:
        return 1, trecho, pedido
    trecho = _achar(NIVEL2, t)
    if trecho:
        return 2, trecho, pedido
    return 0, "", pedido