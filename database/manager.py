from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from .models import Base, Item, ItemStatus
from datetime import datetime
import threading
from config import DATABASE_URL
from contextlib import contextmanager

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
            return cls._instance

    def __init__(self, db_url=None):
        if hasattr(self, 'initialized'):
            return
        # Fallback to config DATABASE_URL if not provided
        db_url = db_url or DATABASE_URL
        
        connect_args = {}
        # check_same_thread is SQLite-specific
        if db_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            
        self.engine = create_engine(db_url, connect_args=connect_args)
        Base.metadata.create_all(self.engine)
        # expire_on_commit=False prevents DetachedInstanceError when accessing model attributes outside sessions
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.initialized = True

    @contextmanager
    def get_session(self):
        """Yields a database session and handles transaction lifecycle."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_items(self, contents):
        # Filter unique and non-empty lines
        unique_contents = list(set([c.strip() for c in contents if c.strip()]))
        if not unique_contents:
            return 0
            
        with self.get_session() as session:
            # Query existing in chunks of 900 to avoid SQLite parameter limit and load limits
            existing_set = set()
            for i in range(0, len(unique_contents), 900):
                chunk = unique_contents[i:i+900]
                existing = session.query(Item.content).filter(Item.content.in_(chunk)).all()
                existing_set.update(e[0] for e in existing)
                
            new_items = [Item(content=c) for c in unique_contents if c not in existing_set]
            session.add_all(new_items)
            return len(new_items)

    def get_assigned_item(self, user_id):
        with self.get_session() as session:
            return session.query(Item).filter(
                Item.user_id == user_id, 
                Item.status == ItemStatus.ASSIGNED
            ).first()

    def assign_next_item(self, user_id, username):
        with self.get_session() as session:
            # Check if user already has an item
            existing = session.query(Item).filter(
                Item.user_id == user_id, 
                Item.status == ItemStatus.ASSIGNED
            ).first()
            if existing:
                return existing, False # Already has one

            # Find next pending item
            item = session.query(Item).filter(
                Item.status == ItemStatus.PENDING
            ).order_by(Item.id).first()

            if item:
                item.status = ItemStatus.ASSIGNED
                item.user_id = user_id
                item.username = username
                item.assigned_at = datetime.now()
                return item, True
            return None, True

    def resolve_item(self, user_id, status: ItemStatus):
        with self.get_session() as session:
            item = session.query(Item).filter(
                Item.user_id == user_id,
                Item.status == ItemStatus.ASSIGNED
            ).first()

            if item:
                item.status = status
                item.completed_at = datetime.now()
                return True
            return False

    def get_stats(self):
        with self.get_session() as session:
            stats = session.query(Item.status, func.count(Item.id)).group_by(Item.status).all()
            result = {status.value: count for status, count in stats}
            # Ensure all statuses are present
            for s in ItemStatus:
                if s.value not in result:
                    result[s.value] = 0
            return result

    def export_items(self, status: ItemStatus):
        with self.get_session() as session:
            items = session.query(Item).filter(Item.status == status).all()
            return [i.content for i in items]

    def clear_items(self, status: ItemStatus):
        with self.get_session() as session:
            session.query(Item).filter(Item.status == status).delete()

    def clear_all_items(self):
        with self.get_session() as session:
            session.query(Item).delete()

    def get_recent_activity(self, limit=10):
        with self.get_session() as session:
            return session.query(Item).filter(
                Item.status.in_([ItemStatus.APPROVED, ItemStatus.REJECTED])
            ).order_by(Item.completed_at.desc()).limit(limit).all()
