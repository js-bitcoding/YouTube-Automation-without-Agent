

import os
import re
import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from chromadb import Client
from chromadb.config import Settings
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain.schema import Document as LangchainDocument
from database.models import Group, Document, YouTubeVideo, ChatConversation, ChatHistory, User,  Instruction, timezone
from langchain.text_splitter import RecursiveCharacterTextSplitter
from utils.logging_utils import logger
from config import OLLAMA_RESPONSE_MODEL

llm = OLLAMA_RESPONSE_MODEL
ollama_embeddings = OllamaEmbeddings(model="nomic-embed-text")
persist_dir = "./chroma_db"
os.makedirs(persist_dir, exist_ok=True)

def fetch_group_data(group_ids: list, db: Session):
    """Fetch the Specific Groups from Database """
    formatted_sections, tone_set, style_set, documents = [], set(), set(), []
    
    for group_id in group_ids:
        try:
            group = db.query(Group).filter(Group.id == group_id).first()
            if not group:
                logger.warning(f"Group with ID {group_id} not found.")
                continue

            section = [f"\nGroup: {group.name or 'Unnamed Group'} (ID: {group.id})"]

            docs = db.query(Document).filter(Document.group_id == group_id).all()
            for doc in docs:
                content = doc.content.strip().replace("\n", " ")
                section.append(f"Document: {doc.filename}\n Full Content: {content}\n")
                documents.append(doc.content)

            videos = db.query(YouTubeVideo).filter(YouTubeVideo.group_id == group_id).all()
            for video in videos:
                transcript = video.transcript.strip().replace("\n", " ")
                tone = video.tone or "Unknown"
                style = video.style or "Unknown"
                tone_set.add(tone.lower())
                style_set.add(style.lower())
                section.append(f"Video: {video.url}\n Transcript: {transcript}\n Tone: {tone}, Style: {style}\n")

            if len(section) > 1:
                formatted_sections.append("\n".join(section))

        except Exception as e:
            logger.error(f"Error fetching group {group_id}: {str(e)}")
            continue

    return {
        "formatted": "\n\n".join(formatted_sections),
        "tones": list(tone_set),
        "styles": list(style_set),
        "documents": documents
    }

def split_text_with_recursive_splitter(text: str, chunk_size: int = 1000, chunk_overlap: int = 200, max_chunks: int = 10):
    """Spliting the text with chunk and overlap"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    all_chunks = splitter.split_text(text)
    
    # Truncate to a maximum number of chunks
    return all_chunks[:max_chunks]

def initialize_chroma_store(group_data: dict, collection_name: str):
    try:
        
        if "group_id" not in group_data:
            logger.error("Missing 'group_id' in group_data")
            raise ValueError("Missing 'group_id' in group_data")
        
        combined_documents = [group_data["formatted"]] + group_data["documents"]
        combined_text = "\n\n".join(combined_documents)

        # Split into max 10 chunks using equal size method
        raw_chunks = split_text_with_recursive_splitter(combined_text, max_chunks=10)
        all_chunks = [
    LangchainDocument(page_content=chunk, metadata={"group_id": group_data["group_id"],"chunk_index": idx})
    for idx, chunk in enumerate(raw_chunks)
]

        for i, chunk in enumerate(all_chunks):
            logger.info(f" Chunk {i+1}/{len(all_chunks)}: {len(chunk.page_content)} characters")
            try:
                embedding = ollama_embeddings.embed_documents([chunk.page_content])
                if embedding and embedding[0]:
                    logger.info(f" Embedded Chunk {i+1}: Vector Length = {len(embedding[0])}")
                else:
                    logger.warning(f" Empty embedding for Chunk {i+1}")
            except Exception as e:
                logger.error(f"Embedding error in Chunk {i+1}: {str(e)}")
                raise

        vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=ollama_embeddings,
        persist_directory=persist_dir,
        collection_name=collection_name
    )

        vectorstore.persist()
        logger.info(f"✅ Chroma collection '{collection_name}' created and persisted successfully with {len(all_chunks)} chunks.")
        return vectorstore, all_chunks, collection_name, embedding

    except Exception as e:
        logger.error(f"Error initializing Chroma store: {str(e)}")
        raise HTTPException(status_code=500, detail="Error initializing Chroma store")

def retrieve_vectorstore_from_chromadb(collection_name: str):
    return Chroma(
        collection_name=collection_name,
        persist_directory=persist_dir,
        embedding_function=ollama_embeddings
    )
    
# ---------------------------------------------
# 4. Utility: Get ChromaDB Collection Name
# ---------------------------------------------
def get_chromadb_collection_name(group_ids, project_ids):
    if group_ids and project_ids:
        return f"project_{project_ids[0]}_group_{group_ids[0]}"
    raise HTTPException(status_code=400, detail="Invalid group/project IDs")

def fetch_group_and_project_for_conversation(conversation_id: int, db: Session):
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.is_deleted == False
    ).first()
    print(f"[Debug] Groups linked to conversation {conversation_id}: {[g.id for g in conversation.session.groups]}")

    if not conversation:
        raise HTTPException(status_code=404, detail="ChatConversation not found")

    session = conversation.session
    group_ids = [g.id for g in session.groups]
    project_ids = [g.project_id for g in session.groups]
    print(f"[Debug] Groups linked to conversation {conversation_id}: {[g.id for g in conversation.session.groups]}")

    if not group_ids or not project_ids:
        raise HTTPException(status_code=404, detail="Groups or Projects not found")

    return group_ids, project_ids

# ---------------------------------------------
# 6. Main Response Generator Function
# ---------------------------------------------

def format_chunks_for_prompt(all_chunks, group_id_map):
    from collections import defaultdict
    import re

    grouped_contents = defaultdict(list)

    for chunk in all_chunks:
        content = chunk.page_content.strip()
        if not content:
            continue

        # Clean heading remnants if present
        cleaned_content = re.sub(r"^Formatted content for[^\n]*\n*", "", content, flags=re.IGNORECASE).strip()

        group_id = chunk.metadata.get("group_id")
        group_label = group_id_map.get(group_id, f"Group {group_id}" if group_id else "Unknown Group")

        if cleaned_content not in grouped_contents[group_id]:
            grouped_contents[group_id].append(cleaned_content)

    formatted = []
    for group_id, contents in grouped_contents.items():
        group_label = group_id_map.get(group_id, f"Group {group_id}")
        group_text = "\n\n".join(contents)
        formatted.append(f"Formatted content for {group_label}\n\n{group_text}")
        print()
    return "\n\n---\n\n".join(formatted)


def generate_response_for_conversation(conversation_id: int, user_prompt: str, db: Session, current_user: User):
    try:
        if user_prompt.lower().strip() in ['hi', 'hello', 'hey', 'how are you']:
            response = "Hello! How can I assist you today?"
            return JSONResponse(content={
                "response": response,
                "conversation_id": conversation_id,
                "user_message": user_prompt,
                "assistant_message": response,
                "history": []
            })

        group_ids, project_ids = fetch_group_and_project_for_conversation(conversation_id, db)
        print(f"[Debug] Group IDs retrieved: {group_ids}")
        for idx, g_id in enumerate(group_ids):
            print(f"[Debug] Group {idx+1} ID: {g_id}, Collection Name: project_{project_ids[0]}_group_{g_id}")

        group_info = fetch_group_data(group_ids, db)
        # collection_name = get_chromadb_collection_name(group_ids, project_ids)
        # vectorstore = retrieve_vectorstore_from_chromadb(collection_name)
        # search_results = vectorstore.similarity_search(user_prompt, k=5)
        all_chunks = []
        
       

        client = Client(Settings(persist_directory=persist_dir))
        collections = client.list_collections()
        print(f"[Debug] Existing ChromaDB collections: {[c.name for c in collections]}")

        for group_id in group_ids:
            collection_name = f"project_{project_ids[0]}_group_{group_id}"
            try:
                vectorstore = retrieve_vectorstore_from_chromadb(collection_name)
                chunks = vectorstore.similarity_search(user_prompt, k=20)
                chunks = sorted(chunks, key=lambda c: c.metadata.get("chunk_index", 0))
                if chunks:
                    print(f"[Debug] Retrieved {len(chunks)} chunks from {collection_name}")
                    
                else:
                    print(f"[Debug] No chunks found for {collection_name}")

        # Log chunks before formatting
                for chunk in chunks:
                    print(f"Raw chunk content: {chunk.page_content[:200]}...")  # Debugging first 200 characters
                    print(f"Chunk Index: {chunk.metadata.get('chunk_index')}, Length: {len(chunk.page_content)}")

                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"[Error] Failed to retrieve vectorstore for {collection_name}: {e}")


        group_id_map = {group_id: f"Group {i+1}" for i, group_id in enumerate(group_ids)}
        import re

# Extract any referenced group number in the user prompt
        match = re.search(r"\bgroup\s*(\d+)\b", user_prompt, re.IGNORECASE)
        requested_group = int(match.group(1)) if match else None

# Get valid group numbers based on group_id_map
        valid_group_numbers = list(range(1, len(group_id_map) + 1))

# Create warning note if user references a group not in the list
        group_reference_note = ""
        if requested_group and requested_group not in valid_group_numbers:
            group_reference_note = (
        f"\n\n⚠️ NOTE: You referenced Group {requested_group}, "
        f"but only Groups {valid_group_numbers} are available. "
        f"The assistant will ignore that reference unless it’s linked."
        )

        formatted_chunks = format_chunks_for_prompt(all_chunks,group_id_map)
        history_records = db.query(ChatHistory).filter(
            ChatHistory.chat_conversation_id == conversation_id,
            ChatHistory.is_deleted == False
        ).order_by(ChatHistory.created_at.asc()).all()

        history_prompt = "\n".join([f"User: {h.query}\nAssistant: {h.response}" for h in history_records])

        instructions = db.query(Instruction).filter(Instruction.is_deleted == False, Instruction.is_activate == True).all()
        instructions_info = "\n".join([f"Instruction: {instr.content}" for instr in instructions])
        print("Formated Chunks",formatted_chunks)

        system_prompt = f"""
You are a YouTube automation assistant helping creators repurpose and remix content from PDFs and videos into engaging scripts, captions, or short-form ideas. 

## OBJECTIVE:
Based on the user's query, select the most relevant content group (e.g. video script templates, business PDFs, or content breakdowns). Your job is to generate a clear, engaging, and audience-tailored script or content piece that feels original and useful — not copied.

## USER QUERY:
{user_prompt}

## CONTENT SOURCES (PDFs, Video Transcripts, or Documents):
## IMPORTANT: If the user query references a specific group (e.g. "Group 2"), use only that group's content — ignore all others, even if present.
{group_reference_note}

The following is background information from the user’s list of groups based on the query above. Use it to understand the broader context:
{formatted_chunks}

## GROUP TONE(S):
{", ".join(group_info["tones"]) or "Neutral"}

## GROUP STYLE(S):
{", ".join(group_info["styles"]) or "Plain"}

## CHAT HISTORY:
{history_prompt}

## INSTRUCTIONS:
{instructions_info}

---

## OUTPUT RULES:
- Focus only on relevant source groups based on the user’s request.
- Rewrite key concepts using a fresh tone, hook, or format.
- If asked for a video script, structure output as:
  [HOOK] → [VALUE] → [EXAMPLES/PROOF] → [CTA]
- Avoid repeating content verbatim unless explicitly requested.
- You can draw from both documents and video transcripts but remix them creatively.

---

## FINAL OUTPUT:
"""

        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

        new_chat = ChatHistory(
            query=user_prompt.strip(),
            response=response.strip(),
            context=group_info,
            chat_conversation_id=conversation_id,
            user_id=current_user.id
        )
        db.add(new_chat)
        db.commit()

        history_ui = [
            {
                "sender": "User",
                "message": h.query,
                "response": h.response,
                "timestamp": h.created_at.isoformat()
            }
            for h in history_records if h.query
        ] + [{
            "sender": "User",
            "message": user_prompt.strip(),
            "response": response.strip(),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }]

        return JSONResponse(content={
            "response": response.strip(),
            "conversation_id": conversation_id,
            "user_message": user_prompt,
            "assistant_message": response.strip(),
            "based_on_groups": group_ids,
            "tone_used": ", ".join([t.capitalize() for t in group_info["tones"]]),
            "style_used": ", ".join([s.capitalize() for s in group_info["styles"]]),
            "history": history_ui
        })

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
    except Exception as e:
        logger.error(f"[Error] Failed to retrieve vectorstore for {collection_name}: {e}")
        logger.warning(f"[Warning] Skipping group {group_id}. Possibly missing ChromaDB or no data.")





