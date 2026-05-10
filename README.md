# 🛰️ TeleSight AI
### Intelligent Telecom Network Supervision Platform

<div align="center">

![TeleSight AI](https://img.shields.io/badge/TeleSight-AI-6366f1?style=for-the-badge&logo=satellite&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=for-the-badge&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Kafka](https://img.shields.io/badge/Apache_Kafka-7.5-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**Real-time 5G/4G/3G network supervision powered by Big Data, Machine Learning & Generative AI**

[Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Tech Stack](#-tech-stack) • [Team](#-team)

</div>

---

## 📡 Overview

**TeleSight AI** is a production-grade intelligent network supervision platform for telecom operators. It ingests real-time KPI data from cellular base stations, detects anomalies using ensemble Machine Learning models, predicts network degradation before it impacts users, and provides a conversational AI agent for NOC engineers — all displayed on a live interactive dashboard.

> Built as part of a 5G/Industry 5.0 academic project, using real Kaggle telecom datasets and production-grade technologies.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📊 **Live KPI Dashboard** | Real-time SINR, latency, throughput, packet loss monitoring via Server-Sent Events |
| 🤖 **Anomaly Detection** | Ensemble ML: Isolation Forest + XGBoost + LSTM with Attention |
| 🔮 **Predictive Analytics** | LSTM predicts network degradation 15 min in advance |
| 🧠 **AI Agent (RAG)** | LangChain agent answers natural language questions about the network |
| 🗺️ **Cell Heatmap** | Geographic visualization of cell towers colored by alert level |
| 📝 **Auto Reports** | LLM-generated supervision reports with root cause analysis |
| ⚡ **Streaming Pipeline** | Apache Kafka ingests 10 KPI records/second per cell |
| 🔄 **LLM Fallback** | Mistral API (primary) → Ollama local (offline fallback) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TeleSight AI                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  CSV Datasets (Kaggle)                                           │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────┐    ┌───────────┐    ┌──────────────────────┐   │
│  │Kafka Producer│───►│  Kafka   │───►│  Kafka Consumer      │   │
│  │ (10 msg/sec) │    │  Broker  │    │  + Feature Eng.      │   │
│  └─────────────┘    └───────────┘    └──────┬───────────────┘   │
│                                             │                    │
│                              ┌──────────────┼──────────────┐    │
│                              ▼              ▼              ▼    │
│                         ┌─────────┐  ┌──────────┐  ┌───────┐   │
│                         │PostgreSQL│  │  Redis   │  │ Logs  │   │
│                         │(history) │  │ (cache)  │  │       │   │
│                         └────┬────┘  └────┬─────┘  └───────┘   │
│                              │             │                     │
│                    ┌─────────▼─────────────▼──────────┐        │
│                    │      FastAPI — Pipeline API        │        │
│                    │           Port 8000                │        │
│                    │  /api/kpi/* | /api/stream/live     │        │
│                    └─────────────┬────────────────────-┘        │
│                                  │                               │
│              ┌───────────────────┼───────────────────┐          │
│              ▼                   ▼                   ▼          │
│   ┌──────────────────┐  ┌───────────────┐  ┌──────────────┐    │
│   │  ML API :8001    │  │  RAG API :8002│  │  Dashboard   │    │
│   │                  │  │               │  │   :3000      │    │
│   │ • Isolation Forest│  │ • LangChain  │  │              │    │
│   │ • XGBoost        │  │ • ChromaDB   │  │ • Live Charts│    │
│   │ • LSTM+Attention │  │ • Mistral AI │  │ • Cell Map   │    │
│   │                  │  │ • Ollama     │  │ • AI Chat    │    │
│   └──────────────────┘  └───────────────┘  └──────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- 8 GB RAM minimum
- 10 GB free disk space

### One-command launch

```bash
# Clone the repository
git clone https://github.com/your-username/telesight-ai.git
cd telesight-ai

# Configure environment
cp partie3_rag/.env.example partie3_rag/.env
# Edit .env and add your MISTRAL_API_KEY

# Launch everything
docker-compose up --build
```

Open **http://localhost:3000** 🎉

### Stop
```bash
docker-compose down
```

---

## ⚙️ Configuration

Edit `partie3_rag/.env`:

```env
# LLM Provider — Mistral API (recommended)
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your_key_here        # Get free at console.mistral.ai
LLM_MODEL=mistral-small-latest

# Fallback — Ollama local (offline mode)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Services
P1_URL=http://localhost:8000
P2_URL=http://localhost:8001
```

---

## 🛠️ Tech Stack

### Backend
| Component | Technology | Role |
|---|---|---|
| Data Streaming | Apache Kafka | Real-time KPI ingestion (10 msg/sec) |
| Storage | PostgreSQL 15 | Historical KPI records |
| Cache | Redis 7 | Live cell state, SSE buffer |
| Pipeline API | FastAPI + psycopg2 | REST endpoints + SSE stream |
| ML Models | Scikit-learn, XGBoost, PyTorch | Anomaly detection + prediction |
| RAG Pipeline | LangChain + ChromaDB | Knowledge retrieval |
| LLM | Mistral AI / Ollama | Natural language responses |
| Embeddings | sentence-transformers | Vector indexing |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 18 + Vite |
| Charts | Recharts |
| Styling | TailwindCSS |
| Real-time | Server-Sent Events (SSE) |
| Icons | Lucide React |
| PDF Export | jsPDF + html2canvas |

### Infrastructure
| Component | Technology |
|---|---|
| Containerization | Docker + Docker Compose |
| Message Broker | Apache Kafka + Zookeeper |
| Orchestration | Docker Compose (9 services) |

---

## 📊 Datasets

| Dataset | Source | Usage |
|---|---|---|
| Cellular Network Handover Prediction | Kaggle (meruvakodandasuraj) | Handover classification, anomaly detection |
| 5G Network KPI Dataset | Kaggle (srikumarnayak) | QoS prediction, LSTM time-series |
| Telecom Dataset | Kaggle (mariamdhieb) | Business intelligence module |

---

## 🤖 ML Models

### Anomaly Detection (Ensemble)
```
Final Score = 0.45 × XGBoost + 0.35 × Isolation Forest + 0.20 × LSTM

Score ≥ 0.70 → 🔴 CRITICAL
Score ≥ 0.40 → 🟡 WARNING  
Score < 0.40 → 🟢 NORMAL
```

### Features (17 engineered features)
- Signal: `rsrp`, `rsrq`, `sinr`, `sinr_rsrp_ratio`, `signal_degradation`
- QoS: `latency`, `throughput_dl`, `throughput_ul`, `packet_loss`, `jitter`
- Derived: `qos_composite_score`, `latency_high`, `throughput_low`, `packet_loss_high`
- Network: `prb_utilization`, `active_users`, `spectral_efficiency`

### LSTM Architecture
```
Input: 20 timesteps × 4 features (sinr, latency, throughput_dl, packet_loss)
     ↓
LSTM (2 layers, hidden=64)
     ↓
Attention Mechanism
     ↓
Classifier (64 → 32 → 1)
     ↓
Output: P(anomaly next step)
```

---

## 🧠 AI Agent

The TeleSight AI agent uses **4 tools** via LangChain:

```python
search_kpi_history(query)      # ChromaDB vector search
get_current_anomalies(level)   # Live anomalies from P1 API
get_ml_prediction(kpi_data)    # Real-time ML scoring from P2 API
get_cell_history(cell_id)      # Historical records for a cell
```

**Example interaction:**
```
User: "Quelles cellules risquent un handover ?"

Agent:
  → get_current_anomalies("critical")
  → search_kpi_history("handover prediction RSRP threshold")
  → get_ml_prediction({"cell_id": "CELL_007", ...})

Response: "3 cellules présentent un risque élevé de handover:
  • CELL_007: RSRP -112 dBm, probabilité handover 78%
  • CELL_013: SINR -2.9 dB, signal dégradé depuis 14h30
  • CELL_019: Vitesse élevée + RSRP limite (-108 dBm)
  Recommandation: Vérifier les cellules voisines et optimiser les seuils A3."
```

---

## 📁 Project Structure

```
telesight-ai/
├── docker-compose.yml              # Master orchestration
├── data/
│   └── unified_kpi_with_anomalies.csv
├── partie1_pipeline/               # Data Pipeline (Port 8000)
│   ├── api/
│   │   ├── main.py
│   │   └── routes/
│   │       ├── kpi.py
│   │       └── stream.py
│   ├── producer/
│   │   ├── kpi_producer.py
│   │   └── data_preparation.py
│   ├── consumer/
│   │   ├── kpi_consumer.py
│   │   └── feature_engineering.py
│   ├── db/init.sql
│   └── docker-compose.yml          # Infrastructure only
├── partie2_ml/                     # ML API (Port 8001)
│   ├── api/
│   │   ├── ml_api.py
│   │   └── predictor.py
│   ├── training/
│   │   ├── 01_prepare_features.py
│   │   ├── 02_train_isolation_forest.py
│   │   ├── 03_train_xgboost.py
│   │   └── 04_train_lstm.py
│   └── models/                     # Trained model files
├── partie3_rag/                    # RAG Agent API (Port 8002)
│   ├── api/rag_api.py
│   ├── rag/
│   │   ├── agent.py
│   │   ├── pipeline.py
│   │   └── ingest.py
│   ├── chroma_db/                  # Vector store
│   └── .env
└── partie4_dashboard/              # React Dashboard (Port 3000)
    └── src/
        ├── components/
        │   ├── KPIChart.jsx
        │   ├── CellMap.jsx
        │   ├── AlertPanel.jsx
        │   ├── AgentChat.jsx
        │   └── ReportButton.jsx
        └── hooks/
            ├── useSSE.js
            └── api.js
```

---

## 🌐 API Endpoints

### Pipeline API (Port 8000)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/kpi/latest` | Latest KPI per cell |
| GET | `/api/kpi/cells` | All cell statuses |
| GET | `/api/kpi/anomalies` | Active anomalies |
| GET | `/api/kpi/stats/global` | Global network stats |
| GET | `/api/kpi/history/{cell_id}` | Cell history |
| GET | `/api/stream/live` | SSE live stream |

### ML API (Port 8001)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ml/predict` | Single KPI prediction |
| POST | `/api/ml/predict/batch` | Batch prediction |
| GET | `/api/ml/score/all-cells` | Score all cells |

### RAG API (Port 8002)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/agent/query` | Ask the AI agent |
| GET | `/api/agent/report` | Generate network report |
| GET | `/api/agent/status` | Agent health check |


---

## 📄 License

This project is built for academic purposes as part of the **5G/Industry 5.0** curriculum.

---

<div align="center">

**TeleSight AI** — *See your network. Predict the future. Act before it breaks.*

Made with ❤️ by the TeleSight Team

</div>