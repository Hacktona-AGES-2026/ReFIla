const API_URL = import.meta.env.VITE_API_URL ?? "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
    throw new Error(detail ?? `Erro ${response.status} ao acessar ${path}`);
  }
  return response.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

export const fetchOptions = () => request("/opcoes");
export const fetchQueue = (filters) => request(`/fila?${new URLSearchParams(filters)}`);
export const fetchPatient = (id, ordem) => request(`/pacientes/${id}?ordem=${ordem}`);
export const fetchReview = () => request("/revisao");
export const fetchAudit = () => request("/auditoria");
export const addEvent = (id, event) => post(`/pacientes/${id}/eventos`, event);
export const addDecision = (id, decision) => post(`/pacientes/${id}/decisao`, decision);
export const resetDemo = () => post("/reiniciar", {});

export const patientLogin = (acesso) => post("/paciente/entrar", acesso);
export const patientAnswers = (acesso, respostas) => post("/paciente/respostas", { ...acesso, respostas });
export const patientReport = (acesso, texto) => post("/paciente/relato", { ...acesso, texto });
export const resolveReport = (id, acao, regulador) => post(`/relatos/${id}/resolver`, { acao, regulador });
