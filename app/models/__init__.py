"""Model registry — import all ORM models so ``Base.metadata`` discovers them."""

from app.models.chat_session_model import ChatSession  # noqa: F401
from app.models.file_record_model import FileRecord  # noqa: F401
from app.models.message_model import Message  # noqa: F401
from app.models.project_model import Project  # noqa: F401
from app.models.user_model import AppUser  # noqa: F401
from app.models.user_settings_model import UserSettings  # noqa: F401
