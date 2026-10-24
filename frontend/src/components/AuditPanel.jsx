import { useEffect, useState } from "react";
import { fetchAudit, resetDemo } from "../api";
import { capitalize, formatDate, formatDateTime, humanize, ORDER_LABELS } from "../format";

const QUALITY_LABELS = {
  recebidas: "solicitações recebidas",
  fora_da_fila: "fora da fila (regulador confirma)",
  alertas_cadastro: "alertas de cadastro",
  dor_imputada: "dor preenchida pelo CID",
  esquecidos: "esperando mais de 3x o prazo",
};

export default function AuditPanel({ refreshKey, onSelect, onReset }) {
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState("");
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    fetchAudit()
      .then(setAudit)
      .catch((e) => setError(e.message));
  }, [refreshKey]);

  async function reset() {
    setResetting(true);
    try {
      await resetDemo();
      onReset();
    } catch (e) {
      setError(e.message);
    } finally {
      setResetting(false);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!audit) return <p className="muted">Carregando...</p>;

  return (
    <section>
      <div className="stats">
        {Object.entries(audit.qualidade_dados).map(([key, value]) => (
          <div className="stat" key={key}>
            <strong>{value}</strong>
            <span>{QUALITY_LABELS[key] ?? humanize(key)}</span>
          </div>
        ))}
      </div>

      <ClassDistribution classes={audit.classes} total={audit.pacientes_na_fila} />
      <Decisions decisions={audit.decisoes} onSelect={onSelect} />
      <NewEvents events={audit.eventos_novos} onSelect={onSelect} />
      <OutOfQueue items={audit.fora_da_fila} />

      <div className="card">
        <h3>Demonstração</h3>
        <p className="muted">Apaga eventos e decisões de teste e recalcula a fila só com o dataset.</p>
        <button className="secondary" onClick={reset} disabled={resetting}>
          {resetting ? "Reiniciando..." : "Reiniciar demonstração"}
        </button>
      </div>
    </section>
  );
}

function ClassDistribution({ classes, total }) {
  return (
    <div className="card">
      <h3>{total} pacientes na fila, por classe</h3>
      <div className="class-bars">
        {Object.entries(classes).map(([classe, n]) => (
          <div className="class-bar" key={classe}>
            <span className="mono">{classe}</span>
            <div className="track">
              <div className={`fill classe-${classe}`} style={{ width: `${(100 * n) / total}%` }} />
            </div>
            <span className="mono">{n}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Decisions({ decisions, onSelect }) {
  return (
    <div className="card table-wrap">
      <h3>Decisões do regulador ({decisions.length})</h3>
      {decisions.length === 0 ? (
        <p className="muted">Nenhuma decisão registrada ainda.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Quando</th>
              <th>Quem</th>
              <th>Solicitação</th>
              <th>Ordem</th>
              <th>Posição</th>
              <th>Motivo</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((d) => (
              <tr key={`${d.data_hora}-${d.solicitacao_id}`} className="clickable" onClick={() => onSelect(d.solicitacao_id)}>
                <td>{formatDateTime(d.data_hora)}</td>
                <td>{d.regulador}</td>
                <td className="mono">{d.solicitacao_id}</td>
                <td>{ORDER_LABELS[d.ordem_usada] ?? d.ordem_usada}</td>
                <td className="mono">
                  {d.posicao_proposta}º → {d.posicao_final}º
                </td>
                <td>{d.motivo}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function NewEvents({ events, onSelect }) {
  if (events.length === 0) return null;
  return (
    <div className="card table-wrap">
      <h3>Eventos lançados pelo regulador ({events.length})</h3>
      <table>
        <tbody>
          {events.map((ev) => (
            <tr key={ev.evento_id} className="clickable" onClick={() => onSelect(ev.solicitacao_id)}>
              <td>{formatDate(ev.data_evento)}</td>
              <td className="mono">{ev.solicitacao_id}</td>
              <td>
                {humanize(ev.tipo_evento)}: {humanize(ev.resultado)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OutOfQueue({ items }) {
  return (
    <div className="card table-wrap">
      <h3>Fora da fila, aguardando confirmação ({items.length})</h3>
      <p className="muted">Duplicatas e prováveis saídas. Nenhuma é oncológica.</p>
      <table>
        <thead>
          <tr>
            <th>Solicitação</th>
            <th>Paciente</th>
            <th>Procedimento</th>
            <th>Motivo</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="mono">{item.id}</td>
              <td>{item.nome}</td>
              <td>{capitalize(item.procedimento)}</td>
              <td>{item.motivo}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
