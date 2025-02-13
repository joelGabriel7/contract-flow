from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from .core.database import engine

app = FastAPI(
    title="ContractFlow API",
    description="API for ContractFlow contact management system",
    version="0.0.1"
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://locahost:5173'], # Frontend URL (Vite default)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    create_db_and_tables()


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "ContractFlow API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)