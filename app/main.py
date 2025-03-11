from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
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
    allow_origins=['http://localhost:5173', 'http://localhost:8000'],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos para el frontend (SPA)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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

# Ruta de fallback para SPA - DEBE IR DESPUÉS de todas las otras rutas
# Esta ruta captura todas las demás rutas que no son ni la raíz ni API
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa(request: Request, full_path: str):

    if full_path.startswith("api/"):
        return {"detail": "Not Found"}
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
