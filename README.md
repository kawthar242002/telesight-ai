<<<<<<< HEAD
<div align="center">
  <h1>📡 TeleSight AI</h1>
  <p><strong>Plateforme Intelligente de Supervision de Réseau Télécom 3G/4G/5G en Temps Réel</strong></p>

  [![Architecture](https://img.shields.io/badge/Architecture-Kafka%20%2B%20ML%20%2B%20RAG%20%2B%20React-6366f1)](#-architecture-du-projet)
  [![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)](#-prérequis)
  [![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=black)](#-dashboard-frontend)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](#-licence)
</div>

---

## 📖 À propos

**TeleSight AI** est une solution complète de bout en bout pour la supervision des réseaux télécoms. Elle ingère des flux de données en temps réel (KPIs cellulaires), détecte les anomalies à l'aide de modèles d'Intelligence Artificielle (Machine Learning) et intègre un agent conversationnel (RAG) pour aider les opérateurs à diagnostiquer et résoudre les problèmes réseau via une interface moderne.

Projet académique réalisé par une équipe de 4 étudiants.

---

## 🚀 Fonctionnalités Principales

- **Ingestion Temps Réel** : Pipeline Kafka asynchrone capable de traiter des milliers de logs réseau par seconde.
- **Détection d'Anomalies ML** : Modèle d'ensemble combinant *Isolation Forest*, *XGBoost* et *LSTM (Deep Learning)* pour une précision maximale.
- **Assistant Virtuel IA (RAG)** : Agent LLM propulsé par LangChain et ChromaDB, interrogeable en langage naturel sur la documentation 3GPP et l'état actuel du réseau. Compatible avec Mistral, OpenAI ou **Ollama** (100% local).
- **Génération de Rapports PDF** : Export automatisé de l'état du réseau généré par l'IA.
- **Dashboard Interactif (Light Theme)** : Interface utilisateur moderne développée en React, avec graphiques temps-réel (Recharts) et carte des cellules.

---

## 🏗 Architecture du Projet

L'architecture est découpée en 4 micro-services indépendants :

```text
telesight_ai/
├── partie1_pipeline/    # 🟡 Data Engineer  | Kafka + Redis + PostgreSQL + FastAPI (:8000)
├── partie2_ml/          # 🟢 ML Engineer    | Isolation Forest + XGBoost + LSTM + FastAPI (:8001)
├── partie3_rag/         # 🔵 GenAI Engineer | LangChain + ChromaDB + LLM API + FastAPI (:8002)
├── partie4_dashboard/   # 🔴 Frontend UI    | React + Vite + TailwindCSS (:3000)
├── data/                # 🗂️ Datasets générés et traités
└── start.ps1            # 🚀 Script de lancement unifié PowerShell
```

---

## ⚙️ Prérequis

Pour exécuter le projet localement, assurez-vous d'avoir installé :

| Outil | Version Minimale | Téléchargement |
|---|---|---|
| **Docker Desktop** | `4.x` | [Lien](https://www.docker.com/products/docker-desktop) |
| **Python** | `3.10+` | [Lien](https://www.python.org/downloads/) |
| **Node.js** | `18+` | [Lien](https://nodejs.org/) |

---

## 🏃‍♂️ Démarrage Rapide (Windows)

La méthode la plus simple pour lancer tous les services (Infrastructure Docker, Ingestion, API ML, Agent RAG, et le Dashboard React) est d'utiliser le script unifié PowerShell.

1. **Ouvrez un terminal PowerShell** à la racine du projet.
2. **Exécutez le script de lancement :**
   ```powershell
   .\start.ps1
   ```

*Ce script s'occupe de lancer Docker, démarrer l'ingestion Kafka, initialiser ChromaDB et lancer les serveurs Uvicorn ainsi que le Dashboard Vite.*

**Accéder au Dashboard :** 👉 [http://localhost:3000](http://localhost:3000)

---

## 🧠 Configuration de l'Agent IA (RAG)

L'agent RAG utilise des modèles de langage (LLM) pour répondre aux questions. Configurez le fournisseur de votre choix dans le fichier `partie3_rag/.env` :

```env
# Option 1 : Ollama (100% local, gratuit et privé - Recommandé)
LLM_PROVIDER=ollama
LLM_MODEL=llama3  # ou mistral:7b

# Option 2 : Mistral AI API
# LLM_PROVIDER=mistral
# MISTRAL_API_KEY=votre_cle_api

# Option 3 : OpenAI API
# LLM_PROVIDER=openai
# OPENAI_API_KEY=votre_cle_api
```

---

## 📡 Endpoints API & Ports

| Service | Port | Description |
|---|---|---|
| **Pipeline Core API** | `:8000` | Gère les flux temps réel, l'historique et la communication avec Kafka/Redis. |
| **Machine Learning API**| `:8001` | Moteur d'inférence (Scoring d'anomalies, prédiction Handover). |
| **Agent RAG API** | `:8002` | Interface avec le LLM et la base vectorielle ChromaDB. |
| **React Dashboard** | `:3000` | Interface utilisateur graphique (Light Theme). |
| **Kafka / Zookeeper** | `:9092 / 2181`| Broker de messages (Docker). |
| **PostgreSQL / Redis** | `:5432 / 6379`| Bases de données persistante et en mémoire (Docker). |

---

## 🔬 Modèles de Machine Learning (Partie 2)

Le système utilise un système de vote (Ensemble) pondéré pour déterminer l'état d'alerte d'une cellule :

- **Isolation Forest** (Non supervisé) : Apprentissage des patterns normaux du réseau. (*Poids: 35%*)
- **XGBoost Anomaly** (Supervisé) : Détection basée sur 17 features réseaux (SINR, Latence, etc.). (*Poids: 45%*)
- **LSTM avec Attention** (Séries temporelles) : Analyse de fenêtres séquentielles (20 steps). (*Poids: 20%*)

---

<div align="center">
  <p>Construit avec ❤️ par l'équipe TeleSight AI.</p>
</div>
=======
# telesight-ai
>>>>>>> 2057c6643a424bf269e724e6ab0e253e2fee007e
