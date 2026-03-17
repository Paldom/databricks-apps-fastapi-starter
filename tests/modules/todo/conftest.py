import pytest
from unittest.mock import AsyncMock, MagicMock

import app.main as app_main
from app.services.todo_service import TodoService
from app.core.deps import get_todo_service
from app.repositories.todo_repository import TodoRepository
from app.models.user_dto import CurrentUser


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=TodoRepository)
    repo.list = AsyncMock()
    repo.get = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_user():
    return CurrentUser(id="user123", email="test@example.com")


@pytest.fixture
def mock_todo_service(mock_repo, mock_user):
    service = TodoService(mock_repo, mock_user, MagicMock())
    app_main.app.dependency_overrides[get_todo_service] = lambda: service
    yield service
    app_main.app.dependency_overrides.clear()
