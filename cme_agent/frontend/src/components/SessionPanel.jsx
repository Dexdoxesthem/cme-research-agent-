import { api, fmtUsd } from '../api.js'

export default function SessionPanel({ session, setSession, config, onToast }) {
  if (!session || !config) return <div className="card">loading session…</div>
  const pnl = session.realized_pnl || 0
  const limit = config.daily_loss_limit
  const frac = Math.min(1, Math.max(0, -pnl / limit))
  const cls = pnl > 0 ? 'pos' : pnl < 0 ? 'neg' : ''

  const reset = async () => {
    if (!confirm('Reset today\'s session P&L?')) return
    await api.post('/session/reset', {})
    setSession(await api.get('/session'))
    onToast('Session reset')
  }

  return (
    <div className="card">
      <div className="h-row">
        <h2 style={{ margin: 0 }}>Session P&L</h2>
        <button className="btn ghost small" onClick={reset}>reset</button>
      </div>
      <div className={`pnl-big ${cls}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(0)}</div>
      <div className="progress"><div className="bar" style={{ width: `${frac * 100}%` }} /></div>
      <div className="muted small">
        {session.trades.length} trade(s) · daily loss limit {fmtUsd(limit)}
        {pnl <= -limit && <div className="limit-hit">DAILY LOSS LIMIT REACHED — no new positions</div>}
        {pnl <= -0.7 * limit && pnl > -limit && <div className="limit-near">Approaching daily loss limit — reduce size or stand down</div>}
      </div>
      <div className="log-list">
        {session.trades.slice().reverse().map((t, i) => (
          <div key={i} className="log-item">
            {t.time} {t.symbol} {t.side} ×{t.contracts} @{t.entry}→{t.exit}{' '}
            <span className={t.pnl >= 0 ? 'pos' : 'neg'}>{t.pnl >= 0 ? '+' : ''}{t.pnl}</span>
          </div>
        ))}
        {session.trades.length === 0 && <div className="muted">no trades today</div>}
      </div>
    </div>
  )
}
