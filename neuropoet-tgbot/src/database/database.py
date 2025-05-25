import json
import random
from collections import defaultdict
from datetime import datetime
from enum import Enum

from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey, text, func, cast, Boolean
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, joinedload
from typing import Optional, List, Dict

Base = declarative_base()


class GenerationModel(Enum):
    RUGPT3 = 'ru_gpt3'
    DEEPSEEK = 'deepseek'


DEFAULT_USER_SETTINGS = {
    "preferred_model": GenerationModel.RUGPT3.value,
}

def get_default_user_settings():
    return json.loads(json.dumps(DEFAULT_USER_SETTINGS))

class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    registered_at = Column(DateTime, default=datetime.now)
    user_settings = Column(MutableDict.as_mutable(JSON), default=lambda: DEFAULT_USER_SETTINGS.copy())

    # Relationships
    emotions = relationship("EmotionAnalysis", back_populates="user")
    generations = relationship("Generation", back_populates="user")
    emotion_ratings = relationship("EmotionRating", back_populates="user")


class EmotionAnalysis(Base):
    __tablename__ = 'emotion_analyses'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    performed_at = Column(DateTime, default=datetime.now)
    request_text = Column(String)  # Текст сообщения
    emotions = Column(JSON)  # Stores dict like {'happy': 0.8, 'sad': 0.2}

    # Relationships
    user = relationship("User", back_populates="emotions")
    ratings = relationship("EmotionRating", back_populates="emotion_analysis")


class GenerationRating(Base):
    __tablename__ = 'generation_ratings'

    id = Column(Integer, primary_key=True)
    rater_id = Column(Integer, ForeignKey('users.user_id'))
    generation_id = Column(Integer, ForeignKey('generations.id'))
    rating = Column(Integer, nullable=False)  # rating from 1 to 5


class Generation(Base):
    __tablename__ = 'generations'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    performed_at = Column(DateTime, default=datetime.now)
    request_text = Column(String)
    emotions = Column(JSON)
    response_text = Column(String)
    model = Column(String, nullable=False, default="ru_gpt3")
    rhyme_scheme = Column(String, default="Неизвестно")
    genre = Column(String, default="произвольный")

    # Relationships
    user = relationship("User", back_populates="generations")
    ratings = relationship("GenerationRating", backref="generation")

    def average_rating(self) -> Optional[float]:
        if self.ratings and len(self.ratings) > 0:
            return sum(r.rating for r in self.ratings) / len(self.ratings)
        return None


class BotFeedback(Base):
    __tablename__ = 'bot_feedback'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    rating = Column(Integer, nullable=False)  # Rating from 1 to 5
    message = Column(String, nullable=True)   # Optional feedback message
    telegram_message_id = Column(Integer, nullable=False, unique=True)  # Explicitly store Telegram message ID
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="feedbacks")


class EmotionRating(Base):
    __tablename__ = 'emotion_ratings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    emotion_analysis_id = Column(Integer, ForeignKey('emotion_analyses.id'))
    is_correct = Column(Boolean, nullable=False)  # правильно ли определена эмоция
    correct_emotion = Column(String, nullable=True)  # правильная эмоция, если is_correct=False
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    user = relationship("User", back_populates="emotion_ratings")
    emotion_analysis = relationship("EmotionAnalysis", back_populates="ratings")


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
            emotions: Dict[str, float],
            request_text: str
    ) -> EmotionAnalysis:
        """Log emotion analysis result and return the created object"""
        with self.Session() as session:
            self.add_user(user_id)  # Ensure user exists
            analysis = EmotionAnalysis(
                user_id=user_id,
                emotions=emotions,
                request_text=request_text
            )
            session.add(analysis)
            session.commit()
            session.refresh(analysis)  # Refresh to get the generated ID
            return analysis

    def log_generation(
            self,
            user_id: int,
            request_text: str,
            emotions: Dict[str, float],
            response_text: str,
            model: str,
            rhyme_scheme: str,
            genre: str,
    ) -> Generation:
        """Log poetry generation result and explicitly return the Generation object"""
        with self.Session() as session:
            self.add_user(user_id)  # Ensure user exists

            generation = Generation(
                user_id=user_id,
                request_text=request_text,
                emotions=emotions,
                response_text=response_text,
                model=model,
                rhyme_scheme=rhyme_scheme,
                genre=genre,
            )
            session.add(generation)
            session.commit()

            session.refresh(generation)  # Explicitly refresh object to get generated ID
            return generation

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

    def rate_generation(
        self, rater_id: int, generation_id: int, rating: int
    ) -> None:
        """Explicitly rate a generation"""
        with self.Session() as session:
            existing_rating = session.query(GenerationRating).filter_by(
                rater_id=rater_id, generation_id=generation_id
            ).first()
            if existing_rating is None:
                session.add(GenerationRating(
                    rater_id=rater_id,
                    generation_id=generation_id,
                    rating=rating
                ))
                session.commit()

    def has_user_rated(self, rater_id: int, generation_id: int) -> bool:
        """Explicitly check if user already rated generation"""
        with self.Session() as session:
            return session.query(GenerationRating).filter_by(
                rater_id=rater_id, generation_id=generation_id
            ).first() is not None

    def get_generation_rating_distribution(self) -> dict[int, int]:
        """Get explicit distribution of generation ratings (1–5)."""
        with self.Session() as session:
            ratings_counts = session.query(
                GenerationRating.rating,
                func.count(GenerationRating.rating)
            ).group_by(GenerationRating.rating).all()

            # Explicitly ensure keys 1 through 5 are present, defaulting to 0
            distribution = defaultdict(int, {rating: count for rating, count in ratings_counts})

            return {rating: distribution[rating] for rating in range(1, 6)}

    def get_generation_rating_distribution_by_model(self) -> dict[str, dict[int, int]]:
        """
        Get explicit distribution of generation ratings (1–5) grouped by generation model.
        Example:
            {
                "deepseek": {1: 0, 2: 0, 3: 0, 4: 1, 5: 9},
                "ru_gpt3": {1: 2, 2: 1, 3: 3, 4: 7, 5: 4}
            }
        """
        with self.Session() as session:
            ratings_data = session.query(
                Generation.model,
                GenerationRating.rating,
                func.count(GenerationRating.rating)
            ).join(
                GenerationRating, Generation.id == GenerationRating.generation_id
            ).group_by(
                Generation.model,
                GenerationRating.rating
            ).all()

            # Explicitly prepare nested dictionaries with default zeros
            model_distribution = defaultdict(lambda: {rating: 0 for rating in range(1, 6)})

            for model, rating, count in ratings_data:
                model_distribution[model][rating] = count

            return dict(model_distribution)

    def get_user_data(self, user_id: int) -> User | None:
        with (self.Session() as session):
            return (
                session.query(User)
                .filter_by(user_id=user_id)
                .first()
            )

    def update_user_settings(self, user_id: int, new_settings: dict) -> bool:
        """Explicitly update user settings JSON by user_id."""
        with self.Session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()

            if user:
                if user.user_settings is None:
                    user.user_settings = new_settings
                else:
                    user.user_settings.update(new_settings)

                session.commit()
                return True
            return False

    def get_all_poems(self, limit: int = 100) -> list[str]:
        with self.Session() as session:
            generations = (
                session.query(Generation)
                .limit(limit)
                .all()
            )
            return [generation.response_text for generation in generations]

    def get_random_poem_fast(self) -> Generation | None:
        with self.Session() as session:
            max_id = session.query(func.max(Generation.id)).scalar()
            if not max_id:
                return None

            random_id = random.randint(1, max_id)

            generation = (
                session.query(Generation)
                .options(joinedload(Generation.ratings))  # Explicitly eager load ratings
                .filter(Generation.id >= random_id)
                .order_by(Generation.id)
                .limit(1)
                .first()
            )

            return generation

    def log_bot_feedback(
            self,
            user_id: int,
            rating: int,
            telegram_message_id: int,
            message: Optional[str] = None
    ) -> None:
        with self.Session() as session:
            self.add_user(user_id)
            feedback = BotFeedback(
                user_id=user_id,
                rating=rating,
                telegram_message_id=telegram_message_id,
                message=message
            )
            session.add(feedback)
            session.commit()

    def update_feedback_message(
            self,
            telegram_message_id: int,
            new_message: str
    ) -> bool:
        """Explicitly updates feedback message using telegram_message_id."""
        with self.Session() as session:
            feedback = session.query(BotFeedback).filter_by(
                telegram_message_id=telegram_message_id
            ).first()

            if feedback:
                feedback.message = new_message
                session.commit()
                return True
            return False

    def get_average_ratings_by_model(self) -> dict[str, float]:
        """Explicitly calculate average ratings grouped by model."""
        with self.Session() as session:
            results = session.query(
                Generation.model,
                func.avg(GenerationRating.rating).label('average_rating'),
                func.count(GenerationRating.id).label('num_ratings')
            ).join(
                GenerationRating, Generation.id == GenerationRating.generation_id
            ).group_by(
                Generation.model
            ).all()

            return {
                model: round(avg_rating, 2)
                for model, avg_rating, count in results
                if count > 0
            }

    def get_ratings_by_top_emotion(self) -> dict[str, dict[str, float]]:
        """Explicitly compute average ratings grouped by the top emotion."""
        with self.Session() as session:
            query_results = session.query(
                Generation.emotions,
                GenerationRating.rating
            ).join(
                GenerationRating, Generation.id == GenerationRating.generation_id
            ).all()

            emotion_stats = defaultdict(list)

            for emotions, rating in query_results:
                if emotions:
                    top_emotion = max(emotions.items(), key=lambda x: x[1])[0]
                    emotion_stats[top_emotion].append(rating)

            return {
                emotion: {
                    "avg_rating": round(sum(ratings) / len(ratings), 2),
                    "count": len(ratings)
                }
                for emotion, ratings in emotion_stats.items()
            }

    def get_ratings_by_rhyme_scheme(self) -> dict[str, dict[str, float]]:
        """Calculate average ratings explicitly by rhyme scheme."""
        with self.Session() as session:
            rhyme_scheme_results = session.query(
                Generation.rhyme_scheme,
                func.avg(GenerationRating.rating),
                func.count(GenerationRating.id)
            ).join(
                GenerationRating, Generation.id == GenerationRating.generation_id
            ).group_by(Generation.rhyme_scheme).all()

            return {
                scheme: {
                    "avg_rating": round(avg, 2),
                    "count": count
                }
                for scheme, avg, count in rhyme_scheme_results
            }

    def get_ratings_by_genre(self) -> dict[str, dict[str, float]]:
        """Calculate average ratings explicitly by genre."""
        with self.Session() as session:
            genre_results = session.query(
                Generation.genre,
                func.avg(GenerationRating.rating),
                func.count(GenerationRating.id)
            ).join(
                GenerationRating, Generation.id == GenerationRating.generation_id
            ).group_by(Generation.genre).all()

            return {
                genre: {
                    "avg_rating": round(avg, 2),
                    "count": count
                }
                for genre, avg, count in genre_results
            }

    def get_feedback_summary(self) -> dict[str, Optional[dict]]:
        with self.Session() as session:
            avg_rating = session.query(func.avg(BotFeedback.rating)).scalar()
            avg_generation_rating = session.query(func.avg(GenerationRating.rating)).scalar()
            avg_generation_rating_by_model = self.get_average_ratings_by_model()

            best_feedback = session.query(BotFeedback) \
                .order_by(BotFeedback.rating.desc(), BotFeedback.created_at.asc()) \
                .first()

            worst_feedback = session.query(BotFeedback) \
                .order_by(BotFeedback.rating.asc(), BotFeedback.created_at.asc()) \
                .first()

            newest_feedback = session.query(BotFeedback) \
                .order_by(BotFeedback.created_at.desc()) \
                .first()

            longest_feedback = session.query(BotFeedback) \
                .filter(BotFeedback.message.isnot(None)) \
                .order_by(func.length(BotFeedback.message).desc()) \
                .first()

            def serialize_feedback(fb: Optional[BotFeedback]) -> Optional[dict]:
                if fb:
                    return {
                        "user_id": fb.user_id,
                        "rating": fb.rating,
                        "message": fb.message,
                        "created_at": fb.created_at.isoformat()
                    }
                return None

            return {
                "average_rating": round(avg_rating, 2) if avg_rating else None,
                "avg_gen_rating":
                    round(avg_generation_rating, 2) if avg_generation_rating else None,
                "avg_gen_rating_by_model": avg_generation_rating_by_model,
                "best_feedback": serialize_feedback(best_feedback),
                "worst_feedback": serialize_feedback(worst_feedback),
                "newest_feedback": serialize_feedback(newest_feedback),
                "longest_feedback": serialize_feedback(longest_feedback),
            }

    def export_bot_feedback_json(self) -> str:
        """Export all feedback entries explicitly to JSON."""
        with self.Session() as session:
            bot_feedback_entries = session.query(BotFeedback).order_by(BotFeedback.created_at.asc()).all()
            summary = self.get_feedback_summary()

            feedback_data = {
                "summary": summary,
                "generations": {
                    "avg_rating": summary["avg_gen_rating"],
                    "avg_rating_by_model": summary["avg_gen_rating_by_model"],
                    "rating_distribution": self.get_generation_rating_distribution(),
                    "rating_distibution_by_model": self.get_generation_rating_distribution_by_model(),
                    "ratings_by_top_emotion": self.get_ratings_by_top_emotion(),
                    "ratings_by_rhyme_scheme": self.get_ratings_by_rhyme_scheme(),
                    "ratings_by_genre": self.get_ratings_by_genre(),
                },
                "bot": [
                    {
                        "id": fb.id,
                        "user_id": fb.user_id,
                        "rating": fb.rating,
                        "message": fb.message,
                        "telegram_message_id": fb.telegram_message_id,
                        "created_at": fb.created_at.isoformat()
                    }
                    for fb in bot_feedback_entries
                ]
            }

            return json.dumps(feedback_data, ensure_ascii=False, indent=2)

    def check_health(self) -> bool:
        """Simple database health check"""
        try:
            with self.Session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            print(f"Database health check failed: {str(e)}")
            return False

    def rate_emotion_analysis(
        self,
        user_id: int,
        emotion_analysis_id: int,
        is_correct: bool,
        correct_emotion: Optional[str] = None
    ) -> None:
        """Сохраняет оценку анализа эмоций"""
        with self.Session() as session:
            session.add(EmotionRating(
                user_id=user_id,
                emotion_analysis_id=emotion_analysis_id,
                is_correct=is_correct,
                correct_emotion=correct_emotion
            ))
            session.commit()

    def has_user_rated_emotion(self, user_id: int, emotion_analysis_id: int) -> bool:
        """Проверяет, оценивал ли пользователь этот анализ эмоций"""
        with self.Session() as session:
            return session.query(EmotionRating).filter_by(
                user_id=user_id,
                emotion_analysis_id=emotion_analysis_id
            ).first() is not None

    def get_emotion_rating_stats(self) -> dict:
        """Получает статистику по оценкам эмоций"""
        with self.Session() as session:
            total_ratings = session.query(func.count(EmotionRating.id)).scalar()
            correct_ratings = session.query(func.count(EmotionRating.id)).filter_by(is_correct=True).scalar()
            
            # Получаем распределение правильных эмоций
            correct_emotions = session.query(
                EmotionRating.correct_emotion,
                func.count(EmotionRating.id)
            ).filter_by(is_correct=False).group_by(EmotionRating.correct_emotion).all()

            return {
                "total_ratings": total_ratings,
                "correct_ratings": correct_ratings,
                "accuracy": correct_ratings / total_ratings if total_ratings > 0 else 0,
                "correct_emotions_distribution": dict(correct_emotions)
            }


# Usage example
if __name__ == "__main__":
    db = Database()

    # Test data
    user_id = 123456789
    db.add_user(user_id)

    # Log emotion analysis
    db.log_emotion_analysis(user_id, {"happy": 0.8, "sad": 0.1}, "Грустный текст о осени")

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
