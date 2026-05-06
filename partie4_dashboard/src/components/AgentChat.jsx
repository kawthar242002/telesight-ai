import { useState, useRef, useEffect } from 'react'
import { api } from '../api'

const SUGGESTIONS = [
  "Quelles cellules sont en alerte critique ?",
  "Pourquoi CELL_007 a une latence élevée ?",
  "Quelle est la tendance du réseau ces dernières heures ?",
  "Explique le SINR et ses seuils 3GPP",
  "Quelles cellules risquent un handover ?",
]

function Message({ msg }) {
  const isUser = msg.role === 'user'
  const time   = new Date(msg.ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 16, animation: 'slideIn 0.25s ease-out'
    }}>
      {/* Author */}
      <div style={{
        fontSize: 10, color: '#475569', marginBottom: 4,
        display: 'flex', gap: 6, alignItems: 'center',
        flexDirection: isUser ? 'row-reverse' : 'row'
      }}>
        <span style={{
          width: 18, height: 18, borderRadius: '50%',
          background: isUser ? 'linear-gradient(135deg,#6366f1,#8b5cf6)' : 'linear-gradient(135deg,#10b981,#059669)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, color: 'white', fontWeight: 700
        }}>
          {isUser ? 'U' : 'AI'}
        </span>
        <span>{isUser ? 'Vous' : 'TeleSight AI'}</span>
        <span style={{ color: '#334155' }}>{time}</span>
      </div>

      {/* Bubble */}
      <div className={isUser ? 'chat-bubble-user' : 'chat-bubble-ai'}>
        {msg.content}
      </div>

      {/* Tool calls (collapsible) */}
      {msg.tool_calls?.length > 0 && (
        <ToolCallDetails calls={msg.tool_calls} />
      )}
    </div>
  )
}

function ToolCallDetails({ calls }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 6, maxWidth: '85%' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)',
          borderRadius: 6, padding: '3px 10px', fontSize: 10, color: '#475569',
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4
        }}
      >
        🔧 {calls.length} outil{calls.length > 1 ? 's' : ''} utilisé{calls.length > 1 ? 's' : ''}
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{
          marginTop: 6, background: 'rgba(0,0,0,0.3)', border: '1px solid #f1f5f9',
          borderRadius: 8, padding: 10, fontSize: 11
        }}>
          {calls.map((tc, i) => (
            <div key={i} style={{ marginBottom: i < calls.length - 1 ? 8 : 0 }}>
              <span style={{ color: '#818cf8', fontWeight: 600 }}>{tc.tool}</span>
              {tc.input && <span style={{ color: '#475569' }}> → {String(tc.input).slice(0, 80)}</span>}
              {tc.output && (
                <div style={{ color: '#64748b', marginTop: 2, paddingLeft: 12, borderLeft: '2px solid #f1f5f9' }}>
                  {String(tc.output).slice(0, 200)}
                  {String(tc.output).length > 200 && '…'}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px',
      background: '#f1f5f9', borderRadius: '14px 14px 14px 4px', width: 'fit-content' }}>
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </div>
  )
}

/**
 * AgentChat — AI chat interface connected to P3 RAG agent
 */
export default function AgentChat() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant', ts: Date.now(), content:
        "Bonjour ! Je suis TeleSight AI, votre assistant de supervision réseau.\n" +
        "Je peux analyser vos KPIs, détecter les causes d'anomalies, et vous conseiller en temps réel.\n" +
        "Posez-moi une question sur votre réseau 5G/4G.",
      tool_calls: []
    }
  ])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const [useAgent, setUseAgent] = useState(true)
  const bottomRef             = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async (text) => {
    const q = (text || input).trim()
    if (!q || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', ts: Date.now(), content: q, tool_calls: [] }])
    setLoading(true)

    try {
      const res = await api.agentQuery(q, useAgent)
      setMessages(prev => [...prev, {
        role: 'assistant', ts: Date.now(),
        content: res.answer || 'Aucune réponse.',
        tool_calls: res.tool_calls || [],
      }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant', ts: Date.now(),
        content: `❌ Erreur de connexion à l'agent (P3). Vérifiez que le service RAG est démarré sur le port 8002.\n\nDétail: ${e.message}`,
        tool_calls: [],
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  return (
    <div className="glass flex flex-col h-full" style={{ padding: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="section-title">Assistant IA</span>
          <span style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 9999,
            background: 'rgba(16,185,129,0.15)', color: '#6ee7b7',
            border: '1px solid rgba(16,185,129,0.3)'
          }}>
            🤖 Mistral RAG
          </span>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#475569', cursor: 'pointer' }}>
          <input
            type="checkbox" checked={useAgent} onChange={e => setUseAgent(e.target.checked)}
            style={{ accentColor: '#6366f1' }}
          />
          Mode agent
        </label>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', paddingRight: 4 }}>
        {messages.map((m, i) => <Message key={i} msg={m} />)}
        {loading && (
          <div style={{ alignSelf: 'flex-start', marginBottom: 8 }}>
            <TypingIndicator />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onClick={() => sendMessage(s)}
              style={{
                background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
                borderRadius: 20, padding: '4px 10px', fontSize: 11, color: '#a5b4fc',
                cursor: 'pointer', transition: 'all 0.15s'
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div style={{ display: 'flex', gap: 8 }}>
        <textarea
          className="input-dark"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Posez une question sur le réseau... (Entrée pour envoyer)"
          rows={2}
          disabled={loading}
          style={{ resize: 'none', flex: 1 }}
          id="agent-chat-input"
        />
        <button
          className="btn-glow"
          onClick={() => sendMessage()}
          disabled={!input.trim() || loading}
          style={{ alignSelf: 'flex-end', padding: '10px 16px', minWidth: 70 }}
          id="agent-chat-send"
        >
          {loading ? '…' : '↑'}
        </button>
      </div>
    </div>
  )
}
