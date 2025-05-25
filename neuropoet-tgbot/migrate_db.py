from sqlalchemy import create_engine, text
import os
from src.database.database import Base

def migrate_database():
    # Подключаемся к базе данных
    db_path = os.path.join(os.path.dirname(__file__), "neuropoet.db")
    engine = create_engine(f"sqlite:///{db_path}")
    
    # SQL-запросы для миграции
    migrations = [
        # Добавляем колонку emotions в таблицу generations, если её нет
        """
        ALTER TABLE generations ADD COLUMN emotions JSON DEFAULT '{}';
        """,
        
        # Добавляем колонку model в таблицу generations, если её нет
        """
        ALTER TABLE generations ADD COLUMN model VARCHAR DEFAULT 'ru_gpt3';
        """,
        
        # Добавляем колонку rhyme_scheme в таблицу generations, если её нет
        """
        ALTER TABLE generations ADD COLUMN rhyme_scheme VARCHAR DEFAULT 'Неизвестно';
        """,
        
        # Добавляем колонку genre в таблицу generations, если её нет
        """
        ALTER TABLE generations ADD COLUMN genre VARCHAR DEFAULT 'произвольный';
        """,
        
        # Добавляем колонку request_text в таблицу emotion_analyses, если её нет
        """
        ALTER TABLE emotion_analyses ADD COLUMN request_text VARCHAR DEFAULT 'Текст не сохранён';
        """,
        
        # Добавляем колонку user_settings в таблицу users, если её нет
        """
        ALTER TABLE users ADD COLUMN user_settings JSON DEFAULT '{"preferred_model": "deepseek"}';
        """
    ]
    
    # Выполняем миграции
    with engine.connect() as connection:
        for migration in migrations:
            try:
                connection.execute(text(migration))
                print(f"Successfully executed: {migration.strip()}")
            except Exception as e:
                print(f"Error executing {migration.strip()}: {str(e)}")
                # Продолжаем выполнение других миграций даже если одна не удалась
                continue
        connection.commit()

def migrate():
    # Создаем движок базы данных
    engine = create_engine("sqlite:///neuropoet.db")

    # Создаем все таблицы
    Base.metadata.create_all(engine)

    # Проверяем существование таблицы emotion_ratings
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='emotion_ratings'
        """))
        if not result.fetchone():
            print("Создаем таблицу emotion_ratings...")
            conn.execute(text("""
                CREATE TABLE emotion_ratings (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    emotion_analysis_id INTEGER NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    correct_emotion VARCHAR,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (emotion_analysis_id) REFERENCES emotion_analyses (id)
                )
            """))
            conn.commit()
            print("Таблица emotion_ratings создана успешно!")
        else:
            print("Таблица emotion_ratings уже существует.")

if __name__ == "__main__":
    migrate_database()
    migrate() 