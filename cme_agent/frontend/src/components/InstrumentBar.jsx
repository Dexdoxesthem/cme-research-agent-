export default function InstrumentBar({ universe, selected, onSelect, onAll, onScan, busy }) {
  const groups = universe || {}
  const order = ['equity', 'rates', 'metals', 'energy', 'ag', 'fx', 'crypto']
  const labels = {
    equity: 'Equity Index', rates: 'Rates', metals: 'Metals',
    energy: 'Energy', ag: 'Agriculture', fx: 'FX', crypto: 'Crypto',
  }

  const coreSyms = Object.values(groups)
    .flatMap((g) => g.members || [])
    .filter((m) => m.core)
    .map((m) => m.symbol)

  return (
    <div className="card">
      <div className="h-row">
        <h2 style={{ margin: 0 }}>Instrument Universe</h2>
        <div className="inst-actions">
          <button className="btn" onClick={onAll} disabled={busy}>Analyze Core</button>
          <button className="btn primary" onClick={onScan} disabled={busy}>Scan Full Universe</button>
        </div>
      </div>

      {Object.keys(groups).length === 0 ? (
        <div className="muted small">universe not loaded</div>
      ) : (
        order.filter((g) => groups[g]).map((g) => (
          <div key={g} className="inst-group">
            <div className="inst-group-label">
              {labels[g]}
              <span className="muted small"> · {groups[g].members.length}</span>
              {g === 'equity' && <span className="pill ok core-pill">core: {coreSyms.join(' ')}</span>}
            </div>
            <div className="inst-row">
              {groups[g].members.map((m) => (
                <button
                  key={m.symbol}
                  className={`btn inst ${selected === m.symbol ? 'active' : ''} ${m.core ? 'core' : 'watch'}`}
                  onClick={() => onSelect(m.symbol)}
                  disabled={busy}
                  title={m.description}
                >
                  {m.symbol} <small>{m.name}</small>
                </button>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
