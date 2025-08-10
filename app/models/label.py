from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from .database import Base

class Label(Base):
    __tablename__ = "label"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    type = Column(String(50), nullable=False)  # bug, feature, ux, etc.
    description = Column(Text, nullable=True)
    
    # Relationships
    feedback_labels = relationship("FeedbackLabel", back_populates="label")
    
    def __repr__(self):
        return f"<Label(name='{self.name}', type='{self.type}')>" 