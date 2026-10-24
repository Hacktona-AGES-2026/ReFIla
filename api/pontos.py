"""Tabela de pontos do score (0 a 1000).

score = base da classe SWALIS + tempo de espera + gravidade (+ risco de piora, opcional)

Regra de segurança: tempo + gravidade + risco (max 150) e MENOR que a distancia
entre duas classes (min 170), entao ninguem "pula" de classe por pontos extras.
"""

# 1) Base da classe (decide o "andar" do paciente)
BASE = {"A1": 850, "A2": 680, "B": 480, "C": 280, "D": 80}

# Prazo maximo de espera por classe, em dias (referencias/swalis.csv)
PRAZO = {"A1": 15, "A2": 21, "B": 60, "C": 180, "D": 360}

# 2) Maximos dos pontos extras
TEMPO_LINEAR_MAX = 45     # tempo de espera: sobe linear ate 3x o prazo da classe
ESQUECIDO_BONUS = 15      # bonus para quem passou de 5x o prazo (so dentro da classe)
ESQUECIDO_ALERTA_X = 3    # alerta "esquecido" quando passa de 3x o prazo
ESQUECIDO_BONUS_X = 5
TEMPO_MAX = TEMPO_LINEAR_MAX + ESQUECIDO_BONUS   # 60 no total (o teto de 1000 nao muda)
GRAV_MAX = 50
RISCO_MAX = 40

# 3) Risco de piora (vem da regressao): probabilidade -> pontos
RISCO_ALTO, RISCO_MOD = 0.40, 0.30     # >=40% = +40 | >=30% = +20


def x_prazo(dias_em_fila, classe):
    """Quantas vezes o prazo da classe o paciente ja esperou."""
    return dias_em_fila / PRAZO[classe]


def pontos_tempo(dias_em_fila, classe):
    """0 a 45. Sobe de forma linear ate o paciente esperar 3x o prazo da classe."""
    return TEMPO_LINEAR_MAX * min(x_prazo(dias_em_fila, classe), 3) / 3


def pontos_esquecido(dias_em_fila, classe):
    """0 ou 15. Bonus para o paciente 'esquecido' (mais de 5x o prazo da classe)."""
    return ESQUECIDO_BONUS if x_prazo(dias_em_fila, classe) > ESQUECIDO_BONUS_X else 0


def esquecido(dias_em_fila, classe):
    """Alerta: passou de 3x o prazo (o tempo linear ja chegou no teto)."""
    return x_prazo(dias_em_fila, classe) > ESQUECIDO_ALERTA_X


def pontos_gravidade(dor, limitacao, n_sinais_piora, asa, diabetes_descomp, texto_pede_atencao):
    """0 a 50, somando sinais clinicos."""
    p = 2 * dor                                                   # ate 20
    p += {"grave": 12, "moderada": 6, "leve": 2}.get(limitacao, 0)  # ate 12
    p += 3 * min(n_sinais_piora, 3)                               # ate 9
    p += 3 if asa and asa >= 3 else 0                             # 3
    p += 3 if diabetes_descomp else 0                             # 3
    p += 3 if texto_pede_atencao else 0                           # 3
    return min(p, GRAV_MAX)


def pontos_risco(prob_piora):
    """0, 20 ou 40, conforme a probabilidade de piora."""
    if prob_piora >= RISCO_ALTO:
        return RISCO_MAX
    if prob_piora >= RISCO_MOD:
        return RISCO_MAX / 2
    return 0


def score(classe, dias_em_fila, dor, limitacao, n_sinais_piora=0, asa=None,
          diabetes_descomp=False, texto_pede_atencao=False, prob_piora=None):
    s = BASE[classe] + pontos_tempo(dias_em_fila, classe) + pontos_esquecido(dias_em_fila, classe)
    s += pontos_gravidade(dor, limitacao, n_sinais_piora, asa, diabetes_descomp, texto_pede_atencao)
    if prob_piora is not None:
        s += pontos_risco(prob_piora)
    return round(s, 1)


# ---- auto-teste: a regra de seguranca vale e o teto e 1000 ----
_ordem = ["A1", "A2", "B", "C", "D"]
_extras = TEMPO_MAX + GRAV_MAX + RISCO_MAX
for _a, _b in zip(_ordem, _ordem[1:]):
    assert BASE[_a] - BASE[_b] > _extras, f"{_a} e {_b} muito proximos"
assert BASE["A1"] + _extras == 1000


if __name__ == "__main__":
    print("Teto:", BASE["A1"] + _extras)
    # Vera (C50.4, A2 se estavel): 607 dias, dor 2, limitacao nenhuma
    print("Exemplo A2, 607 d, dor 2:", score("A2", 607, 2, "nenhuma"))
    # pior caso possivel
    print("A1 maximo:", score("A1", 999, 10, "grave", 3, 4, True, True, 0.9))
    # melhor caso da classe de cima x pior da de baixo
    print("A2 maximo:", score("A2", 999, 10, "grave", 3, 4, True, True, 0.9),
          "| A1 minimo:", score("A1", 0, 0, "nenhuma"))