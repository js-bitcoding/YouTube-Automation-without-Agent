from typing import List
from sqlalchemy.orm import Session
from database.models import Instruction,User
from database.db_connection import get_db
from fastapi import APIRouter, Depends, HTTPException
from functionality.current_user import get_current_user
from database.schemas import InstructionCreate, InstructionOut, InstructionUpdate

instruction_router = APIRouter(prefix="/instruction")

@instruction_router.post("/create-instruction/", response_model=InstructionOut)
def create_instruction(
    instruction: InstructionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # If is_activate is not provided, it will be set to the default value of True
    new_instruction = Instruction(**instruction.dict(), user_id=user.id)
    db.add(new_instruction)
    db.commit()
    db.refresh(new_instruction)

    return new_instruction  # This will return the instruction with all fields, including is_activate


@instruction_router.put("/update-instruction-{instruction_id}/", response_model=InstructionOut)
def update_instruction(
    instruction_id: int,
    update_data: InstructionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Fetch the instruction to update
    instruction = db.query(Instruction).filter(Instruction.id == instruction_id, Instruction.is_deleted == False).first()

    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")

    # Check if the current user is the one who created the instruction
    if instruction.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only update your own instructions")

    # Ensure the user cannot modify their own user_id (this ensures no one can impersonate another user)
    if "user_id" in update_data.dict():
        raise HTTPException(status_code=400, detail="Cannot update user_id directly")

    # Update the instruction fields
    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(instruction, key, value)

    # Commit the changes, which automatically updates the updated_at field
    db.commit()
    db.refresh(instruction)
    return instruction


@instruction_router.delete("/delete-instruction-{instruction_id}/")
def delete_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    instruction = db.query(Instruction).filter(Instruction.id == instruction_id).first()

    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")

    # Check if the current user is the one who created the instruction
    if instruction.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own instructions")

    # Mark the instruction as deleted
    instruction.is_deleted = True
    db.commit()

    return {"detail": "Instruction marked as deleted"}

@instruction_router.get("/get-my-instructions/", response_model=List[InstructionOut])
def get_my_instructions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Retrieve instructions created by the current user
    instructions = db.query(Instruction).filter(Instruction.user_id == user.id, Instruction.is_deleted == False).all()
    
    if not instructions:
        raise HTTPException(status_code=404, detail="No instructions found for this user")

    return instructions

@instruction_router.put("/activate-instruction-{instruction_id}/", response_model=InstructionOut)
def activate_instruction(
    instruction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Fetch the instruction to activate
    instruction = db.query(Instruction).filter(Instruction.id == instruction_id, Instruction.is_deleted == False).first()

    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")

    # Check if the current user is the one who created the instruction
    if instruction.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only activate your own instructions")

    # Set the instruction's activation status to True
    instruction.is_activate = True
    db.commit()
    db.refresh(instruction)

    return instruction


