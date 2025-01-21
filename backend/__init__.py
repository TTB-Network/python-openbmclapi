import fastapi
import uvicorn

app = fastapi.FastAPI()


def init():
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)