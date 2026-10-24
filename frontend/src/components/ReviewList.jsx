import { useEffect, useState } from "react";
import { fetchReview } from "../api";
import ClassBadge from "./ClassBadge";

export default function ReviewList({ refreshKey, onSelect }) {
  const [review, setReview] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchReview()
      .then(setReview)
      .catch((e) => setError(e.message));
  }, [refreshKey]);

  if (error) return <p className="error">{error}</p>;
  if (!review) return <p className="muted">Carregando...</p>;

  return (
    <section>
      <div className="stats">
        <div className="stat">
          <strong>{review.atrasados}</strong>
          <span>de {review.total} sem atualização no prazo</span>
        </div>
        <div className="stat">
          <strong>½ prazo</strong>
          <span>intervalo de revisão de cada classe (A1 7,5 d · D 180 d)</span>
        </div>
      </div>

      <div className="card table-wrap">
        <h3>Quem revisar primeiro ({review.lista.length} mais atrasados)</h3>
        <table>
          <thead>
            <tr>
              <th>Paciente</th>
              <th>Classe</th>
              <th>Posição</th>
              <th>Sem atualizar</th>
              <th>Atraso</th>
            </tr>
          </thead>
          <tbody>
            {review.lista.map((p) => (
              <tr key={p.id} className="clickable" onClick={() => onSelect(p.id)}>
                <td>{p.nome}</td>
                <td>
                  <ClassBadge classe={p.classe} />
                </td>
                <td className="mono">{p.posicao}º</td>
                <td className="mono">
                  {p.dias_sem_atualizar} d <small className="muted">(a cada {p.intervalo} d)</small>
                </td>
                <td className="mono">{p.vezes_acima}x</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
