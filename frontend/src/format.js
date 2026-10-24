export const formatDate = (iso) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("pt-BR");

export const formatDateTime = (iso) =>
  new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

export const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

export const humanize = (code) => capitalize(code.replaceAll("_", " "));

export const ORDER_LABELS = { com_risco: "Com risco previsto", so_regras: "Só regras" };

export const ORDER_HELP = {
  com_risco:
    "Ordem oficial. Primeiro vem a classe (regras clínicas); dentro de cada classe, o score soma tempo na fila, gravidade e " +
    "o risco previsto de piora: um modelo estatístico que estima a chance de o paciente piorar (+20 pontos se for 30% ou mais, " +
    "+40 se for 40% ou mais). O risco só reordena dentro da classe: ele nunca move um paciente de A para B, por exemplo. ▲ e ▼ mostram quem mudou 10 posições ou mais por causa dele.",
  so_regras:
    "A mesma fila sem o modelo: classe e score calculados só com regras (tempo na fila, dor, limitação, diabetes, ASA). " +
    "Serve de comparação: ao alternar, você vê exatamente o que o risco previsto muda.",
};
