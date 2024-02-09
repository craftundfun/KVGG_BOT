import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse

from src.Helper.ReadParameters import getParameter, Parameters

logger = logging.getLogger("API")

app = FastAPI()
basepath = Path(__file__).parent.parent.parent


def run_server():
    import uvicorn

    uvicorn.run(app, host=getParameter(Parameters.HOST), port=8000)


@app.get("/backend/discord/plots/{name}")
def read_root(name: str):
    path: Path = basepath.joinpath(f"data/plots/{name}")

    if not path.exists():
        return JSONResponse(status_code=404, content={"message": f"{name} plot not found"})

    return FileResponse(path, media_type="image/png")
