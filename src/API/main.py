import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse

logger = logging.getLogger("API")

app = FastAPI()
basepath = Path(__file__).parent.parent.parent


def run_server():
    import uvicorn

    # https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-apache-in-ubuntu-22-04
    uvicorn.run(app,
                host="0.0.0.0",
                port=8000,
                ssl_certfile=basepath.joinpath("Web/selfsigned.crt"),
                ssl_keyfile=basepath.joinpath("Web/selfsigned.key").absolute().as_posix())


@app.get("/backend/discord/plots/{name}/{random}")
def get_plot(name: str, random):
    """
    Returns the given image

    :param name: Name of the picture to export
    :param random: Random number to avoid discord caching => ignore it
    """
    path: Path = basepath.joinpath(f"data/plots/{name}")

    if not path.exists():
        return JSONResponse(status_code=404, content={"message": f"{name} plot not found"})

    return FileResponse(path, media_type="image/png")


@app.get("/")
def read_root():
    return {"message": "Hello World"}
