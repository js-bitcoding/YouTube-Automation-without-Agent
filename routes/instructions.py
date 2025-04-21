from typing import List
from sqlalchemy.orm import Session
from database.models import Instruction
from database.db_connection import get_db
from fastapi import APIRouter, Depends, HTTPException
from functionality.current_user import get_current_user
from database.schemas import InstructionCreate, InstructionOut, InstructionUpdate

instruction_router = APIRouter(prefix="/instruction")

@instruction_router.post("/create-instruction/", response_model=InstructionOut)
def create_instruction(instruction: InstructionCreate, db: Session = Depends(get_db)):
    new_instruction = Instruction(**instruction.dict())
    db.add(new_instruction)
    db.commit()
    db.refresh(new_instruction)
    return new_instruction

@instruction_router.put("/update-instruction-{instruction_id}/", response_model=InstructionOut)
def update_instruction(instruction_id: int, update_data: InstructionUpdate, db: Session = Depends(get_db)):
    instruction = db.query(Instruction).filter(Instruction.id == instruction_id, Instruction.is_deleted == False).first()
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")

    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(instruction, key, value)

    db.commit()
    db.refresh(instruction)
    return instruction

@instruction_router.delete("/delete-instruction-{instruction_id}/")
def delete_instruction(instruction_id: int, db: Session = Depends(get_db)):
    instruction = db.query(Instruction).filter(Instruction.id == instruction_id).first()
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")

    instruction.is_deleted = True
    db.commit()
    return {"detail": "Instruction marked as deleted"}

@instruction_router.get("/get-all-instructions/", response_model=List[InstructionOut])
def get_all_instructions(db: Session = Depends(get_db)):
    instructions = db.query(Instruction).filter(Instruction.is_deleted == False).all()
    return instructions
    