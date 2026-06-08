# Network Threat Analyzer

Full-stack network intrusion detection system. Upload CICIDS-format network flow CSVs and get real-time threat classifications with per-session history.

## Stack

- **Backend:** FastAPI + PostgreSQL (SQLAlchemy + Alembic) + JWT auth
- **Frontend:** Streamlit
- **ML:** LSTM (PyTorch) vs Random Forest baseline, tracked with MLflow
- **Infra:** Docker + docker-compose, GitHub Actions CI/CD, deployed on Render

## Architecture

```
Streamlit UI
     ↓ HTTP
FastAPI Backend  ←→  PostgreSQL (prediction history)
     ↓
ML Inference (LSTM / RF)
```

## Running Locally

```bash
cp .env.example .env          # fill in your values
docker-compose up --build     # starts db + backend + frontend
```

- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:8501

## ML Training (run separately before starting the app)

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

## Model Results

| Model | Weighted F1 |
|---|---|
| Random Forest (baseline) | TBD |
| LSTM | TBD |

## Project Structure

```
network-threat-analyzer/
├── backend/          # FastAPI app
├── frontend/         # Streamlit app
├── ml/               # Training scripts (run independently)
└── docker-compose.yml
```
