import auth
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db_connection import init_db, engine, Base
from routes import script, thumbnail, viral_idea_finder, title_generation, group, knowledge, chat, project

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Welcome"])
def startup():
    init_db()
    return {"message": "Welcome to the YouTube Automation!"}

app.include_router(auth.router, prefix="/authentication", tags=["Authentication"])

app.include_router(viral_idea_finder.router, prefix="/viral_idea_finder", tags=["Viral Idea Finder"])

app.include_router(title_generation.router, prefix="/title_generation", tags=["Title Generation"])

app.include_router(thumbnail.thumbnail_router, prefix="/thumbnails", tags=["Thumbnail Finder and Validator"])

app.include_router(script.script_router, prefix="/script", tags=["Script Generation"])


app.include_router(project.project_router, tags=["Project"])

app.include_router(group.group_router, tags=["Group"])

app.include_router(knowledge.knowledge_router, tags=["Knowledge"])

app.include_router(chat.chat_router, tags=["AI Chat"])
