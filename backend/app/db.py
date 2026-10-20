from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import settings


@lru_cache
def engine() -> Engine:
    return create_engine(
        settings().database_url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


def session() -> Iterator[Session]:
    with Session(engine()) as db:
        yield db
