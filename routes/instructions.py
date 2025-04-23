from typing import List
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from database.models import Instruction,User
from database.db_connection import get_db
from functionality.current_user import admin_only
from database.schemas import InstructionCreate, InstructionOut, InstructionUpdate
from utils.logging_utils import logger

instruction_router = APIRouter(prefix="/instruction")

@instruction_router.post("/create", response_model=InstructionOut)
def create_instruction(
    instruction: InstructionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    existing_instruction = db.query(Instruction).filter(Instruction.name == instruction.name).first()
    if existing_instruction:
        logger.warning(f"Create failed: Instruction with name '{instruction.name}' already exists.")
        raise HTTPException(status_code=400, detail=f"Instruction with name '{instruction.name}' already exists.")
    
    new_instruction = Instruction(**instruction.dict(), user_id=user.id)
    db.add(new_instruction)
    db.commit()
    db.refresh(new_instruction)

    logger.info(f"Instruction created by user {user.id}: {new_instruction.name}")
    return new_instruction

@instruction_router.put("/update-{instruction_id}", response_model=InstructionOut)
def update_instruction(
    instruction_id: int,
    update_data: InstructionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
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
    return instruction

@instruction_router.delete("/delete-instruction-{instruction_id}/")
def delete_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    instruction = db.query(Instruction).filter(Instruction.id == instruction_id).first()

    if not instruction:
        logger.warning(f"Delete failed: Instruction {instruction_id} not found.")
        raise HTTPException(status_code=404, detail="Instruction not found or already deleted")

    if instruction.user_id != user.id:
        logger.warning(f"Unauthorized delete attempt by user {user.id} on instruction {instruction_id}")
        raise HTTPException(status_code=403, detail="You can only delete your own instructions")

    instruction.is_deleted = True
    db.commit()
    logger.info(f"Instruction {instruction_id} marked as deleted by user {user.id}")
    return {"detail": "Instruction deleted"}

@instruction_router.get("/get-my-instructions/", response_model=List[InstructionOut])
def get_my_instructions(
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
    instructions = db.query(Instruction).filter(
        Instruction.user_id == user.id, 
        Instruction.is_deleted == False
        ).all()
    
    if not instructions:
        logger.info(f"No instructions found for user {user.id}")
        raise HTTPException(status_code=404, detail="No instructions found for this user")

    logger.info(f"Instructions retrieved for user {user.id}")
    return instructions

@instruction_router.get("/get-my-instructions/{instruction_id}", response_model=InstructionOut)
def get_instruction_by_id(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
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

@instruction_router.put("/activate-instruction-{instruction_id}/", response_model=InstructionOut)
def activate_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(admin_only)
):
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
