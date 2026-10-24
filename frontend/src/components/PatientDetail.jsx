import { useCallback, useEffect, useState } from "react";
import { addDecision, addEvent, fetchPatient, resolveReport } from "../api";
import { capitalize, formatDate, formatDateTime, humanize, ORDER_LABELS } from "../format";
import ClassBadge from "./ClassBadge";

export default function PatientDetail({ patientId, order, eventTypes, onBack, onChanged }) {
  const [patient, setPatient] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetchPatient(patientId, order)
      .then(setPatient)
      .catch((e) => setError(e.message));
  }, [patientId, order]);

  useEffect(load, [load]);

  function handleChanged() {
    load();
    onChanged();
  }

  if (error) return <p className="error">{error}</p>;
  if (!patient) return <p className="muted">Carregando...</p>;

  return (
    <section>
      <button className="link" onClick={onBack}>
        ← Voltar
      </button>

      <div className="card">
        <div className="detail-head">
          <div>
            <small className="muted mono">{patient.id}</small>
            <h2>{patient.nome}</h2>
            <p className="muted">
              {capitalize(patient.procedimento)} · {patient.especialidade}
            </p>
          </div>
          <div>
            <span className="big-number">{patient.posicao}º</span> <ClassBadge classe={patient.classe} />
            <p className="muted">
              {ORDER_LABELS[order]} · score {patient.score}/1000
            </p>
          </div>
        </div>
        <dl className="facts">
          <Fact label="CID" value={`${patient.cid} · ${patient.cid_descricao}`} />
          <Fact label="Por que esta classe" value={capitalize(patient.motivo_classe.split(" | ")[0])} />
          <Fact label="Espera" value={`${patient.dias_em_fila} dias (prazo ${patient.prazo_dias} d)`} />
          <Fact label="Prioridade manual (não usada)" value={capitalize(patient.prioridade_manual)} />
          <Fact label="Idade · município" value={`${patient.idade} anos · ${patient.municipio}`} />
        </dl>
      </div>

      {patient.alertas.length > 0 && (
        <div className="card">
          <h3>Alertas para conferir</h3>
          <ul className="alerts">
            {patient.alertas.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="columns">
        <ScoreBreakdown parts={patient.composicao_score} total={patient.score} />
        <div className="card">
          <h3>Justificativa gerada</h3>
          <p className="muted">{patient.justificativa}</p>
        </div>
      </div>

      {patient.relatos_paciente?.length > 0 && (
        <div className="card">
          <h3>Relatos do paciente</h3>
          <ul className="timeline">
            {patient.relatos_paciente.map((r) => (
              <li key={r.mensagem_id}>
                {r.sinal_de_alerta && <span className="badge alerta">Sinal de alerta</span>} <strong>{r.resumo}</strong>
                <br /><small>{formatDateTime(r.data_hora)} · tendência: {r.tendencia} · resumo por {r.origem_resumo === "llm" ? "IA" : "regras"} · {r.status}</small>
                <br /><small className="muted">Texto original: {r.texto_original}</small>
                {r.status === "pendente" && (
                  <div className="row">
                    <button className="primary" onClick={() => resolveReport(r.mensagem_id, "aceitar", "regulador").then(handleChanged)}>Aceitar como evento ({humanize(r.evento_sugerido)})</button>
                    <button className="link" onClick={() => resolveReport(r.mensagem_id, "descartar", "regulador").then(handleChanged)}>Descartar</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <p className="muted">É o relato do paciente, não validado. Só muda a fila se você aceitar.</p>
        </div>
      )}

      {patient.respostas_paciente?.length > 0 && (
        <div className="card">
          <h3>Respostas do paciente</h3>
          <ul className="timeline">
            {patient.respostas_paciente.map((r, i) => (
              <li key={i}>
                {r.alerta && <span className="badge alerta">Atenção</span>} <strong>{r.resposta}</strong>
                <br /><small>{formatDateTime(r.data_hora)} · {r.pergunta}</small>
              </li>
            ))}
          </ul>
          <p className="muted">Não altera a prioridade sozinho. Quem decide é o regulador.</p>
        </div>
      )}

      <ClinicalText patient={patient} />
      <Events events={patient.eventos} />

      <div className="columns">
        <EventForm patientId={patient.id} eventTypes={eventTypes} onSaved={handleChanged} />
        <DecisionForm patient={patient} order={order} onSaved={handleChanged} />
      </div>
    </section>
  );
}

function Fact({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function ScoreBreakdown({ parts, total }) {
  return (
    <div className="card">
      <h3>De onde vem o score</h3>
      <ul className="breakdown">
        {parts.map((part) => (
          <li key={part.label}>
            <span>{part.label}</span>
            <span>+{part.points}</span>
          </li>
        ))}
        <li>
          <span>Total</span>
          <span>{total}</span>
        </li>
      </ul>
    </div>
  );
}

function ClinicalText({ patient }) {
  if (!patient.justificativa_clinica && !patient.observacoes) return null;
  return (
    <div className="card">
      <h3>Texto livre</h3>
      {patient.justificativa_clinica && <p className="quote">Médico: {patient.justificativa_clinica}</p>}
      {patient.observacoes && <p className="quote">Regulação: {patient.observacoes}</p>}
    </div>
  );
}

function Events({ events }) {
  return (
    <div className="card">
      <h3>Eventos durante a espera ({events.length})</h3>
      {events.length === 0 && <p className="muted">Nenhum evento registrado.</p>}
      <ul className="timeline">
        {events.map((ev) => (
          <li key={ev.evento_id}>
            <strong>{humanize(ev.tipo_evento)}</strong>: {humanize(ev.resultado)}
            {ev.valor_numerico != null && ` (${ev.valor_numerico})`}
            <br />
            <small>
              {formatDate(ev.data_evento)} · {ev.origem}
              {ev.descricao && ` · ${ev.descricao}`}
            </small>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EventForm({ patientId, eventTypes, onSaved }) {
  const types = Object.keys(eventTypes);
  const [type, setType] = useState(types[0]);
  const [result, setResult] = useState(eventTypes[types[0]][0]);
  const [description, setDescription] = useState("");
  const [outcome, setOutcome] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function changeType(next) {
    setType(next);
    setResult(eventTypes[next][0]);
  }

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = { tipo: type, resultado: result };
      if (description.trim()) body.descricao = description.trim();
      setOutcome(await addEvent(patientId, body));
      setDescription("");
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h3>Lançar evento novo</h3>
      <p className="muted">A fila inteira é recalculada na hora.</p>
      <div className="form-row">
        <select value={type} onChange={(e) => changeType(e.target.value)} aria-label="Tipo do evento">
          {types.map((t) => (
            <option key={t} value={t}>
              {humanize(t)}
            </option>
          ))}
        </select>
        <select value={result} onChange={(e) => setResult(e.target.value)} aria-label="Resultado">
          {eventTypes[type].map((r) => (
            <option key={r} value={r}>
              {humanize(r)}
            </option>
          ))}
        </select>
      </div>
      <input
        type="text"
        placeholder="Descrição (opcional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <button className="primary" disabled={saving}>
        {saving ? "Recalculando..." : "Lançar e recalcular"}
      </button>
      {error && <p className="error">{error}</p>}
      {outcome && <EventOutcome outcome={outcome} />}
    </form>
  );
}

function EventOutcome({ outcome }) {
  const moved = outcome.posicao_antes !== outcome.posicao_depois;
  const changedClass = outcome.classe_antes !== outcome.classe_depois;
  return (
    <p className="success">
      Posição {outcome.posicao_antes}º → {outcome.posicao_depois}º
      {moved && outcome.ultrapassados > 0 && ` (passou à frente de ${outcome.ultrapassados})`}.{" "}
      {changedClass
        ? `Mudou de classe: ${outcome.classe_antes} → ${outcome.classe_depois}.`
        : `Continua na classe ${outcome.classe_depois}.`}
    </p>
  );
}

function DecisionForm({ patient, order, onSaved }) {
  const [reason, setReason] = useState("");
  const [regulator, setRegulator] = useState("");
  const [position, setPosition] = useState("");
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const body = { motivo: reason, ordem: order, regulador: regulator.trim() || "regulador" };
      if (position) body.posicao = Number(position);
      setSaved(await addDecision(patient.id, body));
      setReason("");
      setPosition("");
      onSaved();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      <h3>Decisão do regulador</h3>
      <p className="muted">
        Sem posição nova, aceita a proposta ({patient.posicao}º). Oncológico nunca desce.
      </p>
      <div className="form-row">
        <input type="text" placeholder="Seu nome" value={regulator} onChange={(e) => setRegulator(e.target.value)} />
        <input
          type="number"
          min="1"
          placeholder="Nova posição"
          value={position}
          onChange={(e) => setPosition(e.target.value)}
        />
      </div>
      <textarea
        rows="2"
        required
        placeholder="Motivo (obrigatório)"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <button className="primary" disabled={!reason.trim()}>
        Registrar decisão
      </button>
      {error && <p className="error">{error}</p>}
      {saved && (
        <p className="success">
          Registrado: {saved.posicao_proposta}º → {saved.posicao_final}º.
        </p>
      )}
      <DecisionHistory decisions={patient.decisoes} />
    </form>
  );
}

function DecisionHistory({ decisions }) {
  if (decisions.length === 0) return null;
  return (
    <ul className="timeline">
      {decisions.map((d) => (
        <li key={d.data_hora}>
          <strong>{d.regulador}</strong>: {d.posicao_proposta}º → {d.posicao_final}º
          <br />
          <small>
            {formatDateTime(d.data_hora)} · {d.motivo}
          </small>
        </li>
      ))}
    </ul>
  );
}
