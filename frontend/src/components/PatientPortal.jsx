import { useState } from "react";
import { patientAnswers, patientLogin, patientReport } from "../api";
import { formatDate } from "../format";

export default function PatientPortal() {
  const [acesso, setAcesso] = useState(null);
  const [info, setInfo] = useState(null);
  return (
    <div className="portal">
      <header className="portal-top">
        <a className="brand-title small" href="#/">Re<span>Fila</span></a>
        <nav className="portal-nav">
          <a className="link" href="#/como-funciona">Como funciona a fila</a>
          {info && <button className="link" onClick={() => { setInfo(null); setAcesso(null); }}>Sair</button>}
        </nav>
      </header>
      <main className="portal-main">
        {info ? <Home info={info} acesso={acesso} /> : <Login onEnter={(a, i) => { setAcesso(a); setInfo(i); }} />}
      </main>
      <footer className="portal-foot">Protótipo. Suas informações vão para a equipe, que decide o que fazer. Esta área não substitui atendimento médico.</footer>
    </div>
  );
}

function Login({ onEnter }) {
  const [protocolo, setProtocolo] = useState("");
  const [nome, setNome] = useState("");
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErro("");
    const acesso = { protocolo: protocolo.trim(), primeiro_nome: nome.trim() };
    try { onEnter(acesso, await patientLogin(acesso)); } catch (err) { setErro(err.message); } finally { setBusy(false); }
  }
  return (
    <form className="card form login" onSubmit={submit}>
      <h2>Entrar na área do paciente</h2>
      <p className="muted">Use o número do protocolo da sua solicitação e o seu primeiro nome.</p>
      <label>Protocolo<input value={protocolo} onChange={(e) => setProtocolo(e.target.value)} placeholder="SOL-2025-00118" required /></label>
      <label>Primeiro nome<input value={nome} onChange={(e) => setNome(e.target.value)} autoComplete="given-name" required /></label>
      <button className="primary" disabled={busy}>{busy ? "Entrando..." : "Entrar"}</button>
      {erro && <p className="error" role="alert">{erro}</p>}
    </form>
  );
}

function Home({ info, acesso }) {
  const [aberto, setAberto] = useState(false);
  const primeiro = info.nome.split(" ")[0];
  const passos = [
    ["Solicitação registrada", `Em ${formatDate(info.data_entrada)}.`, true],
    ...(info.revisada_em ? [["Revisada pela regulação", `Em ${formatDate(info.revisada_em)}.`, true]] : []),
    ["Aguardando agendamento", "A equipe define a data conforme a necessidade clínica.", false],
  ];
  return (
    <>
      <p className="eyebrow">Enquanto você espera</p>
      <h2 className="greet">Olá, {primeiro}! Veja como está sua solicitação.</h2>
      <div className="card">
        <span className="tag">Solicitação ativa</span>
        <h3>{info.procedimento}</h3>
        <p className="big-wait"><strong>{info.dias_em_fila}</strong> dias de espera <span className="muted">(contados até {formatDate(info.contado_ate)})</span></p>
        <p className="muted">O tempo de espera, sozinho, não indica uma data para a cirurgia. A equipe considera os critérios clínicos e as informações mais recentes.</p>
        {info.ultimo_evento && <p className="muted">Última atualização no seu caso: {formatDate(info.ultimo_evento)}.</p>}
      </div>
      <div className="card">
        <h3>Sua jornada</h3>
        <ol className="steps">
          {passos.map(([titulo, texto, feito]) => (
            <li key={titulo} className={feito ? "done" : "current"}><strong>{titulo}</strong><span>{texto}</span></li>
          ))}
        </ol>
      </div>
      <div className="card">
        <h3>Sua saúde mudou?</h3>
        {aberto ? <Questions info={info} acesso={acesso} onClose={() => setAberto(false)} /> : (
          <>
            <p className="muted">São 2 ou 3 perguntas curtas, escolhidas para o seu caso. Se algo mudou, a equipe pode precisar reavaliar.</p>
            <button className="primary" onClick={() => setAberto(true)}>Responder perguntas</button>
          </>
        )}
      </div>
      {info.pergunta_aberta && <OpenReport info={info} acesso={acesso} />}
      <p className="muted">Precisa de ajuda? Tenha em mãos o protocolo <strong>{info.protocolo}</strong> ao falar com a unidade de saúde. Em caso de piora importante ou sintomas novos, procure atendimento.</p>
    </>
  );
}

function Questions({ info, acesso, onClose }) {
  const [vals, setVals] = useState({});
  const [res, setRes] = useState(null);
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErro("");
    try { setRes(await patientAnswers(acesso, info.perguntas.map((q) => ({ id: q.id, valor: vals[q.id] })))); }
    catch (err) { setErro(err.message); } finally { setBusy(false); }
  }
  if (res) {
    return (
      <div role="status">
        {res.urgente && <p className="error"><strong>Procure atendimento agora.</strong> Vá a uma UPA ou pronto-socorro, ou ligue 192 (SAMU). Não espere a resposta da equipe.</p>}
        <p className="success">Respostas enviadas. A equipe vai ver {res.alertas > 0 ? "e dar atenção ao que você relatou" : "o que você contou"}. O envio não muda sua posição automaticamente.</p>
        <button className="link" onClick={onClose}>Fechar</button>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="questions">
      {info.perguntas.map((q) => (
        <fieldset key={q.id}>
          <legend>{q.texto}</legend>
          {q.opcoes.map((o) => (
            <label key={o.valor} className="opt">
              <input type="radio" name={q.id} value={o.valor} required checked={vals[q.id] === o.valor} onChange={() => setVals({ ...vals, [q.id]: o.valor })} />
              {o.rotulo}
            </label>
          ))}
        </fieldset>
      ))}
      <div className="row">
        <button className="primary" disabled={busy}>{busy ? "Enviando..." : "Enviar respostas"}</button>
        <button type="button" className="link" onClick={onClose}>Cancelar</button>
      </div>
      {erro && <p className="error" role="alert">{erro}</p>}
    </form>
  );
}

function OpenReport({ info, acesso }) {
  const [texto, setTexto] = useState("");
  const [res, setRes] = useState(null);
  const [erro, setErro] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErro("");
    try { setRes(await patientReport(acesso, texto)); setTexto(""); }
    catch (err) { setErro(err.message); } finally { setBusy(false); }
  }
  return (
    <div className="card">
      <h3>Conte com as suas palavras</h3>
      <p>{info.pergunta_aberta.texto}</p>
      {res ? (
        <div role="status">
          {res.urgente && <p className="error"><strong>Procure atendimento agora.</strong> Vá a uma UPA ou pronto-socorro, ou ligue 192 (SAMU). Não espere a resposta da equipe.</p>}
          <p className="success">Recebemos o seu relato. A equipe vai ler e decidir o que fazer. O envio não muda sua posição automaticamente.</p>
          <button className="link" onClick={() => setRes(null)}>Escrever outro</button>
        </div>
      ) : (
        <form onSubmit={submit} className="questions">
          <label>Seu relato
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={4} maxLength={1000} minLength={3} required
              placeholder="Escreva como se sente, desde quando e se melhorou ou piorou." />
          </label>
          <div className="row"><button className="primary" disabled={busy}>{busy ? "Enviando..." : "Enviar relato"}</button></div>
          {erro && <p className="error" role="alert">{erro}</p>}
        </form>
      )}
      <p className="muted">{info.pergunta_aberta.aviso}</p>
      {info.pergunta_aberta.origem === "llm" && <p className="muted"><small>Pergunta redigida com apoio de inteligência artificial.</small></p>}
    </div>
  );
}
