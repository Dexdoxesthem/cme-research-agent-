import { useMemo } from 'react'
import { ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Legend } from 'recharts'

const MA_COLORS = { ma20: '#58a6ff', ma50: '#d29922', ma200: '#bc8cff' }
const AXIS = { stroke: '#8b949e', fontSize: 11, tickLine: false }

export default function PriceChart({ data }) {
  const [chartData, indicators] = useMemo(() => {
    const cd = data.map((b) => ({ ...b, date: b.date.slice(5) }))
    const rsi = cd.filter((b) => b.rsi14 !== null)
    return [cd, rsi]
  }, [data])

  if (!data?.length) return null

  return (
    <div className="chart-block">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 6, right: 12, left: 6, bottom: 0 }}>
          <CartesianGrid stroke="#21262d" strokeDasharray="3 3" />
          <XAxis dataKey="date" {...AXIS} minTickGap={40} />
          <YAxis domain={['auto', 'auto']} {...AXIS} width={64} />
          <Tooltip
            contentStyle={{ background: '#1c2330', border: '1px solid #2d333b', borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: '#8b949e' }}
            formatter={(v, name) => [v, name]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line dataKey="close" stroke="#3fb950" dot={false} strokeWidth={1.8} name="Close" />
          <Line dataKey="ma20" stroke={MA_COLORS.ma20} dot={false} strokeWidth={1.2} name="SMA20" />
          <Line dataKey="ma50" stroke={MA_COLORS.ma50} dot={false} strokeWidth={1.2} name="SMA50" />
          <Line dataKey="ma200" stroke={MA_COLORS.ma200} dot={false} strokeWidth={1.2} name="SMA200" />
          <ReferenceLine y={data[data.length - 1].close} stroke="#8b949e" strokeDasharray="4 4" />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="chart-title">Daily — close + SMA20/50/200 (yfinance, delayed)</div>
      {indicators.length > 20 && (
        <ResponsiveContainer width="100%" height={90}>
          <ComposedChart data={indicators} margin={{ top: 6, right: 12, left: 6, bottom: 0 }}>
            <CartesianGrid stroke="#21262d" strokeDasharray="3 3" />
            <XAxis dataKey="date" {...AXIS} minTickGap={60} />
            <YAxis domain={[0, 100]} {...AXIS} width={32} />
            <Tooltip
              contentStyle={{ background: '#1c2330', border: '1px solid #2d333b', borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: '#8b949e' }}
            />
            <ReferenceLine y={50} stroke="#8b949e" strokeDasharray="3 3" />
            <Line dataKey="rsi14" stroke="#58a6ff" dot={false} strokeWidth={1.2} name="RSI(14)" />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
