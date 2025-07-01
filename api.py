from fastapi import APIRouter

from controllers import demo, user, todo

api_router = APIRouter()

routers_to_include = [
    (demo.router, "", ["Demo"]),
    (user.router, "", ["User"]),
    (todo.router, "", ["Todo"]),
]

for router_instance, prefix_path, tags_list in routers_to_include:
    api_router.include_router(
        router_instance,
        prefix=prefix_path,
        tags=tags_list,
    )

