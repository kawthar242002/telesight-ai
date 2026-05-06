import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { usePolling } from '../hooks/useSSE'

const LEVEL_CONFIG = {
  critical: { bg: '#1a0808', border: '#ef444440', dot: '#ef4444', badge: 'badge-critical', icon: '🔴' },
  warning:  { bg: '#1a1008', border: '#f59e0b40', dot: '#f59e0b', badge: 'badge-warning',  icon: '🟡' },
  normal:   { bg: '#081a0f', border: '#10b98140', dot: '#10b981', badge: 'badge-normal',   icon: '🟢' },
}

function AlertItem({ alert, onSelectCell }) {
  const cfg  = LEVEL_CONFIG[alert.alert_level] || LEVEL_CONFIG.normal
  const time = alert.last_updated
    ? new Date(alert.last_updated).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    : '—'

  return (
    <div
      onClick={() => onSelectCell?.(alert.cell_id)}
      style={{
        background: cfg.bg, border: `1px solid ${cfg.border}`,
        borderRadius: 12, padding: '12px 14px', cursor: 'pointer',
        transition: 'all 0.2s', marginBottom: 8,
        animation: 'slideIn 0.3s ease-out',
      }}
      className="hover:scale-[1.01]"
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="pulse-dot" style={{ background: cfg.dot }} />
          <span style={{ fontWeight: 700, fontSize: 13, color: '#0f172a' }}>
            {alert.cell_id}
          </span>
          <span style={{
            fontSize: 10, color: '#64748b',
            background: '#f1f5f9', padding: '1px 6px', borderRadius: 4
          }}>
            {alert.technology || '5G'}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`badge ${cfg.badge}`}>{alert.alert_level}</span>
          <span style={{ fontSize: 11, color: '#475569' }}>{time}</span>
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <KPITag label="SINR"    value={alert.sinr?.toFixed(1)}    unit="dB"   warn={alert.sinr < 0} />
        <KPITag label="Latence" value={alert.latency?.toFixed(0)}  unit="ms"  warn={alert.latency > 100} />
        <KPITag label="DL"      value={alert.throughput_dl?.toFixed(1)} unit="Mbps" warn={alert.throughput_dl < 10} />
        <KPITag label="PktLoss" value={alert.packet_loss?.toFixed(1)} unit="%" warn={alert.packet_loss > 3} />
      </div>

      {/* Signal score bar */}
      {alert.signal_score !== undefined && (
        <div style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span style={{ fontSize: 10, color: '#475569' }}>Score signal</span>
            <span style={{ fontSize: 10, color: '#64748b' }}>{alert.signal_score?.toFixed(0)}/100</span>
          </div>
          <div style={{ height: 4, background: 'rgba(0,0,0,0.1)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 2,
              width: `${Math.min(100, alert.signal_score || 0)}%`,
              background: alert.signal_score > 60 ? '#10b981' : alert.signal_score > 30 ? '#f59e0b' : '#ef4444',
              transition: 'width 0.5s ease',
            }} />
          </div>
        </div>
      )}
    </div>
  )
}

function KPITag({ label, value, unit, warn }) {
  return (
    <div style={{ fontSize: 11 }}>
      <span style={{ color: '#475569' }}>{label}: </span>
      <span style={{ color: warn ? '#fbbf24' : '#64748b', fontWeight: 600, fontFamily: 'JetBrains Mono' }}>
        {value ?? '—'} <span style={{ color: '#475569' }}>{unit}</span>
      </span>
    </div>
  )
}

/**
 * AlertPanel — polls P1 anomalies every 10s, shows sorted list
 */
export default function AlertPanel({ onSelectCell }) {
  const { data, loading, error } = usePolling(
    () => api.anomalies(),
    10000
  )

  const anomalies = data?.anomalies ?? []
  const critical  = anomalies.filter(a => a.alert_level === 'critical')
  const warning   = anomalies.filter(a => a.alert_level === 'warning')
  const sorted    = [...critical, ...warning]

  return (
    <div className="glass flex flex-col h-full" style={{ padding: '16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <span className="section-title">Alertes Actives</span>
        <div style={{ display: 'flex', gap: 6 }}>
          {critical.length > 0 && (
            <span className="badge badge-critical">{critical.length} critique{critical.length > 1 ? 's' : ''}</span>
          )}
          {warning.length > 0 && (
            <span className="badge badge-warning">{warning.length} alerte{warning.length > 1 ? 's' : ''}</span>
          )}
          {sorted.length === 0 && !loading && (
            <span className="badge badge-normal">Réseau nominal</span>
          )}
        </div>
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
        {loading && sorted.length === 0 ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="shimmer" style={{ height: 80, borderRadius: 12, marginBottom: 8 }} />
          ))
        ) : error ? (
          <div style={{ color: '#ef4444', fontSize: 13, textAlign: 'center', padding: 20 }}>
            ⚠ Connexion P1 indisponible
          </div>
        ) : sorted.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 0', color: '#475569' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
            <p style={{ fontSize: 13 }}>Aucune anomalie détectée</p>
            <p style={{ fontSize: 11, marginTop: 4, color: '#475569' }}>Réseau en état nominal</p>
          </div>
        ) : (
          sorted.map(a => (
            <AlertItem key={a.cell_id} alert={a} onSelectCell={onSelectCell} />
          ))
        )}
      </div>
    </div>
  )
}
