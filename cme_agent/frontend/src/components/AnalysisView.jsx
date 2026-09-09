import { useEffect, useState } from 'react'
import { api, fmt, fmtUsd } from '../api.js'
import PriceChart from './PriceChart.jsx'

function Flag({ f }) {
  const cls = /loss limit|blocked/i.test(f) ? 'bad' : /stale|failure/i.test(f) ? 'warn' : 'warn'
  return <div className={`flag ${cls}`}>{f}</div>
}

function Snapshot({ d }) {
  const cells = [
    ['Price', fmt(d.price)], ['Day High', fmt(d.day_high)], ['Day Low', fmt(d.day_low)],
    ['Day %', d.change_pct === null ? '—' : `${fmt(d.change_pct, 2)}%`],
    ['Sector', d.group || '—'],
    ['20SMA', fmt(d.ma20)], ['50SMA', fmt(d.ma50)], ['200SMA', fmt(d.ma200)],
    ['RSI(14)', fmt(d.rsi14, 1)], ['ATR(14)', fmt(d.atr14, 3)],
    ['Vol (day)', d.volume ? d.volume.toLocaleString() : '—'],
    ['Rating', d.technical_rating?.rating || '—'],
    ['Data', `${d.stale ? 'STALE · ' : ''}${new Date(d.fetch_time).toLocaleTimeString()}`],
  ]
  return (
    <div className="kv-grid">
      {cells.map(([k, v]) => (
        <div key={k} className="kv-cell"><div className="k">{k}</div><div className="v">{v}</div></div>
      ))}
    </div>
  )
}

function PositionTable({ p }) {
  if (p.blocked) return <div className="flag bad">POSITION BLOCKED — {p.reason}</div>
  const rows = [
    ['Direction', p.direction.toUpperCase()],
    ['Entry zone', `${fmt(Math.min(...p.entry_zone))} – ${fmt(Math.max(...p.entry_zone))}`],
    ['Entry reference', fmt(p.entry_ref)],
    ['Stop', fmt(p.stop)],
    ['Stop distance', `${fmt(p.stop_distance_points)} pts (${p.stop_distance_ticks} ticks)`],
    ['Risk / contract', fmtUsd(p.risk_per_contract, 2)],
    ['Risk budget (2%)', fmtUsd(p.risk_budget, 0)],
    ['Max contracts allowed', p.max_contracts],
    ['Suggested contracts', `${p.suggested_contracts} (${p.suggested_ratio_pct}% of max)`],
    ['Total risk @ suggested', `${fmtUsd(p.total_risk_suggested, 2)} (${fmt(p.total_risk_pct_account, 2)}% acct)`],
    ['Target', fmt(p.target)],
    ['Reward', `${fmt(p.reward_points)} pts`],
    ['R:R', p.rr],
  ]
  return (
    <table>
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}><th>{k}</th><td className="num">{v}</td></tr>
        ))}
      </tbody>
    </table>
  )
}

function SignalBanner({ signal }) {
  const cls = signal.includes('BULLISH') ? 'bull' : signal.includes('BEARISH') ? 'bear' : 'flat'
  return <div className={`signal-banner ${cls}`}>SIGNAL: {signal}</div>
}

function AllSummary({ all, onPick }) {
  const syms = Object.keys(all)
  return (
    <div className="all-summary">
      {syms.map((sym) => {
        const r = all[sym]
        const cls = r.signal.includes('BULLISH') ? 'bull' : r.signal.includes('BEARISH') ? 'bear' : 'flat'
        const d = r.data || {}
        return (
          <button key={sym} className={`signal-banner sm ${cls}`} onClick={() => onPick(sym)}>
            <strong>{sym}</strong> — {r.signal}
            {d.group && <span className="muted small"> · {d.group}{d.change_pct != null ? ` · ${d.change_pct > 0 ? '+' : ''}${d.change_pct}%` : ''}</span>}
          </button>
        )
      })}
      <div className="muted small">Click a card for the full detail view.</div>
    </div>
  )
}

export default function AnalysisView({ result, sym, all, contracts, onPick, onBacktest, onSize }) {
  const [chart, setChart] = useState(null)
  const [chartErr, setChartErr] = useState(null)
  const [sizing, setSizing] = useState(false)

  const activeSym = all ? Object.keys(all)[0] : sym

  useEffect(() => {
    let cancelled = false
    setChart(null); setChartErr(null)
    if (!activeSym) return
    api.get(`/chart/${activeSym}?period=6mo`)
      .then((c) => { if (!cancelled) setChart(c) })
      .catch((e) => { if (!cancelled) setChartErr(e.message) })
    return () => { cancelled = true }
  }, [activeSym])

  if (all) {
    return (
      <div className="card results">
        <h2>Analysis — {Object.keys(all).length} instruments</h2>
        <AllSummary all={all} onPick={onPick} />
      </div>
    )
  }

  if (result.data?.error) {
    return <div className="card results"><div className="error-box">{result.data.error}</div></div>
  }

  const d = result.data
  const watchlist = d.core === false

  return (
    <div className="card results">
      <h2>Analysis — {d.name} ({d.symbol}) <span className="muted">· {d.group}</span></h2>
      <SignalBanner signal={result.signal} />

      {chartErr && <div className="error-box">{chartErr}</div>}
      {chart && <PriceChart data={chart.bars} />}

      {result.cross_asset?.line && (
        <div className="sec">
          <h3>Cross-asset context</h3>
          <div className="ctx-line" style={{ fontSize: 13 }}>{result.cross_asset.line}</div>
          {result.cross_asset.peers?.divergent && (
            <div className="flag warn">Diverging from its sector group — treat the move as less confirmed.</div>
          )}
        </div>
      )}

      <div className="sec">
        <h3>Risk flags</h3>
        {result.risk_flags?.length
          ? result.risk_flags.map((f, i) => <Flag key={i} f={f} />)
          : <div className="flag ok">No material risk flags.</div>}
      </div>

      <div className="sec"><h3>Data snapshot</h3><Snapshot d={d} /></div>

      <div className="sec">
        <h3>Why</h3>
        <ul>{result.why.map((w, i) => <li key={i}>{w}</li>)}</ul>
      </div>

      {result.position && (
        <div className="sec">
          <div className="h-row">
            <h3 style={{ margin: 0 }}>Position framework</h3>
            <button className="btn ghost small" onClick={() => onBacktest(d.symbol, '3y')}>Backtest this setup</button>
          </div>
          <PositionTable p={result.position} />
        </div>
      )}

      {watchlist && !result.position && (
        <div className="sec">
          <h3>Position framework</h3>
          <div className="flag warn">Watchlist asset — report only, no size by default.</div>
          {sizing
            ? <div className="loading-line">Requesting explicit sizing…</div>
            : <button className="btn primary small" onClick={() => { setSizing(true); onSize(d.symbol, true) }}>Size this position explicitly</button>}
        </div>
      )}

      {result.backtest?.note && (
        <div className="sec"><h3>Backtest context</h3><div className="muted">{result.backtest.note}</div></div>
      )}

      <div className="sec"><h3>Invalidation</h3><div>{result.invalidation}</div></div>
    </div>
  )
}
