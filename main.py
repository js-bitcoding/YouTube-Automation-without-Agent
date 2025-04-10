import auth
from fastapi import FastAPI
from database.db_connection import init_db, engine, Base
from routes import script, thumbnail, viral_idea_finder, title_generation

Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/", tags=["Welcome"])
def startup():
    init_db()
    return {"message": "Welcome to the YouTube Automation!"}

app.include_router(auth.router, prefix="/authentication", tags=["Authentication"])

app.include_router(viral_idea_finder.router, prefix="/viral_idea_finder", tags=["Viral Idea Finder"])

app.include_router(title_generation.router, prefix="/title_generation", tags=["Title Generation"])

app.include_router(thumbnail.thumbnail_router, prefix="/thumbnails", tags=["Thumbnail Finder and Validator"])

app.include_router(script.script_router, prefix="/script", tags=["Script Generation"])
