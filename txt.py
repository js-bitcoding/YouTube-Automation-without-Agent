# async def update_group_content(
#     project_id: int = Query(...),
#     group_id: int = Query(...),
#     files: List[UploadFile] = File(None),
#     youtube_links: List[str] = Form(default=[]),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     """
#     Updates the content (documents and videos) for a group under a specified project.
    
#     Args:
#         project_id (int): ID of the project the group belongs to.
#         group_id (int): ID of the group to update.
#         files (List[UploadFile]): List of document files to be uploaded (optional).
#         youtube_links (List[str]): List of YouTube links to associate with the group (optional).
#         db (Session): SQLAlchemy DB session.
#         current_user (User): Authenticated user.
        
#     Returns:
#         dict: Contains the list of documents and videos added to the group.
        
#     Raises:
#         HTTPException: If project or group is not found, or if no valid content is provided.
#     """
#     try:
#         logger.info(f"Updating content for group {group_id} under project {project_id} by user {current_user.id}")
        
#         project = db.query(Project).filter(
#             Project.id == project_id,
#             Project.user_id == current_user.id,
#             Project.is_deleted == False
#         ).first()
#         if not project:
#             logger.error(f"Project {project_id} not found for user {current_user.id}")
#             raise HTTPException(status_code=400, detail="Project not found.")

#         group = db.query(Group).filter(
#             Group.id == group_id,
#             Group.project_id == project_id,
#             Group.is_deleted == False
#         ).first()
#         if not group:
#             logger.warning(f"Group {group_id} not found under project {project_id}")
#             raise HTTPException(status_code=404, detail="Group not found.")
        
#         # Check for files and links
#         logger.info(f"Received files: {files}")
#         logger.info(f"Received YouTube links: {youtube_links}")

#         if not files and not youtube_links:
#             logger.warning("No files or YouTube links provided in request")
#             raise HTTPException(status_code=400, detail="❌ Please provide at least one document or YouTube link.")

#         if files is None:
#             files = []  # Set files to an empty list if None is passed

#         valid_links = [link.strip() for link in youtube_links if link.strip()]
#         valid_files = [file for file in files if file.filename and file.content_type.startswith('application/')]  # Check that file has a name and is a PDF or other document type

# # Log the valid files and links
#         logger.info(f"Valid files: {valid_files}")
#         logger.info(f"Valid YouTube links: {valid_links}")

#         if not valid_files and not valid_links:
#             logger.warning("No valid documents or YouTube links provided")
#             raise HTTPException(status_code=400, detail="❌ Please provide at least one document or YouTube link.")


#         # Process the content (both files and YouTube links)
#         results = await process_group_content(
#             project_id, group_id, valid_files, valid_links, db, current_user
#         )

#         documents = [doc.content for doc in db.query(Document).filter(Document.group_id == group_id).all()]
#         you_doc = [doc.transcript for doc in db.query(YouTubeVideo).filter(YouTubeVideo.group_id == group_id).all()]
#         mixed = documents+you_doc 
#         # Initialize Chroma vector store and get collection ID
#         collection_name = f"project_{project_id}_group_{group_id}"
#         vectorstore, all_chunks, collection_id = initialize_chroma_store(mixed,collection_name)

#         # You can use the collection ID directly for RAG-based queries.
#         logger.info(f"Chroma Collection ID: {collection_id}")


#         if not results.get("documents") and not results.get("videos"):
#             logger.warning("Process returned no documents or videos")
#             raise HTTPException(status_code=400, detail="No valid documents or YouTube links provided.")

#         logger.info(f"Content updated for group {group_id}: {results}")
#         return JSONResponse(content=results)

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.exception(f"Unexpected error updating content for group {group_id} under project {project_id}: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")
 



# import sqlite3

# # Connect to the Chroma database
# conn = sqlite3.connect('./chroma_db/chroma.sqlite3')

# # Create a cursor object
# cursor = conn.cursor()

# # Execute a query to get the first 10 entries in the vectors table
# cursor.execute("SELECT * FROM vectors LIMIT 10")

# # Fetch all rows
# rows = cursor.fetchall()

# # Print the rows
# for row in rows:
#     print(row)

# # Close the connection
# conn.close()


import sqlite3

conn = sqlite3.connect('./chroma_db/chroma.sqlite3')  # Adjust path to your database if needed
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

# Check columns in any table (example for a 'vectors' table)
cursor.execute("PRAGMA table_info(vectors);")
columns = cursor.fetchall()
print("Columns in 'vectors' table:", columns)

conn.close()


