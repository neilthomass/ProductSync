from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Initiative(Base):
    __tablename__ = "initiative"
    
    id = Column(Integer, primary_key=True, index=True)
    jira_key = Column(String(50), nullable=True, unique=True)
    status = Column(String(50), default="new")  # new, in_progress, done
    owner = Column(String(100), nullable=True)
    eta = Column(DateTime(timezone=True), nullable=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Initiative(jira_key='{self.jira_key}', status='{self.status}')>" 