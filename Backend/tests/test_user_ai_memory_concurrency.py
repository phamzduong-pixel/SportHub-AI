from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.user import User
from app.models.user_ai_memory import UserAIMemory
from app.services.user_ai_memory_service import UserAIMemoryService


def test_concurrent_memory_upserts_keep_unique_rows_and_valid_values(tmp_path):
    database_path = (tmp_path / 'memory-concurrency.sqlite3').as_posix()
    engine = create_engine(
        f'sqlite:///{database_path}',
        connect_args={'check_same_thread': False, 'timeout': 30},
    )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    try:
        with session_factory() as db:
            user = User(
                full_name='Concurrent Memory User', email='concurrent-memory@test.local',
                hashed_password='unused', role='CUSTOMER',
            )
            db.add(user)
            db.commit()
            user_id = user.id

        barrier = Barrier(8)

        def write_same_preference(_index: int):
            barrier.wait(timeout=10)
            with session_factory() as db:
                return UserAIMemoryService.remember_explicit_statement(
                    db, user_id=user_id, message='Tôi thích Messi.',
                )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(write_same_preference, range(8)))
        assert all(result is not None for result in results)

        with session_factory() as db:
            athletes = list(db.scalars(select(UserAIMemory).where(
                UserAIMemory.user_id == user_id,
                UserAIMemory.memory_type == 'favorite_athlete',
            )).all())
            assert len(athletes) == 1
            assert athletes[0].value == 'Messi'

        update_barrier = Barrier(8)
        style_messages = [
            'Từ giờ hãy trả lời ngắn gọn.' if index % 2 == 0 else 'Từ giờ hãy trả lời chi tiết.'
            for index in range(8)
        ]

        def update_style(message: str):
            update_barrier.wait(timeout=10)
            with session_factory() as db:
                return UserAIMemoryService.remember_explicit_statement(
                    db, user_id=user_id, message=message,
                )

        with ThreadPoolExecutor(max_workers=8) as executor:
            style_results = list(executor.map(update_style, style_messages))
        assert all(result is not None for result in style_results)

        with session_factory() as db:
            styles = list(db.scalars(select(UserAIMemory).where(
                UserAIMemory.user_id == user_id,
                UserAIMemory.memory_type == 'response_style',
            )).all())
            assert len(styles) == 1
            assert styles[0].value in {'concise', 'detailed'}
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
