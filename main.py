import auth
from fastapi import FastAPI
from routes import script, thumbnail
from database.db_connection import init_db, engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/", tags=["Welcome"])
def startup():
    init_db()
    return {"message": "Welcome to the YouTube Automation!"}

app.include_router(auth.router, prefix="/authentication", tags=["Authentication"])

app.include_router(thumbnail.thumbnail_router, prefix="/thumbnails", tags=["Thumbnail Finder and Validator"])

app.include_router(script.script_router, prefix="/script", tags=["Script Generation"])
