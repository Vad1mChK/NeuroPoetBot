import json
import random
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey, text, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import Optional, List, Dict

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    registered_at = Column(DateTime, default=datetime.now)

    # Relationships
    emotions = relationship("EmotionAnalysis", back_populates="user")
    generations = relationship("Generation", back_populates="user")


class EmotionAnalysis(Base):
    __tablename__ = 'emotion_analyses'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    performed_at = Column(DateTime, default=datetime.now)
    emotions = Column(JSON)  # Stores dict like {'happy': 0.8, 'sad': 0.2}

    # Relationships
    user = relationship("User", back_populates="emotions")


class Generation(Base):
    __tablename__ = 'generations'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    performed_at = Column(DateTime, default=datetime.now)
    request_text = Column(String)
    response_text = Column(String)

    # Relationships
    user = relationship("User", back_populates="generations")


class Database:
    def __init__(self, db_url: str = "sqlite:///neuropoet.db"):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

    def add_user(self, user_id: int) -> None:
        """Add new user if not exists"""
        with self.Session() as session:
            if not session.get(User, user_id):
                session.add(User(user_id=user_id, registered_at=datetime.now()))
                session.commit()


    def log_emotion_analysis(
            self,
            user_id: int,
            emotions: Dict[str, float]
    ) -> None:
        """Log emotion analysis result"""
        with self.Session() as session:
            self.add_user(user_id)  # Ensure user exists
            session.add(EmotionAnalysis(
                user_id=user_id,
                emotions=emotions
            ))
            session.commit()

    def log_generation(
            self,
            user_id: int,
            request_text: str,
            response_text: str
    ) -> None:
        """Log poetry generation result"""
        with self.Session() as session:
            self.add_user(user_id)  # Ensure user exists
            session.add(Generation(
                user_id=user_id,
                request_text=request_text,
                response_text=response_text
            ))
            session.commit()

    def get_user_history(
            self,
            user_id: int,
            limit: int = 10
    ) -> Dict[str, List]:
        """Get user's interaction history"""
        with self.Session() as session:
            return {
                "emotions": session.query(EmotionAnalysis)
                .filter_by(user_id=user_id)
                .order_by(EmotionAnalysis.performed_at.desc())
                .limit(limit)
                .all(),
                "generations": session.query(Generation)
                .filter_by(user_id=user_id)
                .order_by(Generation.performed_at.desc())
                .limit(limit)
                .all()
            }

    def get_user_data(self, user_id: int) -> User | None:
        with (self.Session() as session):
            return (
                session.query(User)
                .filter_by(user_id=user_id)
                .first()
            )

    def get_all_poems(self, limit: int = 100) -> list[str]:
        with self.Session() as session:
            generations = (
                session.query(Generation)
                .limit(limit)
                .all()
            )
            return [generation.response_text for generation in generations]

    def get_random_poem_fast(self) -> str | None:
        with self.Session() as session:
            max_id = session.query(func.max(Generation.id)).scalar()
            random_id = random.randint(1, max_id)
            return (
                session.query(Generation)
                .filter(Generation.id >= random_id)
                .limit(1)
                .scalar()
                .response_text
            )


    def check_health(self) -> bool:
        """Simple database health check"""
        try:
            with self.Session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            print(f"Database health check failed: {str(e)}")
            return False


# Usage example
if __name__ == "__main__":
    db = Database()

    # Test data
    user_id = 123456789
    db.add_user(user_id)

    # Log emotion analysis
    db.log_emotion_analysis(user_id, {"happy": 0.8, "sad": 0.1})

    # Log generation
    db.log_generation(
        user_id,
        "Грустный текст о осени",
        "Листья падают, грусть в воздухе..."
    )

    # Get history
    history = db.get_user_history(user_id)
    print(f"Emotion history: {len(history['emotions'])} entries")
    print(f"Generation history: {len(history['generations'])} entries")
