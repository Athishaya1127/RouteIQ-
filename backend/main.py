import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Base, engine
from backend.models.schemas import OptimizeRequest
from backend.services.optimization_workflow import optimize_deliveries
from backend.services.simulation import run_simulation
from backend.services.websocket import manager


Base.metadata.create_all(bind=engine)

app = FastAPI(title="RouteIQ AI Route Optimization API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_simulation())


@app.post("/optimize-route")
async def optimize_route(request: OptimizeRequest):
    return await optimize_deliveries(request)


@app.get("/route-summary")
async def get_route_summary():
    return {"message": "No optimization runs yet."}


@app.get("/")
async def root():
    return {"message": "RouteIQ API is running."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
