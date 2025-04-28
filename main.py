from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db_connection import init_db, engine, Base
from routes import thumbnail, viral_idea_finder, title_generation, group, chat, project, instructions, admin, sessions, auth, collections, files, vector_store

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Welcome"])
def startup():
    init_db()
    return {"message": "Welcome to the YouTube Automation!"}

app.include_router(auth.router, prefix="/authentication", tags=["Authentication"])

app.include_router(admin.admin_router, prefix="/admin", tags=["Admin"])

app.include_router(viral_idea_finder.router, prefix="/viral_idea_finder", tags=["Viral Idea Finder"])

app.include_router(title_generation.router, prefix="/title_generation", tags=["Title Generation"])

app.include_router(thumbnail.thumbnail_router, prefix="/thumbnails", tags=["Thumbnail Finder and Validator"])


app.include_router(project.project_router, tags=["Project"])

app.include_router(group.group_router, tags=["Group"])

app.include_router(sessions.sessions_router, tags=["Sessions"])

app.include_router(chat.chat_router, tags=["AI Chat"])

app.include_router(instructions.instruction_router, tags=["Instructions"])

app.include_router(collections.collection_router, tags=["Collections"])

app.include_router(files.file_router, tags=["Files"])

app.include_router(vector_store.router, tags=["Vector Store"])
