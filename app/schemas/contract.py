# app/schemas/contract.py
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, EmailStr, field_validator, Field
from uuid import UUID
from app.models.contract import ContractStatus, ContractTemplateType, ContractPartyType

# Base schemas
class ContractPartyBase(BaseModel):
    """Base schema for contract party data validation"""
    party_type: ContractPartyType
    user_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    external_name: Optional[str] = None
    external_email: Optional[EmailStr] = None
    signature_required: bool = True
    
    # [CHALLENGE 6] Add validators for ContractPartyBase
    # Requirements:
    
    # - Add validator to ensure external_email is provided when party is external
    @field_validator('external_email')
    def validate_external_email(cls, v, info):
       """Ensure external_email is provided when party is external"""
       party_type = info.data.get('party_type') if hasattr(info, 'data') else None
       user_id = info.data.get('user_id') if hasattr(info, 'data') else None
       if party_type in [ContractPartyType.INDIVIDUAL, ContractPartyType.REPRESENTATIVE] and not user_id and not v:
           raise ValueError('External email is required for external parties')
       return v
    
    # - Add validator to ensure external_name is provided when party is external
    
    @field_validator('external_name')
    def validate_external_name(cls, v, info):
        """Ensure external_name is provided when party is external"""
        party_type = info.data.get('party_type') if hasattr(info, 'data') else None
        user_id = info.data.get('user_id') if hasattr(info, 'data') else None
        if party_type in [ContractPartyType.INDIVIDUAL, ContractPartyType.REPRESENTATIVE] and not user_id and not v:
            raise ValueError('External name is required for external parties')
        return v
    
    # - Add validator to ensure organization_id is provided for ORGANIZATION and REPRESENTATIVE types
    @field_validator('organization_id')
    def validate_organization_id(cls, v, info):
        """Ensure organization_id is provided for ORGANIZATION and REPRESENTATIVE types"""
        party_type = info.data.get('party_type') if hasattr(info, 'data') else None
        if party_type in [ContractPartyType.ORGANIZATION, ContractPartyType.REPRESENTATIVE] and not v:
            raise ValueError('Organization ID is required for organization and representative parties')
        return v
    
class ContractBase(BaseModel):
    """Base schema for contract data validation"""
    title: str
    description: Optional[str] = None
    template_type: ContractTemplateType
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    organization_id: Optional[UUID] = None
    
    # [CHALLENGE 7] Add date validator
    # Requirements:
    # - Add validator to ensure expiration_date is after effective_date when both are provided
    @field_validator('expiration_date')
    def validate_expiration_date(cls, v, info):
        """Ensure expiration_date is after effective_date when both are provided"""
        effective_date = info.data.get('effective_date') if hasattr(info, 'data') else None
        if effective_date and v and v <= effective_date:
            raise ValueError('Expiration date must be after effective date')
        return v


class ContractContentBase(BaseModel):
    """Schema for contract content validation"""
    content: Dict[str, Any]  # JSON structure of the contract content
    change_summary: Optional[str] = None

class ContractVersionCreate(ContractContentBase):
    """Schema for creating a new contract version"""
    pass

class ContractPartyCreate(ContractPartyBase):
    """Schema for creating a new contract party"""
    pass

class ContractCreate(ContractBase):
    """Schema for creating a new contract"""
    # [CHALLENGE 8] Complete ContractCreate schema
    # Requirements:
    # - Add parties list field of type List[ContractPartyCreate]
    parties: List[ContractPartyCreate]
    # - Add content field for initial contract content
    content: Dict[str, Any]
# Update schemas
class ContractPartyUpdate(BaseModel):
    """Schema for updating a contract party"""
    # [CHALLENGE 9] Complete ContractPartyUpdate schema
    # Requirements:
    # - Add optional fields that can be updated (signature_required, external fields)
    # - All fields should be Optional
    signature_required: Optional[bool] = None
    external_name: Optional[str] = None
    external_email: Optional[EmailStr] = None
 
class ContractUpdate(BaseModel):
    """Schema for updating a contract"""
    # [CHALLENGE 10] Complete ContractUpdate schema
    # Requirements:
    # - Add optional fields that can be updated (title, description, dates, status)
    # - All fields should be Optional
    title: Optional[str] = None
    description: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    status: Optional[ContractStatus] = None

class ContractPartyRead(ContractPartyBase):
    """Schema for reading a contract party"""
    id: UUID
    contract_id: UUID
    signature_date: Optional[datetime] = None
    
    # [CHALLENGE 11] Add simplified user and organization info
    # Requirements:
    # - Add optional user field as Dict[str, Any]
    # - Add optional organization field as Dict[str, Any]
    user: Optional[Dict[str, Any]] = None
    organization: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class ContractVersionRead(BaseModel):
    """Schema for reading a contract version"""
    contract_id: UUID
    version: int
    content: Dict[str, ContractContentBase]
    modified_by: Dict[str, Any]
    change_summary: Optional[str] = None


    class Config:
        from_attributes = True

class ContractRead(ContractBase):
    """Schema for reading a contract"""
    id: UUID
    status: ContractStatus
    current_version: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_activity: datetime

    owner: Optional[Dict[str, Any]] = Field(default_factory=dict)
    organization: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True
        
    @field_validator('owner', 'organization', mode='before')
    def ensure_dict(cls, v):
        """Ensure owner and organization are dictionaries"""
        if v is None:
            return {}
        
        # If it's a SQLModel/SQLAlchemy model, convert it to a dict
        if hasattr(v, '__dict__'):
            # Extract only the attributes we want to include
            result = {}
            for attr in ['id', 'email', 'full_name']:
                if hasattr(v, attr):
                    result[attr] = getattr(v, attr)
            return result
            
        return v
     
class ContractDetailRead(ContractRead):
    """Schema for reading a contract with detailed information"""
    parties: List[ContractPartyRead]
    current_content: Dict[str, Any]
    
    class Config:
        from_attributes = True
    
