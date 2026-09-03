from fastapi import APIRouter

from app.api.routes import checkpoints, commitments, people, projects, voice_captures

api_router = APIRouter()
api_router.include_router(people.router)
api_router.include_router(projects.router)
api_router.include_router(commitments.router)
api_router.include_router(checkpoints.router)
api_router.include_router(voice_captures.router)
