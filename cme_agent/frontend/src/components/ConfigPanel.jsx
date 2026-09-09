import { useEffect, useState } from 'react'
import { api, fmtUsd } from '../api.js'

export default function ConfigPanel({ config, setConfig, onToast }) {
  const [form, setForm] = useState({})
  useEffect(() => {
    if (config) setForm({
      account_size: config.account_size,
      risk_percent: config.risk_percent * 100,
      daily_loss_limit: config.daily_loss_limit,
      suggested_size_ratio: config.suggested_size_ratio,
    })
  }, [config])

  if (!config) return <div className="card">loading config…</div>

  const budget = config.account_size * config.risk_percent

  const save = async () => {
    try {
      const c = await api.post('/config', {
        account_size: Number(form.account_size),
        risk_percent: Number(form.risk_percent) / 100,
        daily_loss_limit: Number(form.daily_loss_limit),
        suggested_size_ratio: Number(form.suggested_size_ratio),
      })
      setConfig(c); onToast('Config saved')
    } catch (e) { onToast(e.message) }
  }

  return (
    <div className="card">
      <h2>Account / Risk Rules</h2>
      <div className="kv">
        <label>Account size ($)</label>
        <input type="number" value={form.account_size ?? ''} onChange={(e) => setForm({ ...form, account_size: e.target.value })} />
        <label>Risk per trade (%)</label>
        <input type="number" step="0.5" min="0.5" max="10" value={form.risk_percent ?? ''} onChange={(e) => setForm({ ...form, risk_percent: e.target.value })} />
        <label>Daily loss limit ($)</label>
        <input type="number" step="50" value={form.daily_loss_limit ?? ''} onChange={(e) => setForm({ ...form, daily_loss_limit: e.target.value })} />
        <label>Suggested size (% of max)</label>
        <input type="number" step="5" min="10" max="100" value={form.suggested_size_ratio ?? ''} onChange={(e) => setForm({ ...form, suggested_size_ratio: e.target.value })} />
      </div>
      <div className="row-between">
        <span>2% budget: <strong>{fmtUsd(budget)}</strong></span>
        <button className="btn primary" onClick={save}>Save Config</button>
      </div>
    </div>
  )
}
