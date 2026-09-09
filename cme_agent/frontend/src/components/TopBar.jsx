export default function TopBar({ health, onRefresh }) {
  return (
    <header className="topbar">
      <div className="brand">CME <span>FUTURES RESEARCH AGENT</span></div>
      <div className="topbar-right">
        <button className="btn ghost" onClick={onRefresh}>Refresh All</button>
        <span className={`pill ${health === 'ok' ? 'ok' : health === 'pending' ? 'warn' : 'bad'}`}>
          {health === 'ok' ? 'data loaded' : health === 'pending' ? 'connecting…' : 'load error'}
        </span>
      </div>
    </header>
  )
}
