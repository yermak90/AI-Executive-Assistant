from fastapi import APIRouter

from app.api.routes import commitments, people, projects

api_router = APIRouter()
api_router.include_router(people.router)
api_router.include_router(projects.router)
api_router.include_router(commitments.router)
