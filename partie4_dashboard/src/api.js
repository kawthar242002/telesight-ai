// TeleSight AI — API Configuration
const P1 = 'http://localhost:8000'
const P2 = 'http://localhost:8001'
const P3 = 'http://localhost:8002'

export const api = {
  // ── Part 1 ──────────────────────────────────────────────
  latest:    () => fetch(`${P1}/api/kpi/latest`).then(r => r.json()),
  cells:     () => fetch(`${P1}/api/kpi/cells`).then(r => r.json()),
  anomalies: (level) => fetch(`${P1}/api/kpi/anomalies${level ? `?level=${level}` : ''}`).then(r => r.json()),
  globalStats: () => fetch(`${P1}/api/kpi/stats/global`).then(r => r.json()),
  cellHistory: (id, limit = 60) => fetch(`${P1}/api/kpi/history/${id}?limit=${limit}`).then(r => r.json()),

  // ── Part 2 ──────────────────────────────────────────────
  scoreAllCells: () => fetch(`${P2}/api/ml/score/all-cells`).then(r => r.json()),
  predictSingle: (kpi) => fetch(`${P2}/api/ml/predict`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(kpi)
  }).then(r => r.json()),

  // ── Part 3 ──────────────────────────────────────────────
  agentQuery: (question, useAgent = true) => fetch(`${P3}/api/agent/query`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, use_agent: useAgent })
  }).then(r => r.json()),
  agentReport: () => fetch(`${P3}/api/agent/report`).then(r => r.json()),

  // ── SSE ─────────────────────────────────────────────────
  sseUrl: `${P1}/api/stream/live`,
}

export const P1_URL = P1
export const P2_URL = P2
export const P3_URL = P3
