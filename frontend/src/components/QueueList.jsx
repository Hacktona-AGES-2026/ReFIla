import { useEffect, useState } from "react";
import { fetchQueue } from "../api";
import { capitalize, ORDER_LABELS, ORDER_HELP } from "../format";
import ClassBadge from "./ClassBadge";

const hasAlert = (p) => p.esquecido || p.diabetes_descomp || p.conferir_cadastro;

// Quantas posições o risco previsto de piora mudou em relação à ordem só com regras.
function RiskShift({ delta }) {
  if (Math.abs(delta) < 10) return <span className="delta" />;
  const up = delta > 0;
  return (
    <span className={`delta ${up ? "sobe" : ""}`} title="Mudança de posição causada pelo risco previsto de piora">
      {up ? "▲" : "▼"}
      {Math.abs(delta)}
    </span>
  );
}

export default function QueueList({ options, order, onOrderChange, refreshKey, onSelect }) {
  const [queue, setQueue] = useState([]);
  const [specialty, setSpecialty] = useState("");
  const [support, setSupport] = useState("");
  const [onlyAlerts, setOnlyAlerts] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    fetchQueue({ ordem: order, especialidade: specialty, apoio: support })
      .then(setQueue)
      .catch((e) => setError(e.message));
  }, [order, specialty, support, refreshKey]);

  const visible = onlyAlerts ? queue.filter(hasAlert) : queue;
  const filtered = specialty || support;

  return (
    <section>
      <div className="segmented" role="group" aria-label="Ordem da fila">
        {options.ordens.map((key) => (
          <button key={key} className={order === key ? "active" : ""} onClick={() => onOrderChange(key)}>
            {ORDER_LABELS[key]}
          </button>
        ))}
      </div>
      <p className="order-help">{ORDER_HELP[order]}</p>

      <div className="filters">
        <select value={specialty} onChange={(e) => setSpecialty(e.target.value)} aria-label="Especialidade">
          <option value="">Todas as especialidades</option>
          {options.especialidades.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
        <select value={support} onChange={(e) => setSupport(e.target.value)} aria-label="Especialidade de apoio">
          <option value="">Sem filtro de apoio</option>
          {options.apoio.map((name) => (
            <option key={name} value={name}>
              Apoio: {name}
            </option>
          ))}
        </select>
      </div>

      <div className="toolbar">
        <p className="muted">
          {queue.length} pacientes{filtered && " no filtro (posição na fila inteira)"},{" "}
          {queue.filter(hasAlert).length} com alerta
        </p>
        <label className="toggle">
          <input type="checkbox" checked={onlyAlerts} onChange={(e) => setOnlyAlerts(e.target.checked)} />
          Só alertas
        </label>
      </div>

      {error && <p className="error">{error}</p>}
      <ol className="queue">
        {visible.map((patient) => (
          <li key={patient.id}>
            <button className={`queue-row classe-${patient.classe}`} onClick={() => onSelect(patient.id)}>
              <span className="position">{patient.posicao}º</span>
              <span className="who">
                <strong>{patient.nome}</strong>
                <small>
                  {capitalize(patient.procedimento)} · {patient.cid}
                </small>
              </span>
              {patient.conferir_cadastro && <span className="badge alerta">cadastro</span>}
              {patient.diabetes_descomp && <span className="badge alerta">diabetes</span>}
              {patient.esquecido && <span className="badge">esquecido</span>}
              {order === "com_risco" && <RiskShift delta={patient.mudanca_pelo_risco} />}
              <ClassBadge classe={patient.classe} />
              <span className="score">{patient.score}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
