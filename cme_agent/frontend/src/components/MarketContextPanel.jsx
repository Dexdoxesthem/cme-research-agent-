export default function MarketContextPanel({ ctx, onRefresh }) {
  if (!ctx) return <div className="card"><div className="loading-line">Loading market context…</div></div>

  const groups = ctx.groups || {}
  const order = ['equity', 'rates', 'metals', 'energy', 'ag', 'fx', 'crypto']
  const labels = {
    equity: 'Equity Index', rates: 'Rates (bond px)', metals: 'Metals',
    energy: 'Energy', ag: 'Agriculture', fx: 'FX', crypto: 'Crypto',
  }

  return (
    <div className="card ctx-card">
      <div className="h-row">
        <h2 style={{ margin: 0 }}>Market Context <span className="muted">(cross-asset)</span></h2>
        <button className="btn ghost small" onClick={onRefresh}>refresh scan</button>
      </div>
      <div className="ctx-line">“{ctx.one_line}”</div>

      <div className="ctx-grid">
        {order.filter((g) => groups[g]).map((g) => {
          const m = groups[g]
          const cls = m.avg_change > 0.15 ? 'pos' : m.avg_change < -0.15 ? 'neg' : ''
          return (
            <div key={g} className="ctx-cell" title={`Leader ${m.leader} (${m.leader_pct}%), laggard ${m.laggard} (${m.laggard_pct}%)`}>
              <div className="k">{labels[g]}</div>
              <div className={`v ${cls}`}>{m.avg_change > 0 ? '+' : ''}{m.avg_change}%</div>
              <div className="sub muted">n={m.n} · lead {m.leader} <span className={m.leader_pct > 0 ? 'pos' : 'neg'}>({m.leader_pct > 0 ? '+' : ''}{m.leader_pct}%)</span></div>
            </div>
          )
        })}
      </div>

      {ctx.divergences?.length > 0 && (
        <div className="divergences">
          {ctx.divergences.map((d, i) => <div key={i} className="flag warn">{d}</div>)}
        </div>
      )}
      <div className="muted small" style={{ marginTop: 6 }}>Group avg = mean % change of members · scan {ctx.timestamp ? new Date(ctx.timestamp).toLocaleTimeString() : ''}</div>
    </div>
  )
}
