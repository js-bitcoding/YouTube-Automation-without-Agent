from typing import List
from sqlalchemy.orm import Session
from utils.logging_utils import logger
from database.db_connection import get_db
from fastapi.responses import JSONResponse
from database.models import Instruction,User
from functionality.current_user import admin_only
from fastapi import APIRouter, Depends, HTTPException
from database.schemas import InstructionBase, InstructionOut, InstructionUpdate

instruction_router = APIRouter(prefix="/instruction")

@instruction_router.post("/create/", response_model=InstructionOut)
def create_instruction(
     instruction: InstructionBase = Depends(InstructionBase.as_form),
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    """
    Creates a new instruction, ensuring no duplicate names exist.

    Args:
        instruction (InstructionCreate): The instruction details to create.
        db (Session): SQLAlchemy DB session.
        user (User): Admin user creating the instruction.

    Returns:
        InstructionOut: The newly created instruction.

    Raises:
        HTTPException: If an instruction with the same name already exists.
    """
    try:
        if instruction.name.strip().lower() == "string" or not instruction.name.strip():
            raise HTTPException(status_code=400, detail="Instruction Name cannot be empty.")
            
        if instruction.content.strip().lower() == "string" or not instruction.content.strip():
            raise HTTPException(status_code=400, detail="Instruction Content cannot be empty.")
        
        existing_instruction = db.query(Instruction).filter(Instruction.name == instruction.name).first()
        if existing_instruction:
            logger.warning(f"Create failed: Instruction with name '{instruction.name}' already exists.")
            raise HTTPException(status_code=400, detail=f"Instruction with name '{instruction.name}' already exists.")

        new_instruction = Instruction(**instruction.dict(), user_id=user.id)
        db.add(new_instruction)
        db.commit()
        db.refresh(new_instruction)

        logger.info(f"Instruction created by user {user.id}: {new_instruction.name}")
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "Instruction created successfully.",
                "instruction": {
                    "id": new_instruction.id,
                    "name": new_instruction.name,
                    "content": new_instruction.content,
                    "is_activate": new_instruction.is_activate,
                    "created_at": new_instruction.created_at.isoformat(),
                    "updated_at": new_instruction.updated_at.isoformat(),
                }
            }
        )

    except HTTPException as e:
        logger.error(f"Error: {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})

@instruction_router.put("/update/{instruction_id}/", response_model=InstructionOut)
def update_instruction(
    instruction_id: int,
    update_data: InstructionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    """
    Updates an existing instruction, ensuring that only the owner can modify it and the 'user_id' field cannot be updated.

    Args:
        instruction_id (int): The ID of the instruction to update.
        update_data (InstructionUpdate): The updated instruction data.
        db (Session): SQLAlchemy DB session.
        user (User): Admin user performing the update.

    Returns:
        InstructionOut: The updated instruction.

    Raises:
        HTTPException:
            - If the instruction is not found.
            - If the user is unauthorized to update the instruction.
            - If attempting to update the 'user_id' field directly.
    """
    try:
        instruction = db.query(Instruction).filter(
            Instruction.id == instruction_id, 
            Instruction.is_deleted == False
        ).first()

        if not instruction:
            logger.warning(f"Update failed: Instruction {instruction_id} not found.")
            raise HTTPException(status_code=404, detail="Instruction not found")

        if instruction.user_id != user.id:
            logger.warning(f"Unauthorized update attempt by user {user.id} on instruction {instruction_id}")
            raise HTTPException(status_code=403, detail="You can only update your own instructions")

        if "user_id" in update_data.dict():
            logger.error("User attempted to modify user_id field.")
            raise HTTPException(status_code=400, detail="Cannot update user_id directly")

        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(instruction, key, value)

        db.commit()
        db.refresh(instruction)

        logger.info(f"Instruction {instruction_id} updated by user {user.id}")

        return JSONResponse(
            status_code=200,
            content={
                "message": "Instruction updated successfully.",
                "instruction": {
                    "id": instruction.id,
                    "name": instruction.name,
                    "content": instruction.content,
                    "is_activate": instruction.is_activate,
                    "created_at": instruction.created_at.isoformat(),
                    "updated_at": instruction.updated_at.isoformat(),
                }
            }
        )

    except HTTPException as e:
        logger.error(f"Error: {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred while Updating instruction "})



@instruction_router.delete("/delete/{instruction_id}/")
def delete_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    """
    Marks an instruction as deleted, ensuring that only the owner can delete it.

    Args:
        instruction_id (int): The ID of the instruction to delete.
        db (Session): SQLAlchemy DB session.
        user (User): Admin user performing the deletion.

    Returns:
        dict: A confirmation message indicating the instruction has been deleted.

    Raises:
        HTTPException:
            - If the instruction is not found.
            - If the user is unauthorized to delete the instruction.
    """
    try:
        instruction = db.query(Instruction).filter(Instruction.id == instruction_id).first()

        if not instruction:
            logger.warning(f"Delete failed: Instruction {instruction_id} not found.")
            raise HTTPException(status_code=404, detail="Instruction not found")

        if instruction.user_id != user.id:
            logger.warning(f"Unauthorized delete attempt by user {user.id} on instruction {instruction_id}")
            raise HTTPException(status_code=403, detail="You can only delete your own instructions")

        instruction.is_deleted = True
        db.commit()

        logger.info(f"Instruction {instruction_id} marked as deleted by user {user.id}")
        return JSONResponse(status_code=200, content={"message": "Instruction deleted successfully."})

    except HTTPException as e:
        logger.error(f"Error: {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})

@instruction_router.get("/get/", response_model=List[InstructionOut])
def get_my_instructions(
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    """
    Retrieves all instructions created by the authenticated user that are not marked as deleted.

    Args:
        db (Session): SQLAlchemy DB session.
        user (User): Admin user making the request.

    Returns:
        List[InstructionOut]: A list of instructions for the authenticated user.

    Raises:
        HTTPException:
            - If no instructions are found for the user.
    """
    try:
        instructions = db.query(Instruction).filter(
            Instruction.user_id == user.id, 
            Instruction.is_deleted == False
        ).all()

        if not instructions:
            logger.info(f"No instructions found for user {user.id}")
            raise HTTPException(status_code=404, detail="No instructions found for this user")

        logger.info(f"Instructions retrieved for user {user.id}")
        return instructions

    except HTTPException as e:
        logger.error(f"Error: {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred while get the instruction"})

@instruction_router.get("/get/{instruction_id}/", response_model=InstructionOut)
def get_instruction_by_id(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    """
    Retrieves a specific instruction created by the authenticated user based on the instruction ID.

    Args:
        instruction_id (int): The ID of the instruction to retrieve.
        db (Session): SQLAlchemy DB session.
        user (User): Admin user making the request.

    Returns:
        InstructionOut: The instruction details for the given ID if found and owned by the user.

    Raises:
        HTTPException:
            - If the instruction with the specified ID is not found or not owned by the user.
    """
    try:
        instruction = db.query(Instruction).filter(
            Instruction.id == instruction_id,
            Instruction.user_id == user.id,
            Instruction.is_deleted == False
        ).first()

        if not instruction:
            logger.info(f"Instruction with ID {instruction_id} not found for user {user.id}")
            raise HTTPException(status_code=404, detail="Instruction not found for this user")

        logger.info(f"Instruction with ID {instruction_id} retrieved for user {user.id}")
        return instruction

    except HTTPException as e:
        logger.error(f"Error: {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred while get the instruction"})

@instruction_router.put("/activate/{instruction_id}/", response_model=InstructionOut)
def activate_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    """
    Activates a specific instruction for the authenticated user. If another instruction is already active, it is deactivated.

    Args:
        instruction_id (int): The ID of the instruction to activate.
        db (Session): SQLAlchemy DB session.
        user (User): Admin user making the request.

    Returns:
        JSONResponse: A message indicating the activation status, along with details of the deactivated instruction(s) and the newly activated instruction.

    Raises:
        HTTPException:
            - If the instruction with the specified ID is not found.
            - If the instruction is not owned by the user.
    """
    try:
        instruction = db.query(Instruction).filter(
            Instruction.id == instruction_id, 
            Instruction.is_deleted == False
        ).first()

        if not instruction:
            logger.warning(f"Activation failed: Instruction {instruction_id} not found.")
            raise HTTPException(status_code=404, detail="Instruction not found")

        if instruction.user_id != user.id:
            logger.warning(f"Unauthorized activation attempt by user {user.id} on instruction {instruction_id}")
            raise HTTPException(status_code=403, detail="You can only activate your own instructions")

        previously_active_instructions = db.query(Instruction).filter(
            Instruction.user_id == user.id,
            Instruction.is_activate == True,
            Instruction.id != instruction_id
        ).all()

        deactivated_names = [i.name for i in previously_active_instructions]

        for inst in previously_active_instructions:
            inst.is_activate = False

        instruction.is_activate = True
        db.commit()
        db.refresh(instruction)

        logger.info(f"Instruction {instruction_id} activated by user {user.id}. Deactivated: {deactivated_names}")
        
        return JSONResponse(content={
            "message": f"Instruction '{instruction.name}' is now activated.",
            "deactivated_instructions": deactivated_names,
            "active_instruction": {
                "id": instruction.id,
                "name": instruction.name,
                "content": instruction.content,
                "is_activate": instruction.is_activate,
                "created_at": str(instruction.created_at),
                "updated_at": str(instruction.updated_at),
            }
        })

    except HTTPException as e:
        logger.error(f"Error: {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred while activate instruction"})