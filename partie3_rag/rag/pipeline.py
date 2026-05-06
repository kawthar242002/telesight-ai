"""
TeleSight AI — RAG Pipeline
Architecture: Mistral API (primary) → Ollama local (fallback)
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

import chromadb
from chromadb.utils import embedding_functions
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)
log = logging.getLogger(__name__)

CHROMA_DIR   = Path(__file__).resolve().parent.parent / "chroma_db"
COLLECTION   = "telesight_knowledge"
EMBED_MODEL  = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
TOP_K        = int(os.getenv("RAG_TOP_K", "5"))

# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es TeleSight AI, un expert NOC (Network Operations Center) spécialisé en réseaux 3G/4G/5G.
Tu analyses les KPIs réseau en temps réel et tu conseilles les ingénieurs télécom.

Règles:
1. Réponds TOUJOURS en français, de manière précise et technique
2. Utilise les seuils 3GPP : SINR < 0 dB = critique, latence > 100 ms = dégradé, RSRP < -110 dBm = faible
3. Si tu as des données de cellules dans le contexte, cite-les précisément
4. Donne toujours des recommandations concrètes
5. Si pas de données disponibles, dis-le clairement et explique les standards généraux

Contexte réseau disponible:
{context}
"""

HUMAN_PROMPT = "{question}"


# ─── LLM Factory with Fallback ───────────────────────────────────────────────
def build_llm():
    """
    Priority:
    1. Mistral API (fast, powerful) — if MISTRAL_API_KEY is set
    2. Ollama local (offline fallback) — if Ollama is running
    """
    mistral_key  = os.getenv("MISTRAL_API_KEY", "").strip()
    ollama_url   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "mistral").strip()
    mistral_model = os.getenv("LLM_MODEL", "mistral-small-latest").strip()

    # ── Try Mistral API first ──
    if mistral_key and mistral_key != "your_mistral_api_key_here":
        try:
            from langchain_mistralai import ChatMistralAI
            llm = ChatMistralAI(
                api_key=mistral_key,
                model=mistral_model,
                temperature=0.3,
                max_retries=2,
            )
            # Quick test
            llm.invoke("ping")
            log.info(f"✓ Using Mistral API — model: {mistral_model}")
            return llm, "mistral"
        except Exception as e:
            log.warning(f"Mistral API failed ({e}), trying Ollama fallback...")

    # ── Fallback: Ollama local ──
    try:
        import httpx
        resp = httpx.get(f"{ollama_url}/api/version", timeout=5)
        resp.raise_for_status()
        from langchain_ollama import ChatOllama
        llm = ChatOllama(base_url=ollama_url, model=ollama_model, temperature=0.3)
        log.info(f"✓ Using Ollama local — model: {ollama_model}")
        return llm, "ollama"
    except Exception as e:
        log.error(f"Ollama also failed: {e}")
        raise RuntimeError(
            "Aucun LLM disponible. "
            "Vérifiez MISTRAL_API_KEY dans .env ou lancez 'ollama serve'."
        )


# ─── ChromaDB ────────────────────────────────────────────────────────────────
def get_retriever():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    return client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"},
    )


def retrieve_context(collection, query: str, n_results: int = TOP_K,
                     filter_meta: dict = None) -> str:
    count = collection.count()
    if count == 0:
        return "Base de connaissances vide — aucune donnée indexée."

    kwargs = {
        "query_texts": [query],
        "n_results": min(n_results, count),
    }
    if filter_meta:
        kwargs["where"] = filter_meta

    try:
        results = collection.query(**kwargs)
        docs    = results.get("documents", [[]])[0]
        metas   = results.get("metadatas", [[]])[0]
    except Exception as e:
        log.warning(f"ChromaDB query failed: {e}")
        return "Erreur lors de la recherche dans la base de connaissances."

    if not docs:
        return "Aucune donnée pertinente trouvée."

    chunks = []
    for i, (doc, meta) in enumerate(zip(docs, metas)):
        source = meta.get("doc_type", "unknown")
        cell   = meta.get("cell_id", "")
        prefix = f"[Source {i+1} — {source}{' — ' + cell if cell else ''}]"
        chunks.append(f"{prefix}\n{doc}")

    return "\n\n".join(chunks)


# ─── RAG Pipeline ────────────────────────────────────────────────────────────
class RAGPipeline:
    def __init__(self):
        self.llm, self.provider = build_llm()
        self.collection = get_retriever()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human",  HUMAN_PROMPT),
        ])
        self.parser = StrOutputParser()
        log.info(f"✓ RAG Pipeline ready (provider={self.provider}, vectors={self.collection.count()})")

    def query(self, question: str, cell_filter: str = None) -> dict:
        filter_meta = {"cell_id": cell_filter} if cell_filter else None
        context     = retrieve_context(self.collection, question, filter_meta=filter_meta)

        try:
            chain  = self.prompt | self.llm | self.parser
            answer = chain.invoke({"context": context, "question": question})
        except Exception as e:
            log.error(f"LLM query failed: {e}")
            answer = f"Erreur LLM: {str(e)[:200]}"

        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=min(TOP_K, max(1, self.collection.count())),
            )
            sources = [
                {"content": doc[:200], **meta}
                for doc, meta in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                )
            ]
        except Exception:
            sources = []

        return {
            "answer":       answer,
            "sources":      sources,
            "context_used": context[:500],
            "provider":     self.provider,
        }

    def generate_report(self, anomalies: list, stats: dict) -> str:
        import datetime
        n_crit   = stats.get("critical_count", 0)
        n_warn   = stats.get("warning_count", 0)
        n_normal = stats.get("normal_count", 0)
        total    = stats.get("total_cells", 0)

        context_parts = [
            f"Rapport généré à {datetime.datetime.now().strftime('%H:%M le %d/%m/%Y')}.",
            f"État réseau: {total} cellules — {n_crit} critiques, {n_warn} en alerte, {n_normal} normales.",
        ]
        for a in anomalies[:10]:
            context_parts.append(
                f"CELLULE {a.get('cell_id','?')} [{a.get('alert_level','?').upper()}]: "
                f"SINR={a.get('sinr','?')} dB, Latence={a.get('latency','?')} ms, "
                f"Débit={a.get('throughput_dl','?')} Mbps"
            )

        context  = "\n".join(context_parts)
        question = (
            "Génère un rapport de supervision réseau complet. "
            "Inclure: synthèse état réseau, cellules dégradées, causes probables, "
            "tendances et recommandations d'actions prioritaires."
        )

        try:
            chain  = self.prompt | self.llm | self.parser
            return chain.invoke({"context": context, "question": question})
        except Exception as e:
            return f"Erreur génération rapport: {e}"


# ─── Singleton ───────────────────────────────────────────────────────────────
_pipeline: RAGPipeline = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline