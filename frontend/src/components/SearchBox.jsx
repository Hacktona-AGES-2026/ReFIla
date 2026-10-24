import { useEffect, useRef, useState } from "react";
import { fetchQueue } from "../api";
import { capitalize } from "../format";
import ClassBadge from "./ClassBadge";

// tira acentos e deixa minúsculo: "Hérnia" casa com "hernia"
const norm = (s) =>
  String(s ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();

export default function SearchBox({ onSelect }) {
  const [patients, setPatients] = useState([]);
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  // carrega a fila uma vez; a busca roda no navegador
  useEffect(() => {
    fetchQueue({ ordem: "com_risco" })
      .then(setPatients)
      .catch(() => {});
  }, []);

  // fecha ao clicar fora
  useEffect(() => {
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const terms = norm(text).split(/\s+/).filter(Boolean);
  const results = terms.length
    ? patients
        .filter((p) => {
          const alvo = norm(`${p.nome} ${p.id} ${p.procedimento} ${p.cid}`);
          return terms.every((t) => alvo.includes(t));
        })
        .slice(0, 8)
    : [];

  function pick(p) {
    onSelect(p.id);
    setText("");
    setOpen(false);
  }

  return (
    <div className="search" ref={box}>
      <svg className="search-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M20 20l-4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <input
        type="text"
        value={text}
        placeholder="Buscar paciente, protocolo, cirurgia ou CID"
        aria-label="Buscar paciente"
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && results[0]) pick(results[0]);
          if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && terms.length > 0 && (
        <ul className="search-results">
          {results.length === 0 && <li className="search-empty">Nenhum paciente encontrado.</li>}
          {results.map((p) => (
            <li key={p.id}>
              <button onClick={() => pick(p)}>
                <span className="who">
                  <strong>{p.nome}</strong>
                  <small>
                    {p.id} · {capitalize(p.procedimento)} · {p.cid}
                  </small>
                </span>
                <span className="muted">{p.posicao}º</span>
                <ClassBadge classe={p.classe} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
