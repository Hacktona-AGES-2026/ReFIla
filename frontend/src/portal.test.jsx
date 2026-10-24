// Testes de interface da area do paciente. Rodam contra a API real:
//   VITE_API_URL=http://localhost:8000 npm test
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import HowItWorks from "./components/HowItWorks";
import Landing from "./components/Landing";
import PatientPortal from "./components/PatientPortal";

afterEach(cleanup);
const api = describe.skipIf(!import.meta.env.VITE_API_URL);

async function entrar(protocolo, nome) {
  const user = userEvent.setup();
  render(<PatientPortal />);
  await user.type(screen.getByLabelText("Protocolo"), protocolo);
  await user.type(screen.getByLabelText("Primeiro nome"), nome);
  await user.click(screen.getByRole("button", { name: "Entrar" }));
  return user;
}

describe("telas sem API", () => {
  it("a tela inicial leva para paciente e medico", () => {
    render(<Landing />);
    expect(screen.getByRole("link", { name: /Sou paciente/ }).getAttribute("href")).toBe("#/paciente");
    expect(screen.getByRole("link", { name: /Sou médico/ }).getAttribute("href")).toBe("#/medico");
  });
  it("Como funciona a fila traz a frase do criterio", () => {
    render(<HowItWorks />);
    expect(screen.getByText(/necessidade clínica/)).toBeTruthy();
    expect(screen.getByText(/mudar de posição a qualquer momento/)).toBeTruthy();
  });
});

api("area do paciente com a API real", () => {
  it("login errado mostra erro e nao entra", async () => {
    await entrar("SOL-2025-00118", "Zzz");
    expect((await screen.findByRole("alert")).textContent).toMatch(/Não encontramos/);
  });
  it("login certo mostra o nome e nunca posicao, classe ou score", async () => {
    await entrar("sol-2025-00118", "salete");
    expect(await screen.findByText(/Olá, Salete!/)).toBeTruthy();
    expect(screen.getByText("Enquanto você espera")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\d+º|classe|score|prioridade/i);
  });
  it("perguntas do caso e alerta de urgencia", async () => {
    const user = await entrar("SOL-2025-00118", "Salete");
    await user.click(await screen.findByRole("button", { name: "Responder perguntas" }));
    const hernia = screen.getByRole("group", { name: /hérnia/i });
    await user.click(within(hernia).getByLabelText("Sim"));
    await user.click(within(screen.getByRole("group", { name: /pronto-socorro/i })).getByLabelText("Não"));
    await user.click(screen.getByRole("button", { name: "Enviar respostas" }));
    expect((await screen.findByRole("status")).textContent).toMatch(/Procure atendimento agora/);
  });
  it("relato livre com sinal de alerta mostra a orientacao de urgencia (regras, sem depender de LLM)", async () => {
    const user = await entrar("SOL-2025-00118", "Salete");
    await user.type(await screen.findByLabelText(/Seu relato/), "tive falta de ar e sangramento hoje");
    await user.click(screen.getByRole("button", { name: "Enviar relato" }));
    const status = await screen.findByRole("status");
    expect(status.textContent).toMatch(/Procure atendimento agora/);
    expect(status.textContent).toMatch(/não muda sua posição/);
  });
  it("relato livre sem alerta so confirma o recebimento", async () => {
    const user = await entrar("SOL-2025-00118", "Salete");
    await user.type(await screen.findByLabelText(/Seu relato/), "estou melhor, a dor passou");
    await user.click(screen.getByRole("button", { name: "Enviar relato" }));
    const status = await screen.findByRole("status");
    expect(status.textContent).toMatch(/Recebemos o seu relato/);
    expect(status.textContent).not.toMatch(/Procure atendimento agora/);
  });
});
