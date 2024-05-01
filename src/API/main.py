import html
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse

from src.Helper.ReadParameters import getParameter, Parameters

# from src.Manager.BackgroundServiceManager import minutelyErrorCount

logger = logging.getLogger("KVGG")
sendLog = False

app = FastAPI()
basepath = Path(__file__).parent.parent.parent


def run_server():
    import uvicorn

    logger.info("Starting API")

    # https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-apache-in-ubuntu-22-04
    uvicorn.run(app,
                host="0.0.0.0",
                port=getParameter(Parameters.API_PORT),
                ssl_certfile=basepath.joinpath("Web/selfsigned.crt"),
                ssl_keyfile=basepath.joinpath("Web/selfsigned.key").absolute().as_posix())


@app.get("/backend/discord/plots/{name}/{random}")
def get_plot(name: str, random):
    """
    Returns the given image

    :param name: Name of the picture to export
    :param random: Random number to avoid discord caching => ignore it
    """
    name = html.escape(name)
    path: Path = basepath.joinpath(f"data/plots/{name}")

    if not path.exists():
        logger.warning(f"plot at path: {path} does not exist")

        return JSONResponse(status_code=404, content={"message": f"{name} plot not found"})

    logger.debug("successfully returned plot")
    return FileResponse(path, media_type="image/png")

# @app.get("/health")
# def root():
#     """
#     Returns the status of the MinutelyUpdateService
#     """
#     global sendLog
#
#     if minutelyErrorCount > 2:
#         if not sendLog:
#             logger.error("errors of minutely job are too high, returning 503 to initiate restart")
#             sendLog = True
#
#         return JSONResponse(status_code=503, content={"message": "Service unavailable"})
#
#     return JSONResponse(status_code=200, content={"message": "Service available"})
