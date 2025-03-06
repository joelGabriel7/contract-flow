from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from .core.database import engine
from .api.auth import router as auth_router
from .api.users import router as user_router
from .api.organizations import router as org_router
from .api.contract import router as contract_router
app = FastAPI(
    title="ContractFlow API",
    description="API for ContractFlow contact management system",
    version="0.0.1"
)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],  # Frontend URL (Vite default)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    create_db_and_tables()


@app.get("/api/health", tags=['Health Check'])
async def health_check():
    return {"status": "ok", "message": "ContractFlow API is running"}

app.include_router(auth_router, prefix='/api/auth', tags=['Authentication'])
app.include_router(user_router, prefix='/api/users', tags=['Users'])
app.include_router(org_router, prefix='/api/organizations', tags=['Admin Organizations'])
app.include_router(contract_router, prefix='/api/contracts', tags=['Contracts'])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
