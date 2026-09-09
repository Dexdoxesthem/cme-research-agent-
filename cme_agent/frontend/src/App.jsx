import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import TopBar from './components/TopBar.jsx'
import ConfigPanel from './components/ConfigPanel.jsx'
import SessionPanel from './components/SessionPanel.jsx'
import CalendarPanel from './components/CalendarPanel.jsx'
import InstrumentBar from './components/InstrumentBar.jsx'
import MarketContextPanel from './components/MarketContextPanel.jsx'
import AnalysisView from './components/AnalysisView.jsx'
import BacktestPanel from './components/BacktestPanel.jsx'
import './App.css'

export default function App() {
  const [config, setConfig] = useState(null)
  const [session, setSession] = useState(null)
  const [calendar, setCalendar] = useState(null)
  const [contracts, setContracts] = useState(null)
  const [universe, setUniverse] = useState(null)
  const [marketCtx, setMarketCtx] = useState(null)
  const [selected, setSelected] = useState('MES')
  const [analysis, setAnalysis] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeAllResult, setAnalyzeAllResult] = useState(null)
  const [error, setError] = useState(null)
  const [backtest, setBacktest] = useState(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = useCallback((msg) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2200)
  }, [])

  const loadBase = useCallback(async () => {
    try {
      const [cfg, sess, cal, ctr, uni] = await Promise.all([
        api.get('/config'), api.get('/session'), api.get('/calendar?hours=72'),
        api.get('/contracts'), api.get('/universe'),
      ])
      setConfig(cfg); setSession(sess); setCalendar(cal); setContracts(ctr); setUniverse(uni)
    } catch (e) { setError(e.message) }
  }, [])

  const loadMarketContext = useCallback(async () => {
    try {
      const c = await api.get('/market-context')
      setMarketCtx(c)
    } catch (e) { setError(e.message) }
  }, [])

  useEffect(() => { loadBase(); loadMarketContext() }, [loadBase, loadMarketContext])

  const runAnalysis = useCallback(async (sym, size = false) => {
    setSelected(sym); setAnalyzing(true); setError(null); setAnalyzeAllResult(null)
    try {
      const r = await api.get(`/analyze/${sym}${size ? '?size=true' : ''}`)
      setAnalysis(r)
    } catch (e) { setError(e.message); setAnalysis(null) }
    finally { setAnalyzing(false) }
  }, [])

  const runAnalyzeAll = useCallback(async (watchlist = false) => {
    setAnalyzing(true); setError(null); setAnalysis(null)
    try {
      const r = await api.get(`/analyze/all${watchlist ? '?include_watchlist=true' : ''}`)
      setAnalyzeAllResult(r)
      const first = Object.keys(r)[0]
      if (first) setSelected(first)
    } catch (e) { setError(e.message) }
    finally { setAnalyzing(false) }
  }, [])

  const runBacktest = useCallback(async (sym, period) => {
    setBacktestLoading(true); setError(null)
    try {
      const r = await api.get(`/backtest/${sym}?period=${period}`)
      setBacktest({ sym, period, data: r })
    } catch (e) { setError(e.message) }
    finally { setBacktestLoading(false) }
  }, [])

  return (
    <div className="app">
      <TopBar
        health={config ? 'ok' : 'pending'}
        onRefresh={() => { loadBase(); loadMarketContext() }}
      />
      {error && <div className="error-banner">{error}</div>}
      <main className="grid">
        <aside className="col">
          <ConfigPanel config={config} setConfig={setConfig} onToast={showToast} />
          <SessionPanel session={session} setSession={setSession} config={config} onToast={showToast} />
          <CalendarPanel calendar={calendar} setCalendar={setCalendar} onToast={showToast} />
        </aside>

        <section className="col wide">
          <MarketContextPanel ctx={marketCtx} onRefresh={loadMarketContext} />

          <InstrumentBar
            universe={universe}
            selected={selected}
            onSelect={(s) => runAnalysis(s, false)}
            onAll={() => runAnalyzeAll(false)}
            onScan={() => runAnalyzeAll(true)}
            busy={analyzing}
          />

          {analyzing && <div className="card"><div className="loading-line">Fetching live data…</div></div>}

          {!analyzing && analyzeAllResult && (
            <AnalysisView
              all={analyzeAllResult}
              contracts={contracts}
              onPick={runAnalysis}
              onBacktest={runBacktest}
            />
          )}

          {!analyzing && !analyzeAllResult && analysis && (
            <AnalysisView
              result={analysis}
              sym={selected}
              contracts={contracts}
              onBacktest={runBacktest}
              onSize={runAnalysis}
            />
          )}

          {!analyzing && !analyzeAllResult && !analysis && (
            <div className="card empty-state">Select an instrument above to run analysis.</div>
          )}

          <BacktestPanel
            contracts={contracts}
            backtest={backtest}
            loading={backtestLoading}
            onRun={runBacktest}
          />
        </section>
      </main>
      <footer className="footer">Research support for a futures trading challenge. Not investment advice — probabilistic output, no guaranteed outcomes. Market data is delayed (yfinance).</footer>
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
