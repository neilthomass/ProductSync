from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class SourceUser(Base):
    __tablename__ = "source_user"
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False)  # discord, slack, notion
    handle = Column(String(100), nullable=False)
    is_internal = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<SourceUser(platform='{self.platform}', handle='{self.handle}')>" 