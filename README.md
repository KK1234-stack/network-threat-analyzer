# Network Threat Analyzer

Full-stack network intrusion detection system. Upload CICIDS-format network flow CSVs and get real-time threat classifications with per-session history.

## Stack

- **Backend:** FastAPI + PostgreSQL (SQLAlchemy) + JWT auth
- **Frontend:** Streamlit
- **ML:** Random Forest (production) vs LSTM (PyTorch), tracked with MLflow
- **Infra:** Docker + docker-compose

## Architecture

```
Streamlit UI
     ↓ HTTP
FastAPI Backend  ←→  PostgreSQL (prediction history)
     ↓
ML Inference (Random Forest)
```

## Getting Started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git

### 1. Clone the repo

```bash
git clone https://github.com/KK1234-stack/network-threat-analyzer.git
cd network-threat-analyzer
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and set your values:

```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourchosenpassword
POSTGRES_DB=threat_analyzer
DATABASE_URL=postgresql://postgres:yourchosenpassword@db:5432/threat_analyzer
SECRET_KEY=any-long-random-string
```

### 3. Add the trained model

The RF model file is too large for git. You need to obtain `rf_model.pkl` and place it at:

```
ml/models/rf_model.pkl
```

Options:
- Download from the project's Kaggle notebook (`ml/eda_and_training.ipynb`) — run it and export the model from the Output panel
- Or trigger retraining after startup via `POST /admin/retrain` (requires CICIDS2017 data in `ml/data/`)

> `scaler.pkl` and `label_encoder.pkl` are already included in the repo under `ml/processed/`.

### 4. Start the app

```bash
docker-compose up --build
```

This starts three services:
- **PostgreSQL** — database
- **FastAPI backend** — http://localhost:8000
- **Streamlit frontend** — http://localhost:8501

First build takes 3–5 minutes. Subsequent starts are fast.

### 5. Use the app

1. Open http://localhost:8501
2. Register an account and log in
3. Upload a CICIDS2017-format CSV to get threat classifications
4. View prediction history in the History tab

API docs (Swagger UI): http://localhost:8000/docs

### Stopping the app

```bash
docker-compose down          # stop containers
docker-compose down -v       # stop and delete the database volume
```

## ML Training

Training was done on the CICIDS2017 dataset. See `ml/eda_and_training.ipynb` for the full EDA, preprocessing decisions, and training runs.

To retrain locally:

```bash
cd ml
pip install -r requirements.txt

# 1. Download CICIDS2017 dataset into ml/data/
# 2. Preprocess
python preprocess.py

# 3. Train both models (tracked in MLflow)
python train.py

# 4. Evaluate
python evaluate.py

# MLflow UI
mlflow ui  # opens at http://localhost:5000
```

You can also trigger retraining via the API (hot-reloads without restart):

```
POST /admin/retrain
GET  /admin/retrain/status
```

## Model Results

Trained on CICIDS2017 (2.83M flows, 12 classes). Random Forest is the production model.

| Model | Weighted F1 | Macro F1 |
|---|---|---|
| **Random Forest** | **0.9981** | **0.89** |
| LSTM | 0.9746 | 0.76 |

### Per-class RF Results

| Class | Precision | Recall | F1 |
|---|---|---|---|
| BENIGN | 1.00 | 1.00 | 1.00 |
| DDoS | 1.00 | 1.00 | 1.00 |
| DoS Hulk | 1.00 | 1.00 | 1.00 |
| PortScan | 0.99 | 1.00 | 1.00 |
| DoS GoldenEye | 0.99 | 1.00 | 0.99 |
| DoS Slowhttptest | 0.99 | 0.99 | 0.99 |
| DoS slowloris | 0.99 | 1.00 | 1.00 |
| FTP-Patator | 1.00 | 1.00 | 1.00 |
| SSH-Patator | 1.00 | 1.00 | 1.00 |
| Web Attack - Brute Force | 0.79 | 0.57 | 0.67 |
| Bot | 0.46 | 0.99 | 0.63 |
| Web Attack - XSS | 0.36 | 0.68 | 0.47 |

Bot and Web Attack classes score lower due to limited real samples in the original dataset (under 2k each).

## Dataset

[CICIDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) — Canadian Institute for Cybersecurity.
2.83M network flows across 8 days, 12 traffic classes (1 benign + 11 attack types).

Preprocessing steps: strip column whitespace, drop inf/NaN rows, remove 13 constant/near-constant/duplicate columns, undersample BENIGN to 200k, SMOTE minority classes to 50k minimum, StandardScaler.

## Roadmap / Future Work

### User Data Feeds Retraining
Currently the model is trained once on CICIDS2017 and retraining re-uses the same static dataset. The intended future flow is:

```
User uploads CSV → backend saves it to persistent storage
                          ↓
              Admin reviews + verifies predictions
                          ↓
         Retrain on CICIDS2017 + accumulated user submissions
                          ↓
              Better model deployed automatically
```

This requires:
- **Persistent upload storage** — currently planned as a Docker volume (`ml/uploads/`), swap to **AWS S3** for production deployments
- **Labeling workflow** — admin UI to mark predictions as correct/incorrect before they feed into retraining
- **Combined training pipeline** — `trainer.py` reads original `.npy` arrays + new labeled CSVs and merges them before training

### Raw Packet Support (.pcap)
Currently the system expects CSVs pre-processed by **CICFlowMeter** (65 flow-level statistical features). Real-world users have raw `.pcap` files, not pre-processed CSVs.

Planned approach:
```
.pcap upload → packet parser (scapy/dpkt) → flow feature extraction
             → same 65-feature format → existing RF classifier
```

A longer-term alternative is replacing the RF with a **deep learning model with automatic feature extraction** (CNN or Transformer on raw packet byte sequences), eliminating the need for manual feature engineering entirely.

### Deployment
- CI/CD pipeline is scaffolded (`.github/workflows/deploy.yml`) but deploy steps are disabled pending Render/Railway setup
- Re-enable by adding `RENDER_DEPLOY_HOOK_BACKEND` and `RENDER_DEPLOY_HOOK_FRONTEND` as GitHub secrets and restoring the push trigger

## Project Structure

```
network-threat-analyzer/
├── backend/                  # FastAPI app
│   └── app/
│       ├── core/             # config, database, security
│       ├── models/           # SQLAlchemy ORM models
│       ├── routes/           # auth, predictions, retrain
│       └── ml/               # inference + background trainer
├── frontend/                 # Streamlit app
├── ml/                       # Training pipeline (run independently)
│   ├── eda_and_training.ipynb
│   ├── preprocess.py
│   ├── train.py
│   ├── evaluate.py
│   ├── processed/            # scaler.pkl, label_encoder.pkl
│   └── models/               # trained model files (gitignored)
└── docker-compose.yml
```
