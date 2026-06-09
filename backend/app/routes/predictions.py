from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import pandas as pd
import io

from app.core.database import get_db
from app.models.prediction import Prediction
from app.models.user import User
from app.routes.auth import get_current_user
from app.ml.model import run_inference

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/upload")
async def upload_and_predict(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    contents = await file.read()
    try:
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse CSV — ensure the file is valid UTF-8 CSV")

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV is empty")

    if len(df) > 100_000:
        raise HTTPException(status_code=400, detail="CSV too large — maximum 100,000 rows per upload")

    try:
        results = run_inference(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

    label_dist = {}
    for label in results["labels"]:
        label_dist[label] = label_dist.get(label, 0) + 1

    threat_labels = [l for l in results["labels"] if l != "BENIGN"]

    prediction = Prediction(
        user_id=current_user.id,
        filename=file.filename,
        total_flows=len(results["labels"]),
        threat_count=len(threat_labels),
        benign_count=label_dist.get("BENIGN", 0),
        label_distribution=label_dist,
        model_version=results["model_version"],
        inference_time_ms=results["inference_time_ms"],
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return {
        "prediction_id": prediction.id,
        "filename": file.filename,
        "total_flows": prediction.total_flows,
        "threat_count": prediction.threat_count,
        "benign_count": prediction.benign_count,
        "label_distribution": label_dist,
        "model_version": results["model_version"],
        "inference_time_ms": results["inference_time_ms"],
        "per_row": [
            {"flow_index": i, "label": l, "confidence": c}
            for i, (l, c) in enumerate(zip(results["labels"], results["confidences"]))
        ],
    }


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id)
        .order_by(Prediction.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "uploaded_at": r.uploaded_at.isoformat(),
            "total_flows": r.total_flows,
            "threat_count": r.threat_count,
            "benign_count": r.benign_count,
            "label_distribution": r.label_distribution,
            "model_version": r.model_version,
            "inference_time_ms": r.inference_time_ms,
        }
        for r in records
    ]
