"""
TeleSight AI — Agent simplifié (compatible TOUS modèles Ollama)
Approche directe : collecte les données via les outils, puis appelle le LLM une seule fois.
Pas de ReAct, pas d'AgentExecutor → fonctionne avec qwen2.5:0.5b, tinyllama, mistral, etc.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from pipeline import build_llm, get_retriever, retrieve_context

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)
log = logging.getLogger(__name__)

P1_URL = os.getenv("P1_URL", "http://localhost:8000")
P2_URL = os.getenv("P2_URL", "http://localhost:8001")


# ═══════════════════════════════════════════════════════════════════════════════
# OUTILS — fonctions Python pures
# ═══════════════════════════════════════════════════════════════════════════════

def get_current_anomalies(level: str = "") -> str:
    """Récupère les anomalies réseau actives depuis P1."""
    url = f"{P1_URL}/api/kpi/anomalies"
    if level in ("critical", "warning"):
        url += f"?level={level}"
    try:
        resp = httpx.get(url, timeout=8)
        resp.raise_for_status()
        anomalies = resp.json().get("anomalies", [])
        if not anomalies:
            return "Aucune anomalie active actuellement sur le réseau."
        lines = [f"Anomalies actives ({len(anomalies)} cellules) :"]
        for a in anomalies[:15]:
            lines.append(
                f"  • {a.get('cell_id', '?')} [{a.get('alert_level', '?').upper()}] "
                f"SINR={a.get('sinr', '?')} dB | "
                f"Latence={a.get('latency', '?')} ms | "
                f"Débit={a.get('throughput_dl', '?')} Mbps"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Erreur récupération anomalies : {e}"


def get_cell_history(cell_id: str) -> str:
    """Récupère l'historique KPI d'une cellule depuis P1."""
    try:
        resp = httpx.get(f"{P1_URL}/api/kpi/history/{cell_id}?limit=10", timeout=8)
        if resp.status_code == 404:
            return f"Cellule {cell_id} introuvable."
        resp.raise_for_status()
        records = resp.json().get("history", [])
        if not records:
            return f"Aucun historique disponible pour {cell_id}."
        lines = [f"Historique {cell_id} ({len(records)} enregistrements) :"]
        for r in records:
            lines.append(
                f"  [{r.get('timestamp', '?')[:16]}] "
                f"SINR={r.get('sinr', '?')} dB | "
                f"Latence={r.get('latency', '?')} ms | "
                f"Débit={r.get('throughput_dl', '?')} Mbps | "
                f"Statut={r.get('alert_level', '?')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Erreur historique {cell_id} : {e}"


def get_ml_prediction(cell_id: str) -> str:
    """Appelle P2 ML pour scorer une cellule."""
    try:
        resp = httpx.get(f"{P1_URL}/api/kpi/latest", timeout=8)
        resp.raise_for_status()
        cells = resp.json().get("cells", [])
        kpi = next((c for c in cells if c.get("cell_id") == cell_id), None)
        if not kpi:
            return f"Cellule {cell_id} non trouvée dans les KPIs actuels."
    except Exception as e:
        return f"Erreur récupération KPI pour {cell_id} : {e}"
    try:
        resp = httpx.post(f"{P2_URL}/api/ml/predict", json=kpi, timeout=10)
        resp.raise_for_status()
        r = resp.json()
        return (
            f"Prédiction ML pour {cell_id} : "
            f"Score={r.get('anomaly_score', 0):.2f} | "
            f"Niveau={r.get('alert_level', '?').upper()} | "
            f"Proba handover={r.get('handover_probability', 0):.2f} | "
            f"Explication: {r.get('explanation', 'N/A')}"
        )
    except Exception as e:
        return f"Erreur prédiction ML : {e}"


def get_global_stats() -> str:
    """Récupère les statistiques globales du réseau depuis P1."""
    try:
        resp = httpx.get(f"{P1_URL}/api/kpi/stats/global", timeout=8)
        resp.raise_for_status()
        s = resp.json()
        return (
            f"Statistiques réseau global : "
            f"{s.get('total_cells', '?')} cellules supervisées | "
            f"SINR moyen={s.get('avg_sinr', '?')} dB | "
            f"Latence moyenne={s.get('avg_latency', '?')} ms | "
            f"Taux anomalies={s.get('anomaly_rate', '?')}%"
        )
    except Exception as e:
        return f"Erreur stats globales : {e}"


def search_knowledge_base(query: str) -> str:
    """Recherche dans ChromaDB (historique KPI + docs télécom)."""
    try:
        collection = get_retriever()
        context = retrieve_context(collection, query, n_results=3)
        return context if context else "Aucune donnée trouvée dans la base de connaissances."
    except Exception as e:
        return f"Erreur base de connaissances : {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# COLLECTE INTELLIGENTE DES DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_cell_id(question: str) -> Optional[str]:
    """Extrait CELL_XXX depuis la question."""
    match = re.search(r'CELL_\d+', question.upper())
    return match.group(0) if match else None


def collect_context(question: str) -> tuple[str, list]:
    """
    Collecte automatiquement les données pertinentes selon la question.
    Retourne (contexte_textuel, liste_tool_calls).
    """
    q = question.lower()
    context_parts = []
    tool_calls = []
    cell_id = _extract_cell_id(question)

    # 1. Toujours inclure les stats globales
    stats = get_global_stats()
    context_parts.append(f"[Statistiques réseau]\n{stats}")
    tool_calls.append({"tool": "get_global_stats", "input": "", "output": stats[:200]})

    # 2. Anomalies si question liée aux alertes / cellules / réseau
    if any(w in q for w in [
        "anomal", "alerte", "critique", "warning", "dégrad", "problème",
        "cellule", "cell", "réseau", "network", "quelles", "quel"
    ]):
        level = "critical" if "critique" in q else ""
        anomalies = get_current_anomalies(level)
        context_parts.append(f"[Anomalies actives]\n{anomalies}")
        tool_calls.append({"tool": "get_current_anomalies", "input": level, "output": anomalies[:300]})

    # 3. Historique + ML si cellule spécifique mentionnée
    if cell_id:
        history = get_cell_history(cell_id)
        context_parts.append(f"[Historique {cell_id}]\n{history}")
        tool_calls.append({"tool": "get_cell_history", "input": cell_id, "output": history[:300]})

        ml = get_ml_prediction(cell_id)
        context_parts.append(f"[Prédiction ML {cell_id}]\n{ml}")
        tool_calls.append({"tool": "get_ml_prediction", "input": cell_id, "output": ml[:300]})

    # 4. Base de connaissances si question sur standards/KPIs/définitions
    if any(w in q for w in [
        "standard", "3gpp", "sinr", "rsrp", "rsrq", "qos", "kpi",
        "norme", "seuil", "définition", "signifie", "qu'est"
    ]):
        kb = search_knowledge_base(question)
        context_parts.append(f"[Base de connaissances télécom]\n{kb}")
        tool_calls.append({"tool": "search_knowledge_base", "input": question, "output": kb[:300]})

    # 5. Si rien collecté → anomalies par défaut
    if len(context_parts) == 1:
        anomalies = get_current_anomalies()
        context_parts.append(f"[Anomalies actives]\n{anomalies}")
        tool_calls.append({"tool": "get_current_anomalies", "input": "", "output": anomalies[:300]})

    return "\n\n".join(context_parts), tool_calls


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT UNIVERSEL (fonctionne avec tous les modèles)
# ═══════════════════════════════════════════════════════════════════════════════

PROMPT_TEMPLATE = """Tu es TeleSight AI, un expert en supervision de réseaux télécoms (NOC).
Tu travailles avec des données KPI de réseaux 3G/4G/5G en temps réel.

RÈGLES IMPORTANTES :
- Réponds TOUJOURS en français
- Sois précis, technique et structuré
- Base ta réponse UNIQUEMENT sur les données ci-dessous
- Utilise les seuils 3GPP : SINR < 0 dB = mauvais, latence > 100 ms = dégradé, débit < 5 Mbps = insuffisant
- Si des cellules sont en alerte, explique la cause et donne des recommandations concrètes

DONNÉES RÉSEAU ACTUELLES :
{context}

QUESTION : {question}

RÉPONSE EN FRANÇAIS :"""


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class TeleSightAgent:
    def __init__(self):
        llm_result = build_llm()
        self.llm = llm_result[0] if isinstance(llm_result, tuple) else llm_result
        log.info("✓ TeleSight Agent initialisé (mode direct — compatible tous modèles Ollama)")

    def query(self, question: str) -> dict:
        try:
            # Étape 1 : Collecter les données pertinentes
            context, tool_calls = collect_context(question)
            log.info(f"[Agent] Contexte collecté via {len(tool_calls)} outil(s)")

            # Étape 2 : Appeler le LLM avec le contexte
            prompt = PROMPT_TEMPLATE.format(context=context, question=question)
            response = self.llm.invoke([HumanMessage(content=prompt)])
            answer = response.content if hasattr(response, "content") else str(response)

            # Nettoyage de la réponse
            answer = answer.strip()
            if not answer or len(answer) < 10:
                answer = "Je n'ai pas pu générer une réponse. Vérifiez que Ollama est bien démarré et que le modèle répond correctement."

            log.info(f"[Agent] Réponse générée ({len(answer)} caractères)")
            return {
                "answer":     answer,
                "tool_calls": tool_calls,
                "sources":    [],
            }

        except Exception as e:
            log.error(f"[Agent] Erreur : {e}", exc_info=True)
            return {
                "answer":     f"Erreur lors du traitement de votre question : {str(e)}",
                "tool_calls": [],
                "sources":    [],
            }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_agent: TeleSightAgent = None


def get_agent() -> TeleSightAgent:
    global _agent
    if _agent is None:
        _agent = TeleSightAgent()
    return _agent