import { useState } from 'react'
import { fmt } from '../api.js'

function StatCell({ k, v, accent }) {
  return (
    <div className="kv-cell">
      <div className="k">{k}</div>
      <div className={`v ${accent || ''}`}>{v}</div>
    </div>
  )
}

export default function BacktestPanel({ contracts, backtest, loading, onRun }) {
  const [sym, setSym] = useState('MES')
  const [period, setPeriod] = useState('3y')

  const b = backtest?.data
  return (
    <div className="card">
      <div className="h-row">
        <h2 style={{ margin: 0 }}>Backtest <span className="muted">(built-in trend+RSI setup)</span></h2>
      </div>
      <div className="inst-row" style={{ margin: '10px 0' }}>
        <select value={sym} onChange={(e) => setSym(e.target.value)}>
          {(contracts ? Object.keys(contracts) : ['MES', 'MGC', 'MCL', 'ZN']).map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="2y">2 years</option>
          <option value="3y">3 years</option>
          <option value="5y">5 years</option>
        </select>
        <button className="btn primary" onClick={() => onRun(sym, period)} disabled={loading}>
          {loading ? 'Running…' : 'Run'}
        </button>
        {backtest && <span className="muted small">last: {backtest.sym} · {backtest.period}</span>}
      </div>

      {!b && !loading && <div className="muted">Not run yet — click Run to walk history for setups and report sample-size-annotated stats.</div>}
      {loading && <div className="loading-line">Walking historical bars…</div>}

      {b && b.error && <div className="error-box">{b.error}</div>}
      {b && !b.error && (
        <>
          {!b.sample_size && <div className="muted">{b.note || 'No setups matched in history.'}</div>}
          {b.sample_size > 0 && (
            <>
              <div className="kv-grid" style={{ marginBottom: 10 }}>
                <StatCell k="Sample size" v={b.sample_size} />
                <StatCell k="Win rate" v={`${(b.win_rate * 100).toFixed(1)}%`} accent={b.win_rate >= 0.5 ? 'pos' : 'neg'} />
                <StatCell k="Avg R / trade" v={b.avg_r} accent={b.avg_r >= 0 ? 'pos' : 'neg'} />
                <StatCell k="Expectancy (R)" v={b.expectancy_r} accent={b.expectancy_r >= 0 ? 'pos' : 'neg'} />
                <StatCell k="Stop hits" v={`${(b.stop_hit_pct * 100).toFixed(0)}%`} />
                <StatCell k="Target hits" v={`${(b.target_hit_pct * 100).toFixed(0)}%`} />
                <StatCell k="Time exits" v={`${(b.time_exit_pct * 100).toFixed(0)}%`} />
              </div>
              {b.longs && (
                <div className="muted small" style={{ marginBottom: 8 }}>
                  Longs: n={b.longs.n}, win {(b.longs.win_rate * 100).toFixed(1)}%, avgR {b.longs.avg_r}
                  &nbsp;|&nbsp; Shorts: n={b.shorts.n}, win {(b.shorts.win_rate * 100).toFixed(1)}%, avgR {b.shorts.avg_r}
                </div>
              )}
              <div className="sec">
                <h3>Recent signals ({b.sample_size} total)</h3>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr><th>date</th><th>dir</th><th>entry</th><th>stop</th><th>target</th><th>R</th><th>exit</th></tr>
                    </thead>
                    <tbody>
                      {b.recent_trades.map((t, i) => (
                        <tr key={i}>
                          <td>{t.date}</td><td>{t.direction}</td>
                          <td className="num">{fmt(t.entry)}</td><td className="num">{fmt(t.stop)}</td>
                          <td className="num">{fmt(t.target)}</td>
                          <td className={`num ${t.r_outcome > 0 ? 'pos' : t.r_outcome < 0 ? 'neg' : ''}`}>{t.r_outcome}</td>
                          <td>{t.exit_reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="muted small">{b.note}</div>
            </>
          )}
        </>
      )}
    </div>
  )
}
