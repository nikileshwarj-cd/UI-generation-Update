"""
main.py
FastAPI Application Entry Point for the UI-to-Code Generator Platform.
Replaces the old Flask app_ui.py.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routes.api_routes import router as project_router

# Load environment configuration (.env)
load_dotenv()

# Initialize FastAPI application
app = FastAPI(
    title="UI-to-Code Generator API",
    description="Scalable FastAPI backend replacing Flask.",
    version="2.0.0"
)

# Enable CORS for React frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register project routes
app.include_router(project_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
