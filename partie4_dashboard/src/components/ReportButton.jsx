import { useState } from 'react'
import { api } from '../api'
import jsPDF from 'jspdf'

/**
 * ReportButton — generates AI supervision report and offers PDF download
 */
export default function ReportButton() {
  const [loading,  setLoading]  = useState(false)
  const [report,   setReport]   = useState(null)
  const [error,    setError]    = useState(null)
  const [showModal, setModal]   = useState(false)

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.agentReport()
      setReport(data)
      setModal(true)
    } catch (e) {
      setError(`Erreur: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const downloadPDF = () => {
    if (!report) return
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })
    const margin  = 50
    const pageW   = doc.internal.pageSize.getWidth()
    const maxW    = pageW - margin * 2
    let y = margin

    // Header
    doc.setFillColor(17, 17, 24)
    doc.rect(0, 0, pageW, 80, 'F')
    doc.setFontSize(20)
    doc.setTextColor(165, 180, 252)
    doc.text('TeleSight AI — Rapport de Supervision', margin, 40)
    doc.setFontSize(10)
    doc.setTextColor(100, 116, 139)
    const ts = report.timestamp ? new Date(report.timestamp).toLocaleString('fr-FR') : new Date().toLocaleString('fr-FR')
    doc.text(`Généré le ${ts}`, margin, 58)
    y = 100

    // Stats summary
    if (report.stats) {
      doc.setFontSize(11)
      doc.setTextColor(50, 50, 50)
      const s = report.stats
      doc.text(
        `Cellules: ${s.total_cells ?? '?'} | Critiques: ${s.critical_count ?? 0} | ` +
        `SINR moyen: ${s.avg_sinr ?? '?'} dB | Latence moy: ${s.avg_latency ?? '?'} ms`,
        margin, y
      )
      y += 24
    }

    // Divider
    doc.setDrawColor(200, 200, 200)
    doc.setLineWidth(1)
    doc.line(margin, y, pageW - margin, y)
    y += 20

    // Body
    doc.setFontSize(10)
    doc.setTextColor(0, 0, 0)
    
    let bodyText = report.report || 'Rapport vide.'
    // Clean up text to prevent overflowing:
    // 1. Replace non-breaking spaces with normal spaces
    bodyText = bodyText.replace(/\u00A0/g, ' ')
    // 2. Replace tabs with spaces
    bodyText = bodyText.replace(/\t/g, '  ')
    // 3. Shorten long markdown table dashes which prevent wrapping
    bodyText = bodyText.replace(/-{4,}/g, '---')
    
    const lines = doc.splitTextToSize(bodyText, maxW)
    lines.forEach(line => {
      if (y > 780) { doc.addPage(); y = margin }
      doc.text(line, margin, y)
      y += 14
    })

    // Footer
    doc.setFontSize(9)
    doc.setTextColor(71, 85, 105)
    doc.text('TeleSight AI — Plateforme de supervision réseau télécom 5G/4G/3G', margin, 820)

    doc.save(`telesight_rapport_${new Date().toISOString().slice(0,10)}.pdf`)
  }

  return (
    <>
      <button
        className="btn-glow"
        onClick={generate}
        disabled={loading}
        id="report-generate-btn"
        style={{ display: 'flex', alignItems: 'center', gap: 8 }}
      >
        {loading ? (
          <>
            <span style={{ display: 'inline-block', width: 14, height: 14, borderRadius: '50%',
              border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white',
              animation: 'spin 0.8s linear infinite' }} />
            Génération...
          </>
        ) : (
          <>📄 Rapport IA</>
        )}
      </button>

      {error && (
        <div style={{ color: '#fca5a5', fontSize: 12, marginTop: 4 }}>{error}</div>
      )}

      {/* Modal */}
      {showModal && report && (
        <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) setModal(false) }}>
          <div className="modal-box">
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a' }}>
                  📊 Rapport de Supervision
                </h2>
                <p style={{ fontSize: 12, color: '#475569', marginTop: 4 }}>
                  {report.timestamp ? new Date(report.timestamp).toLocaleString('fr-FR') : ''}
                  {report.anomaly_count !== undefined && ` · ${report.anomaly_count} anomalies`}
                </p>
              </div>
              <button
                onClick={() => setModal(false)}
                style={{ background: '#f1f5f9', border: '1px solid rgba(0,0,0,0.1)',
                  borderRadius: 8, padding: '6px 12px', color: '#64748b', cursor: 'pointer', fontSize: 13 }}
              >
                ✕
              </button>
            </div>

            {/* Stats cards */}
            {report.stats && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 20 }}>
                <StatMini label="Cellules" value={report.stats.total_cells ?? '—'} />
                <StatMini label="Critiques" value={report.stats.critical_count ?? 0} color="#ef4444" />
                <StatMini label="SINR moy" value={`${report.stats.avg_sinr ?? '?'} dB`} />
                <StatMini label="Latence" value={`${report.stats.avg_latency ?? '?'} ms`} />
              </div>
            )}

            {/* Report text */}
            <div style={{
              background: '#ffffff', border: '1px solid #f1f5f9',
              borderRadius: 10, padding: 16, fontSize: 13, lineHeight: 1.7, color: '#334155',
              maxHeight: 320, overflowY: 'auto', whiteSpace: 'pre-wrap', marginBottom: 20
            }}>
              {report.report}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setModal(false)}
                style={{ background: '#f1f5f9', border: '1px solid rgba(0,0,0,0.1)',
                  borderRadius: 8, padding: '8px 16px', color: '#64748b', cursor: 'pointer', fontSize: 13 }}
              >
                Fermer
              </button>
              <button
                className="btn-glow"
                onClick={downloadPDF}
                id="report-download-btn"
              >
                ⬇ Télécharger PDF
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  )
}

function StatMini({ label, value, color }) {
  return (
    <div style={{
      background: '#ffffff', borderRadius: 8, padding: '8px 10px', textAlign: 'center'
    }}>
      <div style={{ fontSize: 16, fontWeight: 700, color: color || '#0f172a', fontFamily: 'JetBrains Mono' }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>{label}</div>
    </div>
  )
}
