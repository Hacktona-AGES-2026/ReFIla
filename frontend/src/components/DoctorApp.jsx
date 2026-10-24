import { useEffect, useState } from "react";
import { fetchOptions } from "../api";
import AuditPanel from "./AuditPanel";
import PatientDetail from "./PatientDetail";
import QueueList from "./QueueList";
import ReviewList from "./ReviewList";
import SearchBox from "./SearchBox";

const TABS = { queue: "Fila", review: "Revisão", audit: "Auditoria" };

export default function DoctorApp() {
  const [tab, setTab] = useState("queue");
  const [options, setOptions] = useState(null);
  const [order, setOrder] = useState("com_risco");
  const [selectedId, setSelectedId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchOptions()
      .then(setOptions)
      .catch((e) => setError(e.message));
  }, []);

  function openPatient(id) {
    setSelectedId(id);
    window.scrollTo(0, 0);
  }

  const refresh = () => setRefreshKey((k) => k + 1);

  function renderMain() {
    if (!options) return <p className="muted">{error ? "" : "Carregando..."}</p>;
    if (selectedId) {
      return (
        <PatientDetail
          patientId={selectedId}
          order={order}
          eventTypes={options.eventos}
          onBack={() => setSelectedId(null)}
          onChanged={refresh}
        />
      );
    }
    if (tab === "review") return <ReviewList refreshKey={refreshKey} onSelect={openPatient} />;
    if (tab === "audit") return <AuditPanel refreshKey={refreshKey} onSelect={openPatient} onReset={refresh} />;
    return (
      <QueueList
        options={options}
        order={order}
        onOrderChange={setOrder}
        refreshKey={refreshKey}
        onSelect={openPatient}
      />
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          Re<span>Fila</span>
        </h1>
        <p>A classe vem de regras clínicas; os pontos só ordenam dentro dela. O sistema propõe, o regulador decide.</p>
        <nav>
          <a className="link" href="#/">Trocar perfil</a>
          {Object.entries(TABS).map(([key, label]) => (
            <button
              key={key}
              className={tab === key && !selectedId ? "active" : ""}
              onClick={() => {
                setTab(key);
                setSelectedId(null);
              }}
            >
              {label}
            </button>
          ))}
          <SearchBox onSelect={openPatient} />
        </nav>
      </header>

      <main>
        {error && <p className="error">Não foi possível falar com a API: {error}</p>}
        {renderMain()}
      </main>
    </div>
  );
}
