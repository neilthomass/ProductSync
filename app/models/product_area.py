from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from .database import Base

class ProductArea(Base):
    __tablename__ = "product_area"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Relationships
    feedback = relationship("Feedback", back_populates="product_area")
    
    def __repr__(self):
        return f"<ProductArea(name='{self.name}')>" 