from sqlalchemy import Column, Integer, String, Text, Float, DateTime, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Cluster(Base):
    __tablename__ = "cluster"
    
    id = Column(Integer, primary_key=True, index=True)
    centroid_embedding = Column(LargeBinary, nullable=True)  # Store as bytes
    summary = Column(Text, nullable=True)
    size = Column(Integer, default=1)
    severity_est = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    feedback = relationship("Feedback", back_populates="cluster")
    
    def __repr__(self):
        return f"<Cluster(id={self.id}, size={self.size}, confidence={self.confidence})>" 