import { useState, useCallback } from 'react'
import { useSSE, usePolling } from './hooks/useSSE'
import { api } from './api'
import KPIChart     from './components/KPIChart'
import CellMap      from './components/CellMap'
import AlertPanel   from './components/AlertPanel'
import AgentChat    from './components/AgentChat'
import ReportButton from './components/ReportButton'

/* ═══════════════════════════════════════════════════════════════════════════
   STAT CARD
═══════════════════════════════════════════════════════════════════════════ */
function StatCard({ label, value, unit, icon, accent, sub }) {
  return (
    <div style={{
      flex: 1, minWidth: 150,
      background: '#ffffff',
      border: '1px solid rgba(0,0,0,0.1)',
      borderRadius: 12, padding: '16px 20px',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* accent bar */}
      <div style={{ position:'absolute', top:0, left:0, right:0, height:2,
        background: accent || 'rgba(59,130,246,.6)', borderRadius:'12px 12px 0 0' }} />
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:10 }}>
        <span style={{ fontSize:10, fontWeight:600, textTransform:'uppercase',
          letterSpacing:'.1em', color:'#475569' }}>{label}</span>
        <span style={{ fontSize:18, opacity:.7 }}>{icon}</span>
      </div>
      <div style={{ display:'flex', alignItems:'baseline', gap:4 }}>
        <span style={{ fontSize:26, fontWeight:800, fontFamily:'JetBrains Mono, monospace',
          color: accent || '#0f172a', lineHeight:1 }}>{value ?? '—'}</span>
        {unit && <span style={{ fontSize:12, color:'#475569' }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize:10, color:'#475569', marginTop:6 }}>{sub}</div>}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   HEADER
═══════════════════════════════════════════════════════════════════════════ */
function Header({ isConnected, stats }) {
  return (
    <header style={{
      height: 56, display:'flex', alignItems:'center', justifyContent:'space-between',
      padding:'0 24px', background:'#f8fafc',
      borderBottom:'1px solid rgba(0,0,0,0.1)',
      position:'sticky', top:0, zIndex:40, flexShrink:0,
    }}>
      {/* Logo */}
      <div style={{ display:'flex', alignItems:'center', gap:12 }}>
        <div style={{
          width:32, height:32, borderRadius:8,
          background:'linear-gradient(135deg,#2563eb,#7c3aed)',
          display:'flex', alignItems:'center', justifyContent:'center',
          fontSize:16, boxShadow:'0 0 16px rgba(37,99,235,0.4)',
        }}>📡</div>
        <div>
          <div style={{ fontSize:15, fontWeight:800, letterSpacing:'-.02em', color:'#0f172a',
            fontFamily:'JetBrains Mono, monospace' }}>TeleSight<span style={{ color:'#3b82f6' }}>AI</span></div>
          <div style={{ fontSize:10, color:'#475569', letterSpacing:'.05em' }}>SUPERVISION RÉSEAU 5G/4G/3G</div>
        </div>
      </div>

      {/* Stats inline */}
      <div style={{ display:'flex', alignItems:'center', gap:24 }}>
        {stats?.total_cells != null && (
          <div style={{ display:'flex', gap:20 }}>
            {[
              { l:'Cellules',  v: stats.total_cells ?? '—', u:'' },
              { l:'SINR moy',  v: stats.avg_sinr    ? `${stats.avg_sinr}` : '—', u:'dB' },
              { l:'Latence',   v: stats.avg_latency ? `${stats.avg_latency}` : '—', u:'ms' },
              { l:'Anomalies', v: `${stats.anomaly_rate_pct ?? 0}`, u:'%',
                color:(stats.anomaly_rate_pct??0)>20?'#f87171':(stats.anomaly_rate_pct??0)>5?'#fbbf24':'#34d399' },
            ].map(s => (
              <div key={s.l} style={{ textAlign:'center' }}>
                <div style={{ fontSize:14, fontWeight:700, color: s.color || '#0f172a',
                  fontFamily:'JetBrains Mono, monospace' }}>{s.v}<span style={{ fontSize:10, color:'#475569', marginLeft:2 }}>{s.u}</span></div>
                <div style={{ fontSize:9, color:'#475569', textTransform:'uppercase', letterSpacing:'.08em' }}>{s.l}</div>
              </div>
            ))}
          </div>
        )}

        {/* Live indicator */}
        <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:11,
          padding:'5px 12px', borderRadius:20,
          background: isConnected ? 'rgba(52,211,153,0.08)' : 'rgba(248,113,113,0.08)',
          border: `1px solid ${isConnected ? 'rgba(52,211,153,0.2)' : 'rgba(248,113,113,0.2)'}`,
        }}>
          <span style={{
            width:6, height:6, borderRadius:'50%',
            background: isConnected ? '#34d399' : '#f87171',
            boxShadow: isConnected ? '0 0 6px #34d399' : '0 0 6px #f87171',
            display:'inline-block',
            animation: isConnected ? 'livePulse 2s ease-in-out infinite' : 'none',
          }} />
          <span style={{ color: isConnected ? '#34d399' : '#f87171', fontWeight:600 }}>
            {isConnected ? 'LIVE' : 'OFF'}
          </span>
        </div>

        <ReportButton />
      </div>
    </header>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   TAB BAR
═══════════════════════════════════════════════════════════════════════════ */
function TabBar({ active, onChange }) {
  const tabs = [
    { id:'charts', icon:'📈', label:'Graphiques Live' },
    { id:'map',    icon:'🗺', label:'Carte Cellules' },
    { id:'chat',   icon:'🤖', label:'Assistant IA' },
  ]
  return (
    <div style={{ display:'flex', gap:2, padding:'0 24px',
      borderBottom:'1px solid #f1f5f9',
      background:'#f8fafc', flexShrink:0 }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)} style={{
          padding:'10px 18px', fontSize:12, fontWeight:600,
          border:'none', cursor:'pointer', transition:'all .2s',
          background:'transparent', letterSpacing:'.04em',
          borderBottom: active === t.id ? '2px solid #3b82f6' : '2px solid transparent',
          color: active === t.id ? '#2563eb' : '#475569',
          marginBottom:-1,
        }}>
          {t.icon} {t.label}
        </button>
      ))}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   CELL DETAIL MODAL
═══════════════════════════════════════════════════════════════════════════ */
function CellDetailModal({ cellId, onClose }) {
  const { data, loading } = usePolling(
    () => Promise.all([api.cellHistory(cellId, 20), api.predictSingle({ cell_id: cellId })]),
    999999, [cellId]
  )
  const history  = data?.[0]?.history ?? []
  const ml       = data?.[1] ?? null

  return (
    <div onClick={e => e.target === e.currentTarget && onClose()} style={{
      position:'fixed', inset:0, background:'rgba(255,255,255,0.8)',
      backdropFilter:'blur(4px)', zIndex:50,
      display:'flex', alignItems:'center', justifyContent:'center', padding:20,
    }}>
      <div style={{
        background:'#ffffff', border:'1px solid rgba(0,0,0,0.1)',
        borderRadius:16, width:'100%', maxWidth:720,
        maxHeight:'80vh', overflowY:'auto', padding:28,
      }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:20 }}>
          <div>
            <div style={{ fontSize:18, fontWeight:700, color:'#0f172a', marginBottom:8 }}>📡 {cellId}</div>
            {ml && (
              <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                <span style={{
                  padding:'2px 10px', borderRadius:20, fontSize:11, fontWeight:600,
                  background: ml.alert_level==='critical'?'rgba(239,68,68,.15)':ml.alert_level==='warning'?'rgba(245,158,11,.15)':'rgba(16,185,129,.15)',
                  color: ml.alert_level==='critical'?'#fca5a5':ml.alert_level==='warning'?'#fcd34d':'#6ee7b7',
                  border:`1px solid ${ml.alert_level==='critical'?'rgba(239,68,68,.3)':ml.alert_level==='warning'?'rgba(245,158,11,.3)':'rgba(16,185,129,.3)'}`,
                }}>{ml.alert_level}</span>
                <span style={{ fontSize:12, color:'#64748b' }}>
                  Score : <strong style={{ fontFamily:'JetBrains Mono', color:'#0f172a' }}>{(ml.anomaly_score*100).toFixed(0)}%</strong>
                </span>
              </div>
            )}
          </div>
          <button onClick={onClose} style={{
            background:'#f1f5f9', border:'1px solid rgba(0,0,0,0.1)',
            borderRadius:8, padding:'6px 12px', color:'#475569', cursor:'pointer', fontSize:13,
          }}>✕</button>
        </div>

        {ml?.explanation && (
          <div style={{
            background:'#ffffff', border:'1px solid rgba(0,0,0,0.1)',
            borderRadius:10, padding:'12px 14px', fontSize:13, color:'#334155', marginBottom:16,
          }}>{ml.explanation}</div>
        )}

        {loading ? (
          <div style={{ height:100, background:'#ffffff', borderRadius:10 }} />
        ) : history.length > 0 ? (
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
            <thead>
              <tr style={{ borderBottom:'1px solid rgba(0,0,0,0.1)' }}>
                {['Heure','SINR','RSRP','Latence','DL Mbps','Statut'].map(h => (
                  <th key={h} style={{ padding:'8px 10px', color:'#475569', textAlign:'left', fontWeight:600, fontSize:10, textTransform:'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.slice(0,10).map((r,i) => (
                <tr key={i} style={{ borderBottom:'1px solid #ffffff' }}>
                  <td style={{ padding:'7px 10px', color:'#475569', fontFamily:'JetBrains Mono', fontSize:11 }}>
                    {r.timestamp ? new Date(r.timestamp).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}) : '—'}
                  </td>
                  <td style={{ padding:'7px 10px', color:r.sinr<0?'#f87171':'#34d399', fontFamily:'JetBrains Mono' }}>{r.sinr?.toFixed(1)}</td>
                  <td style={{ padding:'7px 10px', color:'#475569', fontFamily:'JetBrains Mono' }}>{r.rsrp?.toFixed(0)}</td>
                  <td style={{ padding:'7px 10px', color:r.latency>100?'#fbbf24':'#475569', fontFamily:'JetBrains Mono' }}>{r.latency?.toFixed(0)}</td>
                  <td style={{ padding:'7px 10px', color:r.throughput_dl<10?'#fbbf24':'#475569', fontFamily:'JetBrains Mono' }}>{r.throughput_dl?.toFixed(1)}</td>
                  <td style={{ padding:'7px 10px' }}>
                    <span style={{
                      padding:'1px 8px', borderRadius:20, fontSize:10, fontWeight:600,
                      background:r.alert_level==='critical'?'rgba(239,68,68,.15)':r.alert_level==='warning'?'rgba(245,158,11,.15)':'rgba(16,185,129,.15)',
                      color:r.alert_level==='critical'?'#fca5a5':r.alert_level==='warning'?'#fcd34d':'#6ee7b7',
                    }}>{r.alert_level||'normal'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ color:'#475569', fontSize:13, textAlign:'center', padding:24 }}>
            Aucun historique disponible.
          </div>
        )}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════
   APP
═══════════════════════════════════════════════════════════════════════════ */
export default function App() {
  const { events, latestByCell, isConnected } = useSSE(200)
  const [selectedCell, setSelectedCell] = useState(null)
  const [detailCell,   setDetailCell]   = useState(null)
  const [activeTab,    setActiveTab]    = useState('charts')

  const { data: stats } = usePolling(api.globalStats, 30000)
  const displayStats    = stats || {}

  // Clic sur la carte → ouvre le modal détail
  const handleMapClick = useCallback((cellId) => {
    setSelectedCell(cellId)
    setDetailCell(cellId)
  }, [])

  // Clic sur une alerte → bascule carte + flyTo
  const handleAlertClick = useCallback((cellId) => {
    setSelectedCell(cellId)
    setActiveTab('map')
  }, [])

  const critCnt  = displayStats.critical_count   ?? 0
  const totalCells = displayStats.total_cells    ?? Object.keys(latestByCell).length
  const anomRate = displayStats.anomaly_rate_pct ?? null

  return (
    <div style={{ minHeight:'100vh', display:'flex', flexDirection:'column',
      background:'#f8fafc', color:'#0f172a', fontFamily:'system-ui, sans-serif' }}>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width:5px; }
        ::-webkit-scrollbar-track { background:#f8fafc; }
        ::-webkit-scrollbar-thumb { background:#0f172a; border-radius:3px; }
        @keyframes livePulse {
          0%,100% { box-shadow: 0 0 6px #34d399; }
          50%      { box-shadow: 0 0 12px #34d399, 0 0 20px #34d39944; }
        }
        @keyframes shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>

      <Header isConnected={isConnected} stats={displayStats} />
      <TabBar active={activeTab} onChange={setActiveTab} />

      <main style={{ flex:1, padding:'20px 24px', display:'flex', flexDirection:'column', gap:16, minHeight:0 }}>

        {/* ── KPI Cards ── */}
        <div style={{ display:'flex', gap:12, flexWrap:'wrap' }}>
          <StatCard label="Cellules" value={totalCells} icon="📡"
            accent="#3b82f6" sub={`${critCnt} critique(s) actives`} />
          <StatCard label="SINR Moyen" value={displayStats.avg_sinr ?? '—'} unit="dB" icon="📶"
            accent={displayStats.avg_sinr < 0 ? '#ef4444' : '#10b981'}
            sub="Signal to Noise Ratio" />
          <StatCard label="Latence Moy." value={displayStats.avg_latency ?? '—'} unit="ms" icon="⏱"
            accent={displayStats.avg_latency > 100 ? '#f59e0b' : '#3b82f6'}
            sub="Temps de réponse réseau" />
          <StatCard label="Anomalies" value={anomRate !== null ? anomRate : '—'} unit="%" icon="⚠"
            accent={anomRate > 20 ? '#ef4444' : anomRate > 5 ? '#f59e0b' : '#10b981'}
            sub={events.length > 0 ? `${events.length} events SSE` : 'En attente stream…'} />
        </div>

        {/* ── Content ── */}
        <div style={{ flex:1, minHeight:0, display:'grid', gap:16,
          gridTemplateColumns: activeTab === 'chat' ? '1fr' : '1fr 340px',
        }}>

          {/* LEFT */}
          <div style={{ display:'flex', flexDirection:'column', gap:16, minHeight:0 }}>

            {activeTab === 'charts' && (
              <>
                {selectedCell && (
                  <div style={{ display:'flex', alignItems:'center', gap:8, fontSize:12 }}>
                    <span style={{ color:'#3b82f6' }}>Filtre actif :</span>
                    <span style={{ padding:'2px 12px', borderRadius:20, fontSize:11,
                      background:'rgba(59,130,246,0.1)', border:'1px solid rgba(59,130,246,0.2)',
                      color:'#2563eb' }}>{selectedCell}</span>
                    <button onClick={() => setSelectedCell(null)} style={{
                      background:'none', border:'none', color:'#475569', cursor:'pointer', fontSize:12,
                    }}>✕ Toutes les cellules</button>
                  </div>
                )}
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
                  {['sinr','latency','throughput_dl','packet_loss'].map(m => (
                    <div key={m} style={{ height:210,
                      background:'#ffffff', border:'1px solid #f1f5f9',
                      borderRadius:12, overflow:'hidden' }}>
                      <KPIChart metric={m} events={events} selectedCell={selectedCell} />
                    </div>
                  ))}
                </div>
              </>
            )}

            {activeTab === 'map' && (
              /* ↓ hauteur FIXE en px — Leaflet doit voir une hauteur réelle au moment du mount */
              <div style={{ height:520 }}>
                <CellMap
                  onSelectCell={handleMapClick}
                  selectedCell={selectedCell}
                />
              </div>
            )}

            {activeTab === 'chat' && (
              <div style={{ height:580 }}>
                <AgentChat />
              </div>
            )}
          </div>

          {/* RIGHT — AlertPanel toujours visible sauf chat */}
          {activeTab !== 'chat' && (
            <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
              <div style={{ height: activeTab === 'charts' ? 480 : 520,
                background:'#ffffff',
                border:'1px solid rgba(0,0,0,0.1)', borderRadius:14, overflow:'hidden' }}>
                <AlertPanel onSelectCell={handleAlertClick} />
              </div>
              {activeTab === 'charts' && (
                <div style={{ flex:1, minHeight:160,
                  background:'#ffffff',
                  border:'1px solid rgba(0,0,0,0.1)', borderRadius:14, overflow:'hidden' }}>
                  <AgentChat />
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {detailCell && (
        <CellDetailModal cellId={detailCell} onClose={() => setDetailCell(null)} />
      )}
    </div>
  )
}