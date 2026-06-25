from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import declarative_base
import enum
from datetime import datetime

Base = declarative_base()

class ItemStatus(enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    APPROVED = "approved"
    REJECTED = "rejected"

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String, nullable=False)
    status = Column(Enum(ItemStatus), default=ItemStatus.PENDING, index=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Item(id={self.id}, content='{self.content}', status='{self.status}')>"
