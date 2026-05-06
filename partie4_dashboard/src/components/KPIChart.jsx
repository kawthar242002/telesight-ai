import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

const METRICS = {
  sinr:          { label: 'SINR',        unit: 'dB',   color: '#818cf8', threshold: 0,   thresholdLabel: 'Seuil critique' },
  latency:       { label: 'Latence',     unit: 'ms',   color: '#f59e0b', threshold: 100, thresholdLabel: '100 ms' },
  throughput_dl: { label: 'Débit DL',    unit: 'Mbps', color: '#10b981', threshold: 10,  thresholdLabel: '10 Mbps' },
  packet_loss:   { label: 'Perte pqts',  unit: '%',    color: '#f87171', threshold: 3,   thresholdLabel: '3%' },
}

const CustomTooltip = ({ active, payload, label, unit }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(17,17,24,0.97)', border: '1px solid rgba(0,0,0,0.1)',
      borderRadius: 10, padding: '8px 14px', fontSize: 13
    }}>
      <p style={{ color: '#64748b', marginBottom: 4 }}>{label}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value} {unit}
        </p>
      ))}
    </div>
  )
}

/**
 * KPIChart — live line chart for one metric, updated from SSE events
 * Props:
 *   metric      : 'sinr' | 'latency' | 'throughput_dl' | 'packet_loss'
 *   events      : array of SSE KPI records
 *   selectedCell: optional cell_id filter
 *   maxPoints   : max data points to display
 */
export default function KPIChart({ metric = 'sinr', events = [], selectedCell = null, maxPoints = 60 }) {
  const cfg = METRICS[metric] || METRICS.sinr

  const chartData = useMemo(() => {
    const filtered = selectedCell
      ? events.filter(e => e.cell_id === selectedCell)
      : events

    return filtered
      .slice(0, maxPoints)
      .reverse()
      .map((e, i) => ({
        time:  e.timestamp ? new Date(e.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : `T${i}`,
        value: parseFloat(e[metric]) || 0,
        cell:  e.cell_id,
        alert: e.alert_level,
      }))
  }, [events, metric, selectedCell, maxPoints])

  const current = chartData[chartData.length - 1]?.value
  const isAlert = current !== undefined && (
    (metric === 'sinr'          && current < 0)   ||
    (metric === 'latency'       && current > 100) ||
    (metric === 'throughput_dl' && current < 10)  ||
    (metric === 'packet_loss'   && current > 3)
  )

  return (
    <div className="glass p-4 flex flex-col gap-3 h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="section-title">{cfg.label}</span>
          <div className="flex items-center gap-2 mt-1">
            <span style={{
              fontSize: '1.6rem', fontWeight: 800,
              color: isAlert ? (metric === 'sinr' ? '#f87171' : '#fbbf24') : cfg.color,
              fontFamily: 'JetBrains Mono, monospace'
            }}>
              {current !== undefined ? current.toFixed(1) : '—'}
            </span>
            <span style={{ color: '#475569', fontSize: 13 }}>{cfg.unit}</span>
            {isAlert && (
              <span className="badge badge-warning" style={{ fontSize: 10 }}>⚠ Dégradé</span>
            )}
          </div>
        </div>
        {selectedCell && (
          <span style={{
            fontSize: 11, color: '#818cf8', background: 'rgba(99,102,241,0.1)',
            padding: '3px 10px', borderRadius: 9999, border: '1px solid rgba(99,102,241,0.2)'
          }}>
            {selectedCell}
          </span>
        )}
      </div>

      {/* Chart */}
      <div style={{ flex: 1, minHeight: 120 }}>
        {chartData.length === 0 ? (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="shimmer" style={{ width: '100%', height: 120, borderRadius: 8 }} />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time" tick={{ fill: '#475569', fontSize: 10 }}
                tickLine={false} axisLine={false}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fill: '#475569', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip unit={cfg.unit} />} />
              {cfg.threshold !== undefined && (
                <ReferenceLine
                  y={cfg.threshold} stroke="rgba(239,68,68,0.4)"
                  strokeDasharray="4 4"
                  label={{ value: cfg.thresholdLabel, fill: '#ef4444', fontSize: 10, position: 'right' }}
                />
              )}
              <Line
                type="monotone" dataKey="value" name={cfg.label}
                stroke={cfg.color} strokeWidth={2}
                dot={false} activeDot={{ r: 4, fill: cfg.color }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
