from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False)  # discord, slack, notion
    source_msg_id = Column(String(100), nullable=False)
    author_id = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    text_raw = Column(Text, nullable=False)
    text_clean = Column(Text, nullable=True)
    product_area_id = Column(Integer, ForeignKey("product_area.id"), nullable=True)
    priority_score = Column(Float, nullable=True)
    cluster_id = Column(Integer, ForeignKey("cluster.id"), nullable=True)
    status = Column(String(50), default="new")  # new, triaged, resolved
    
    # Relationships
    product_area = relationship("ProductArea", back_populates="feedback")
    cluster = relationship("Cluster", back_populates="feedback")
    labels = relationship("FeedbackLabel", back_populates="feedback")
    
    __table_args__ = (
        # Ensure idempotency as specified in README
        {'postgresql_partition_by': 'LIST (source)'}
    )

class FeedbackLabel(Base):
    __tablename__ = "feedback_label"
    
    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(Integer, ForeignKey("feedback.id"), nullable=False)
    label_id = Column(Integer, ForeignKey("label.id"), nullable=False)
    score = Column(Float, nullable=False)  # confidence score
    
    # Relationships
    feedback = relationship("Feedback", back_populates="labels")
    label = relationship("Label", back_populates="feedback_labels") 