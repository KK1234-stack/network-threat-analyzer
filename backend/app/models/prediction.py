from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    total_flows = Column(Integer)
    threat_count = Column(Integer)
    benign_count = Column(Integer)

    # Label breakdown e.g. {"DDoS": 120, "PortScan": 30, "BENIGN": 850}
    label_distribution = Column(JSON)

    model_version = Column(String)
    inference_time_ms = Column(Float)

    user = relationship("User", back_populates="predictions")
