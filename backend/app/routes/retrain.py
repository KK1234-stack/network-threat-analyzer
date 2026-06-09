from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.routes.auth import get_current_user
from app.models.user import User
from app.ml.trainer import trigger_retrain, get_state

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.email != settings.ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/retrain", status_code=202)
def start_retrain(current_user: User = Depends(require_admin)):
    if not trigger_retrain():
        raise HTTPException(status_code=409, detail="Retraining already in progress")
    return {"message": "Retraining started"}


@router.get("/retrain/status")
def retrain_status(current_user: User = Depends(require_admin)):
    return get_state()
