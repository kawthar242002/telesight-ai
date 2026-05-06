import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import { usePolling } from '../hooks/useSSE'

/* ── Leaflet loader ─────────────────────────────────────────────────────── */
function loadLeaflet() {
  return new Promise((resolve) => {
    if (window.L) return resolve(window.L)
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(link)
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.onload = () => resolve(window.L)
    document.head.appendChild(script)
  })
}

/* ── Coordonnées fixes Tunisie (API ne retourne pas lat/lng) ─────────────── */
const COORDS = {
  CELL_001:[36.819,10.166], CELL_002:[36.806,10.182], CELL_003:[36.799,10.134],
  CELL_004:[36.835,10.216], CELL_005:[36.860,10.195], CELL_006:[36.812,10.234],
  CELL_007:[37.274, 9.874], CELL_008:[37.073,10.042], CELL_009:[36.945,10.667],
  CELL_010:[37.109,10.453], CELL_011:[37.329,10.210], CELL_012:[35.678,10.097],
  CELL_013:[35.501,10.742], CELL_014:[35.829,10.639], CELL_015:[36.182, 9.558],
  CELL_016:[36.409, 9.871], CELL_017:[35.937, 9.063], CELL_018:[34.741,10.760],
  CELL_019:[34.886,10.589], CELL_020:[35.172,10.931], CELL_021:[35.300,10.082],
  CELL_022:[33.882,10.098], CELL_023:[33.504,10.527], CELL_024:[32.857,10.707],
  CELL_025:[31.629, 9.462], CELL_026:[33.340, 8.829], CELL_027:[30.467, 9.833],
  CELL_028:[35.167, 8.831], CELL_029:[35.959, 8.374], CELL_030:[36.399, 8.695],
}

function getLL(id) {
  if (COORDS[id]) return COORDS[id]
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0
  return [30.5 + (Math.abs(h % 1000) / 1000) * 7, 7.5 + (Math.abs((h >> 8) % 1000) / 1000) * 4.5]
}

/* ── Couleurs ────────────────────────────────────────────────────────────── */
const CLR = {
  critical:{ fill:'#ef4444', stroke:'#dc2626', label:'⚠ CRITIQUE' },
  warning: { fill:'#f59e0b', stroke:'#d97706', label:'! ALERTE'   },
  normal:  { fill:'#10b981', stroke:'#059669', label:'✓ NORMAL'   },
}

/* ── Popup HTML ──────────────────────────────────────────────────────────── */
function popup(cell) {
  const c   = CLR[cell.alert_level] || CLR.normal
  const pct = Math.round((cell.anomaly_score ?? 0) * 100)
  return `
    <div style="font-family:monospace;background:#0f172a;border:1px solid ${c.stroke};
      border-radius:10px;padding:14px;min-width:200px;color:#0f172a;
      box-shadow:0 0 24px ${c.fill}55;">
      <div style="font-weight:700;font-size:13px;color:${c.fill};margin-bottom:6px;">
        📡 ${cell.cell_id}
      </div>
      <div style="font-size:10px;color:${c.fill};background:${c.fill}22;
        padding:2px 8px;border-radius:4px;display:inline-block;margin-bottom:10px;
        font-weight:600;letter-spacing:.05em;">
        ${c.label}
      </div>
      <div style="font-size:11px;display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:10px;">
        <span style="color:#475569">Score</span>
        <span style="color:${c.fill};font-weight:700;text-align:right">${pct}/100</span>
      </div>
      <div style="height:4px;background:#ffffff11;border-radius:2px;overflow:hidden;">
        <div style="height:100%;width:${pct}%;background:${c.fill};border-radius:2px;"></div>
      </div>
      <div style="margin-top:9px;font-size:9px;color:#475569;line-height:1.5">
        ${cell.explanation ?? ''}
      </div>
    </div>`
}

/* ── Composant principal ─────────────────────────────────────────────────── */
export default function CellMap({ onSelectCell, selectedCell }) {
  const divRef     = useRef(null)   // <div> Leaflet cible
  const mapRef     = useRef(null)   // L.map instance
  const LRef       = useRef(null)   // Leaflet lib
  const mrkRef     = useRef({})     // markers
  const initRef    = useRef(false)  // init guard
  const [ready,    setReady]    = useState(false)
  const [localSel, setLocalSel] = useState(null)

  const { data, loading, error, refresh } = usePolling(() => api.scoreAllCells(), 30000)
  const cells = data?.cells ?? []

  /* ── Init Leaflet (une fois) ─────────────────────────────────────────── */
  useEffect(() => {
    if (initRef.current) return
    initRef.current = true

    loadLeaflet().then((L) => {
      if (mapRef.current) return
      LRef.current = L

      const map = L.map(divRef.current, {
        center: [33.9, 9.5], zoom: 6,
        zoomControl: true, attributionControl: false,
      })

      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
      }).addTo(map)

      mapRef.current = map

      // CRITIQUE : forcer le recalcul de la taille après paint
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          map.invalidateSize()
          setReady(true)
        })
      })
    })

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        LRef.current   = null
        mrkRef.current = {}
        initRef.current = false
        setReady(false)
      }
    }
  }, [])

  /* ── Markers ─────────────────────────────────────────────────────────── */
  useEffect(() => {
    if (!ready || !mapRef.current || !LRef.current || cells.length === 0) return
    const L = LRef.current, map = mapRef.current

    Object.values(mrkRef.current).forEach(m => { try { m.remove() } catch(_){} })
    mrkRef.current = {}

    const bounds = []

    cells.forEach(cell => {
      const [lat, lng] = getLL(cell.cell_id)
      const lvl = cell.alert_level || 'normal'
      const c   = CLR[lvl] || CLR.normal
      const sc  = cell.anomaly_score ?? 0.3
      const r   = 8 + sc * 12

      bounds.push([lat, lng])

      if (lvl !== 'normal') {
        mrkRef.current[`_p_${cell.cell_id}`] = L.circleMarker([lat, lng], {
          radius: r + 9, fillColor:'transparent',
          color: c.fill, weight: 1.5, opacity: 0.5, fillOpacity: 0,
          className:'ts-pulse',
        }).addTo(map)
      }

      const mk = L.circleMarker([lat, lng], {
        radius: r, fillColor: c.fill, color: c.stroke,
        weight: 2, opacity: 1,
        fillOpacity: lvl === 'critical' ? .95 : lvl === 'warning' ? .85 : .65,
      })
      mk.bindPopup(popup(cell), { className:'ts-popup', maxWidth:240 })
      mk.bindTooltip(cell.cell_id, { direction:'top', className:'ts-tip' })
      mk.on('click', () => { setLocalSel(cell.cell_id); onSelectCell?.(cell.cell_id, cell) })
      mk.addTo(map)
      mrkRef.current[cell.cell_id] = mk
    })

    if (!selectedCell && bounds.length > 0)
      map.fitBounds(L.latLngBounds(bounds), { padding:[50,50], maxZoom:9 })

  }, [ready, cells]) // eslint-disable-line

  /* ── Navigation depuis alertes ───────────────────────────────────────── */
  useEffect(() => {
    if (!selectedCell || !ready || !mapRef.current) return
    setLocalSel(selectedCell)
    const mk = mrkRef.current[selectedCell]
    if (!mk) return
    mapRef.current.flyTo(mk.getLatLng(), 11, { animate:true, duration:1.0 })
    setTimeout(() => {
      try {
        mk.openPopup()
        const orig = { radius: mk.options.radius, weight: mk.options.weight }
        mk.setStyle({ radius: orig.radius + 7, weight: 4 })
        setTimeout(() => mk.setStyle(orig), 1500)
      } catch(_){}
    }, 950)
  }, [selectedCell, ready])

  const sum = {
    critical: cells.filter(c => c.alert_level === 'critical').length,
    warning:  cells.filter(c => c.alert_level === 'warning').length,
    normal:   cells.filter(c => !c.alert_level || c.alert_level === 'normal').length,
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%',
      borderRadius:14, overflow:'hidden', background:'#f8fafc',
      border:'1px solid rgba(0,0,0,0.1)' }}>

      <style>{`
        .ts-pulse { animation: ts-pulse 2s ease-in-out infinite; }
        @keyframes ts-pulse { 0%,100%{opacity:.5} 50%{opacity:.04} }
        .ts-popup .leaflet-popup-content-wrapper {
          background:transparent!important; box-shadow:none!important; padding:0!important;
        }
        .ts-popup .leaflet-popup-content { margin:0!important; }
        .ts-popup .leaflet-popup-tip-container { display:none!important; }
        .ts-tip {
          background:#ffffff!important; border:1px solid #334155!important;
          color:#64748b!important; font-size:10px!important; padding:2px 8px!important;
          border-radius:4px!important;
        }
        .ts-tip::before { display:none!important; }
        .leaflet-control-zoom {
          border:1px solid rgba(0,0,0,0.1)!important;
          border-radius:8px!important; overflow:hidden;
        }
        .leaflet-control-zoom a {
          background:#ffffff!important; color:#475569!important;
          border-color:#f1f5f9!important; width:28px!important; height:28px!important;
          line-height:28px!important;
        }
        .leaflet-control-zoom a:hover { color:#0f172a!important; background:#0f172a!important; }
      `}</style>

      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'0 16px', height:46, background:'#ffffff',
        borderBottom:'1px solid #f1f5f9', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:3, height:16, background:'#3b82f6', borderRadius:2 }} />
          <span style={{ fontSize:11, fontWeight:700, textTransform:'uppercase',
            letterSpacing:'.1em', color:'#334155' }}>Carte des Cellules</span>
        </div>
        <div style={{ display:'flex', gap:12, alignItems:'center' }}>
          <Dot color="#ef4444" n={sum.critical} label="crit" />
          <Dot color="#f59e0b" n={sum.warning}  label="warn" />
          <Dot color="#10b981" n={sum.normal}   label="ok"   />
          <button onClick={refresh} style={{
            background:'#f1f5f9', border:'1px solid rgba(0,0,0,0.1)',
            borderRadius:6, padding:'4px 12px', color:'#475569',
            fontSize:11, cursor:'pointer', transition:'color .15s',
          }}
            onMouseEnter={e=>e.target.style.color='#0f172a'}
            onMouseLeave={e=>e.target.style.color='#475569'}
          >↻ Refresh</button>
        </div>
      </div>

      {/* Map — flex:1 pour prendre tout l'espace restant */}
      <div style={{ flex:1, position:'relative', minHeight:0 }}>
        {/* ↓ hauteur 100% fonctionne car le parent a une hauteur réelle (flex:1 dans un flex column avec hauteur connue) */}
        <div ref={divRef} style={{ width:'100%', height:'100%' }} />

        {loading && cells.length === 0 && (
          <Overlay>
            <Spinner />
            <span style={{ color:'#475569', fontSize:12, marginTop:10 }}>Chargement des cellules…</span>
          </Overlay>
        )}
        {error && (
          <Overlay>
            <span style={{ fontSize:30 }}>⚠</span>
            <span style={{ color:'#ef4444', fontSize:13, fontWeight:600 }}>ML API indisponible</span>
            <span style={{ color:'#475569', fontSize:11 }}>Port 8001</span>
            <button onClick={refresh} style={{
              marginTop:8, background:'rgba(239,68,68,.1)',
              border:'1px solid rgba(239,68,68,.3)', borderRadius:6,
              padding:'5px 16px', color:'#ef4444', fontSize:11, cursor:'pointer',
            }}>Réessayer</button>
          </Overlay>
        )}
      </div>

      {/* Footer */}
      <div style={{ height:34, flexShrink:0, borderTop:'1px solid #f1f5f9',
        background: localSel ? 'rgba(59,130,246,0.06)' : 'transparent',
        display:'flex', alignItems:'center', padding:'0 16px', gap:8,
        fontSize:11, color: localSel ? '#2563eb' : '#334155' }}>
        {localSel ? (
          <>
            <span>📡</span>
            <span>Cellule sélectionnée :</span>
            <strong style={{ color:'#1d4ed8' }}>{localSel}</strong>
            <button onClick={() => {
              setLocalSel(null)
              if (mapRef.current && LRef.current && cells.length > 0)
                mapRef.current.flyToBounds(
                  LRef.current.latLngBounds(cells.map(c => getLL(c.cell_id))),
                  { padding:[50,50], maxZoom:9, duration:.8 }
                )
            }} style={{ marginLeft:'auto', background:'transparent',
              border:'1px solid rgba(147,197,253,.2)', borderRadius:4,
              padding:'1px 8px', color:'#475569', fontSize:10, cursor:'pointer' }}>
              ✕ Tout afficher
            </button>
          </>
        ) : (
          <span>Cliquez sur une cellule ou une alerte pour la localiser</span>
        )}
      </div>
    </div>
  )
}

function Dot({ color, n, label }) {
  return (
    <span style={{ display:'flex', alignItems:'center', gap:4, fontSize:11, color:'#475569' }}>
      <span style={{ width:7, height:7, borderRadius:'50%', background:color,
        boxShadow:`0 0 6px ${color}88`, display:'inline-block' }} />
      <span style={{ color:'#64748b' }}>{n}</span> {label}
    </span>
  )
}

function Overlay({ children }) {
  return (
    <div style={{ position:'absolute', inset:0, background:'rgba(248,250,252,0.85)',
      display:'flex', flexDirection:'column', alignItems:'center',
      justifyContent:'center', zIndex:999, gap:6 }}>
      {children}
    </div>
  )
}

function Spinner() {
  return (
    <>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      <div style={{ width:28, height:28, border:'2px solid rgba(59,130,246,0.15)',
        borderTop:'2px solid #3b82f6', borderRadius:'50%',
        animation:'spin 1s linear infinite' }} />
    </>
  )
}