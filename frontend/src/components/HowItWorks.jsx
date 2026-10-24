export default function HowItWorks() {
  return (
    <div className="portal">
      <header className="portal-top"><a className="brand-title small" href="#/">Re<span>Fila</span></a><a className="link" href="#/paciente">Área do paciente</a></header>
      <main className="portal-main prose">
        <h2>Como funciona a fila</h2>
        <p className="lead">Priorizamos pela <strong>necessidade clínica</strong>, não só pela ordem de chegada. Casos podem mudar de posição a qualquer momento.</p>
        <h3>O que a equipe leva em conta</h3>
        <p>O tipo de problema de saúde, os sintomas e como eles estão evoluindo, e também há quanto tempo a pessoa espera. Quem espera muito não é esquecido: a espera longa também conta.</p>
        <h3>Por que uma posição pode mudar</h3>
        <p>Um exame novo, uma ida ao pronto-socorro ou uma informação atualizada podem mudar a avaliação. Por isso é importante contar à equipe quando algo muda na sua saúde.</p>
        <h3>Quem decide</h3>
        <p>O sistema sugere uma ordem, e um profissional de saúde confere e decide. Cada mudança fica registrada.</p>
        <h3>Por que não mostramos a posição</h3>
        <p>A posição muda com frequência e depende de cada caso. Mostrar um número isolado poderia causar ansiedade ou uma falsa ideia de injustiça, e informações de outras pessoas nunca são exibidas.</p>
        <p className="muted">Esta página não substitui orientação médica. Em caso de piora importante, procure atendimento.</p>
      </main>
    </div>
  );
}
