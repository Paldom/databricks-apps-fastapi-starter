from .models import Todo
from .schemas import TodoRead


def to_dto(entity: Todo) -> TodoRead:
    return TodoRead.model_validate(entity, from_attributes=True)
