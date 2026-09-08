from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes import router

app = FastAPI(title="NORA Coverage Diagnostics")
app.include_router(router)


@app.get("/")
async def serve_default_page():
    html_path = Path(__file__).resolve().parent / "Nora.html"
    return FileResponse(html_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=4021, reload=True)
