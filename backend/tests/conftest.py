import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.main import app as fastapi_app
from app.models.enums import UserRole
from app.models.user import User
import app.models  # ensure all models are registered

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    # Disable rate limiting by default so standard functional tests don't get throttled
    original_enabled = limiter.enabled
    limiter.enabled = False

    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with TestClient(fastapi_app) as test_client:
        yield test_client

    fastapi_app.dependency_overrides.clear()
    limiter.enabled = original_enabled


@pytest.fixture
def seed_users(db_session: Session):
    password_hash = hash_password("Secret123!")

    users = {
        "admin": User(
            name="System Admin",
            email="admin@college.edu",
            password_hash=password_hash,
            role=UserRole.ADMIN,
            is_active=True,
        ),
        "coordinator": User(
            name="Block Coordinator",
            email="coordinator@college.edu",
            password_hash=password_hash,
            role=UserRole.COORDINATOR,
            is_active=True,
        ),
        "faculty": User(
            name="Faculty Member",
            email="faculty@college.edu",
            password_hash=password_hash,
            role=UserRole.FACULTY,
            is_active=True,
        ),
        "hod": User(
            name="Department Head",
            email="hod@college.edu",
            password_hash=password_hash,
            role=UserRole.HOD,
            is_active=True,
        ),
        "inactive": User(
            name="Inactive Faculty",
            email="inactive@college.edu",
            password_hash=password_hash,
            role=UserRole.FACULTY,
            is_active=False,
        ),
    }

    for user in users.values():
        db_session.add(user)
    db_session.commit()
    for user in users.values():
        db_session.refresh(user)

    return users
