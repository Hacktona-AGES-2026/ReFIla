export default function Landing() {
  return (
    <div className="landing">
      <h1 className="brand-title">Re<span>Fila</span></h1>
      <p className="landing-lead">A fila mede o tempo de espera. A ReFila mede como a pessoa está agora.</p>
      <h2 className="landing-ask">Como você quer entrar?</h2>
      <div className="landing-choices">
        <a className="choice" href="#/paciente">
          <strong>Sou paciente</strong>
          <span>Acompanhar minha solicitação e contar como estou.</span>
        </a>
        <a className="choice" href="#/medico">
          <strong>Sou médico ou regulador</strong>
          <span>Ver a fila, revisar casos e registrar decisões.</span>
        </a>
      </div>
      <a className="link" href="#/como-funciona">Como funciona a fila</a>
    </div>
  );
}
