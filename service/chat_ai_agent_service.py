import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
# from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from database.models import Group, Document, YouTubeVideo, ChatConversation, ChatHistory, User,Instruction
from utils.logging_utils import logger
from config import OLLAMA_EMBEDDING_MODEL, OLLAMA_RESPONSE_MODEL

llm = OLLAMA_RESPONSE_MODEL

ollama_embeddings = OLLAMA_EMBEDDING_MODEL

def fetch_group_data(group_ids: list, db: Session):
    """
    Retrieves and formats group documents and video transcripts with tone/style metadata.

    Args:
        group_ids (list): List of group IDs to fetch content for.
        db (Session): SQLAlchemy DB session.

    Returns:
        dict: Contains formatted content, tones, styles, and raw documents.
    """
    formatted_sections = []
    tone_set = set()
    style_set = set()

    documents = []
    for group_id in group_ids:
        try:
            group = db.query(Group).filter(Group.id == group_id).first()
            if not group:
                logger.warning(f"Group with ID {group_id} not found.")
                continue

            section = [f"\nGroup: {group.name or 'Unnamed Group'} (ID: {group.id})"]

            docs = db.query(Document).filter(Document.group_id == group_id).all()
            logger.info(f"Found {len(docs)} documents in Group {group_id}")
            for doc in docs:
                content = doc.content.strip().replace("\n", " ")
                section.append(f"Document: {doc.filename}\n Full Content: {content}\n")
                documents.append(doc.content)

            videos = db.query(YouTubeVideo).filter(YouTubeVideo.group_id == group_id).all()
            logger.info(f"Found {len(videos)} videos in Group {group_id}")
            for video in videos:
                transcript = video.transcript.strip().replace("\n", " ")
                tone = video.tone or "Unknown"
                style = video.style or "Unknown"

                tone_set.add(tone.lower())
                style_set.add(style.lower())

                section.append(
                    f"Video: {video.url}\n Full Transcript: {transcript}\n"
                    f"Tone: {tone.capitalize()}, Style: {style.capitalize()}\n"
                )
            
            if len(section) > 1:
                formatted_sections.append("\n".join(section))
                logger.debug(f"Formatted section for group {group_id}")

        except Exception as e:
            logger.error(f"Error fetching data for group {group_id}: {str(e)}")
            continue

    return {
        "formatted": "\n\n".join(formatted_sections),
        "tones": list(tone_set),
        "styles": list(style_set),
        "documents": documents
    }

# def initialize_faiss_store(documents: list):
def initialize_chroma_store(documents: list):
    """
    Creates a FAISS vector store from chunked input documents.

    Args:
        documents (list): List of raw document strings.

    Returns:
        tuple: (vectorstore, all_chunks) used for similarity search.
    """
    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )

        all_chunks = []
        for doc in documents:
            chunks = splitter.create_documents([doc])
            all_chunks.extend(chunks)
            for i, chunk in enumerate(chunks):
                logger.info(f"Chunk {i+1}: {chunk.page_content}")

        # vectorstore = FAISS.from_documents(all_chunks, ollama_embeddings)
        vectorstore = Chroma.from_documents(
            documents=all_chunks,
            embedding=ollama_embeddings,
            persist_directory="./chroma_db"
        )
        vectorstore.persist()
        logger.info(f"Vectorstore created with {len(all_chunks)} chunks.")

        return vectorstore, all_chunks
    
    except Exception as e:
        logger.error(f"Error initializing FAISS store: {str(e)}")
        raise HTTPException(status_code=500, detail="Error initializing FAISS store")

def generate_response_from_prompt_and_data(group_data: str, user_prompt: str):
    """
    Uses LLM to generate a response based on provided group content and user prompt.

    Args:
        group_data (str): Contextual content (e.g., document or transcript).
        user_prompt (str): User's input or question.

    Returns:
        str: LLM-generated response.
    """
    try:
        prompt = f"Here is some content:\n{group_data}\n\nNow, answer the following prompt:\n{user_prompt}"
        response = llm.invoke(prompt)
        return response
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating response from LLM")


def generate_response_for_conversation(conversation_id: int, user_prompt: str, db: Session, current_user: User):
    """
    Generates an AI assistant response for a specific chat conversation based on user input,
    retrieved documents, chat history, and active instructions.

    This function fetches the relevant chat conversation and associated groups, retrieves contextual
    documents and video transcripts, and builds a full prompt including previous conversation history
    and style/tone instructions. It then invokes an LLM to generate a context-aware response.

    The assistant's response and user query are saved in the chat history.

    Args:
        conversation_id (int): The ID of the target chat conversation.
        user_prompt (str): The new user message to generate a response for.
        db (Session): SQLAlchemy database session for querying and saving data.
        current_user (User): The authenticated user initiating the request.

    Returns:
        JSONResponse: A JSON-formatted response containing the assistant's reply, chat history,
                      used styles and tones, and metadata about the conversation.

    Raises:
        HTTPException: If the chat conversation is not found, no group content is available,
                       or the LLM invocation fails.
    """
    try:
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == conversation_id,
            ChatConversation.is_deleted == False
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="ChatConversation not found")

        chat_session = conversation.session
        group_ids = [group.id for group in chat_session.groups]
        group_info = fetch_group_data(group_ids, db)
        if not group_info["formatted"]:
            raise HTTPException(status_code=404, detail="No content available for this chat")

        # vectorstore, all_chunks = initialize_faiss_store(group_info["documents"])
        vectorstore, all_chunks = initialize_chroma_store(group_info["documents"])

        max_chunks = 10
        chunked_text = "\n\n".join([chunk.page_content for chunk in all_chunks[:max_chunks]])

        history_records = db.query(ChatHistory).filter(
            ChatHistory.chat_conversation_id == conversation.id,
            ChatHistory.is_deleted == False
        ).order_by(ChatHistory.created_at.asc()).all()

        instructions = db.query(Instruction).filter(
            Instruction.is_deleted == False,
            Instruction.is_activate == True
        ).all()

        history_prompt = ""
        for record in history_records:
            history_prompt += f"User: {record.query}\n"
            history_prompt += f"Assistant: {record.response}\n"

        search_results = vectorstore.similarity_search(user_prompt, k=3)

        retrieved_data = "\n\n".join([result.page_content for result in search_results])
        instructions_info = "\n".join([f" Instruction: {instr.content}" for instr in instructions])
        logger.info("Group Info",group_info)
        logger.info("Retrieve Data",retrieved_data)

        full_prompt = f"""
            You are a highly capable and context-aware assistant helping a user with information from documents, videos, and previous conversations. Use the instructions and retrieved knowledge to respond in a helpful, clear, and tone-adaptive manner.

            ##  Active User Instructions:
            {instructions_info or "None provided."}

            ##  Primary Context (Documents & Video Transcripts):
            The following is background information from the user’s selected groups. Use it to understand the broader context, tone, and style. Incorporate relevant information, but do not repeat it verbatim unless directly relevant.

            {group_info["formatted"]}

            These are raw extracted chunks from your documents, chunked for better context understanding.
            {chunked_text}

            ##  Communication Style Guidance:
            The content involves various tones and styles:
            - Tones: {", ".join(group_info["tones"]).capitalize() or "Neutral"}
            - Styles: {", ".join(group_info["styles"]).capitalize() or "Plain"}

            Match your response tone and style to align with these.

            ##  Chat History:
            Maintain conversational continuity. Refer to prior user and assistant messages as needed.

            {history_prompt}

            ## 📩 User Prompt:
            {user_prompt}

            ## 🤖 Assistant Response:
            """

        response = llm.invoke(full_prompt)

        new_chat = ChatHistory(
            query=user_prompt.strip(),
            response=response.strip(),
            context=group_info,
            chat_conversation_id=conversation.id,
            user_id=current_user.id
        )
        db.add(new_chat)
        db.commit()

        return JSONResponse(content={
            "response": response.strip(),
            "conversation_id": conversation_id,
            "user_message": user_prompt.strip(),
            "assistant_message": response.strip(),
            "based_on_groups": group_ids,
            "tone_used": ", ".join([tone.capitalize() for tone in group_info["tones"]]) if group_info["tones"] else "",
            "style_used": ", ".join([style.capitalize() for style in group_info["styles"]]) if group_info["styles"] else "",
            "history": [
                {
                    "sender": "User",
                    "message": h.query,
                    "response": h.response,
                    "timestamp": h.created_at.isoformat()
                }
                for h in history_records if h.query
            ] + [
                {
                    "sender": "User",
                    "message": user_prompt.strip(),
                    "response": response.strip(),
                    "timestamp": datetime.datetime.utcnow().isoformat()
                }
            ]
        })
    except Exception as e:
        logger.error(f"Error in generate_response_for_conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
