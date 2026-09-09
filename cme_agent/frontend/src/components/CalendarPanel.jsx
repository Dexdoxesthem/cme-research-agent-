import { useState } from 'react'
import { api } from '../api.js'

export default function CalendarPanel({ calendar, setCalendar, onToast }) {
  const [form, setForm] = useState({ date: '', name: '', impact: 'high' })
  const [open, setOpen] = useState(false)

  if (!calendar) return <div className="card">loading calendar…</div>

  const add = async () => {
    if (!form.date.trim() || !form.name.trim()) { onToast('date + name required'); return }
    await api.post('/calendar', form)
    setCalendar(await api.get('/calendar?hours=72'))
    setForm({ date: '', name: '', impact: 'high' })
    onToast('Event added')
  }

  return (
    <div className="card">
      <h2>Macro Calendar <span className="muted">(next 72h)</span></h2>
      <div className="log-list">
        {calendar.upcoming.length === 0 && <div className="muted">No scheduled high-impact events in next 72h.</div>}
        {calendar.upcoming.map((e, i) => (
          <div key={i} className="log-item">
            <span className={`imp ${e.impact === 'high' ? 'bad' : e.impact === 'medium' ? 'warn' : 'ok'}`}>{e.date}</span> · {e.name}
          </div>
        ))}
      </div>
      <div className="add-cal">
        <button className="btn ghost small" onClick={() => setOpen(!open)}>{open ? '− collapse' : '+ add event'}</button>
        {open && (
          <div className="kv" style={{ marginTop: 8 }}>
            <label>Date</label>
            <input type="text" placeholder="2026-09-16 14:00" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            <label>Name</label>
            <input type="text" placeholder="CPI release" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <label>Impact</label>
            <select value={form.impact} onChange={(e) => setForm({ ...form, impact: e.target.value })}>
              <option>high</option><option>medium</option><option>low</option>
            </select>
            <button className="btn primary" onClick={add}>Add</button>
          </div>
        )}
      </div>
    </div>
  )
}
