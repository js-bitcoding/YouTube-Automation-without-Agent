import os
import re
import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from collections import defaultdict
# from langchain_chroma import Chroma
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain.schema import Document as LangchainDocument
from database.models import Group, Document, YouTubeVideo, ChatConversation, ChatHistory, User,  Instruction, timezone
from utils.logging_utils import logger
from config import OLLAMA_RESPONSE_MODEL

llm = OLLAMA_RESPONSE_MODEL
ollama_embeddings = OllamaEmbeddings(model="nomic-embed-text")
persist_dir = "./chroma_db"
os.makedirs(persist_dir, exist_ok=True)

def fetch_group_data(group_ids: list, db: Session):
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

def split_text_into_chunks(text: str) -> list:
    """
    Splits the input text into evenly sized chunks (by character count), preserving all content.

    Args:
        text (str): The full input text.
        max_chunks (int): The maximum number of chunks to return.

    Returns:
        list: A list of strings, each being a chunk of the input text.
    """
    text = text.strip()
    chunk_size = 300
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def initialize_chroma_store(group_data: dict, collection_name: str):
    try:
        
        if "group_id" not in group_data:
            logger.error("Missing 'group_id' in group_data")
            raise ValueError("Missing 'group_id' in group_data")
        
        combined_documents = [group_data["formatted"]] + group_data["documents"]
        combined_text = "\n\n".join(combined_documents)

        raw_chunks = split_text_into_chunks(combined_text)
        all_chunks = [
    LangchainDocument(page_content=chunk, metadata={"group_id": group_data["group_id"]})
    for chunk in raw_chunks
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

def get_chromadb_collection_name(group_ids, project_ids):
    if group_ids and project_ids:
        return f"project_{project_ids[0]}_group_{group_ids[0]}"
    raise HTTPException(status_code=400, detail="Invalid group/project IDs")

def fetch_group_and_project_for_conversation(conversation_id: int, db: Session):
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.is_deleted == False
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="ChatConversation not found")

    session = conversation.session
    group_ids = [g.id for g in session.groups]
    project_ids = [g.project_id for g in session.groups]

    if not group_ids or not project_ids:
        raise HTTPException(status_code=404, detail="Groups or Projects not found")

    return group_ids, project_ids

def format_chunks_for_prompt(all_chunks, group_id_map):
    grouped_contents = defaultdict(set)

    for chunk in all_chunks:
        content = chunk.page_content.strip()
        cleaned_content = re.sub(r"^Formatted content for .*?\n+", "", content, flags=re.IGNORECASE).strip()

        grouped_contents[chunk.metadata.get("group_id")].add(cleaned_content)

    formatted = []
    for group_id, contents in grouped_contents.items():
        group_label = group_id_map.get(group_id, f"Group {group_id}" if group_id else "Unknown Group")

        group_text = "\n\n".join(sorted(contents))
        formatted.append(f"Formatted content for {group_label}\n\n{group_text}")

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
        group_info = fetch_group_data(group_ids, db)
        # collection_name = get_chromadb_collection_name(group_ids, project_ids)
        # vectorstore = retrieve_vectorstore_from_chromadb(collection_name)
        # search_results = vectorstore.similarity_search(user_prompt, k=5)
        all_chunks = []

        for group_id in group_ids:
            collection_name = f"project_{project_ids[0]}_group_{group_id}"
            try:
                vectorstore = retrieve_vectorstore_from_chromadb(collection_name)
                chunks = vectorstore.similarity_search(user_prompt, k=20)

                for chunk in chunks:
                    print(f"Raw chunk content: {chunk.page_content[:200]}...")

                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning(f"Could not retrieve vectorstore for {collection_name}: {e}")

        group_id_map = {group_id: f"Group {i+1}" for i, group_id in enumerate(group_ids)}

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
            You are a highly capable and context-aware assistant helping a user with information from documents, videos, and previous conversations. Use the instructions and retrieved knowledge to respond in a helpful, clear, and tone-adaptive manner.

            ##  Primary Context (Documents & Video Transcripts):
            The following is background information from the user’s selected groups. Use it to understand the broader context, tone, and style. Incorporate relevant information, but do not repeat it verbatim unless directly relevant.
            {formatted_chunks}

            ## Tones:
            {", ".join(group_info["tones"]).capitalize() or "Neutral"}

            ## Styles:
            {", ".join(group_info["styles"]).capitalize() or "Plain"}

            ## Chat History:
            {history_prompt}

            ## Instructions:
            {instructions_info}

            ## User Prompt:
            {user_prompt}

            ## Assistant Response:
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
        raise HTTPException(status_code=500, detail=f"Server Error while generating Response: {str(e)}")
