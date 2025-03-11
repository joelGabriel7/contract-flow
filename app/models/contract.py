from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlmodel import Field, Relationship, Column, JSON
from uuid import UUID, uuid4

from app.models.base import TimestampModel
from app.models.users import User
from app.models.organization import Organization


class ContractStatus(str, Enum):
    """
    Define possible states for a contract document
    """

    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    REJECTED = "rejected"

class ContractTemplateType(str, Enum):
    """
    Define possible contract template types
    """

    NDA = "nda"  # Non-Disclosure Agreement
    FREELANCE = "freelance"  # Freelance Agreement
    COLLABORATION = "collaboration"  # Collaboration Agreement
    CUSTOM = "custom"  # Custom Agreement


class Contract(TimestampModel, table=True):
    """Primary contract entity representing a legal agreement"""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Basic contract information
    title: str
    description: Optional[str] = None
    template_type: ContractTemplateType = ContractTemplateType.CUSTOM
    status: ContractStatus = ContractStatus.DRAFT
    effective_date: Optional[datetime] = Field(default_factory=datetime.utcnow)
    expiration_date: Optional[datetime] = Field(default_factory=datetime.utcnow)

    # ownerships
    owner_id: UUID = Field(foreign_key="user.id")
    owner: User = Relationship(sa_relationship_kwargs={"foreign_keys": "[Contract.owner_id]"})

    organization_id: Optional[UUID] = Field(default=None, foreign_key="organization.id")
    organization: Optional[Organization] = Relationship()

    versions: List['ContractVersion'] = Relationship(back_populates="contract", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    parties: List['ContractParty'] = Relationship(back_populates="contract", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    current_version: int = Field(default=1)

    last_activity_by_id: UUID = Field(foreign_key="user.id")
    last_activity_by: User = Relationship(sa_relationship_kwargs={"foreign_keys": "[Contract.last_activity_by_id]"})
    last_activity: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ContractPartyType(str, Enum):
    """Types of parties that can be involved in a contract"""

    INDIVIDUAL = "individual"  # Person signing in individual capacity
    ORGANIZATION = "organization"  # Organization as a party
    REPRESENTATIVE = "representative"  # Person signing on behalf of organization
    
class ContractParty(TimestampModel, table=True):
    """Represents a party involved in a contract"""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Add your implementation here
    contract_id: UUID = Field(foreign_key="contract.id", primary_key=True)
    party_type: ContractPartyType = ContractPartyType.INDIVIDUAL
    
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship()
    
    organization_id: Optional[UUID] = Field(default=None, foreign_key="organization.id")
    organization: Optional[Organization] = Relationship()
    
    external_name: Optional[str] = None
    external_email: Optional[str] = None
    
    signature_required: bool = False
    signature_date: Optional[datetime] = None
    signature_data: Optional[str] = None

    # Relationships
    contract: Contract = Relationship(back_populates="parties")



class ContractVersion(TimestampModel, table=True):
    """Represents a specific version of a contract document"""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Contract reference
    contract_id: UUID = Field(foreign_key="contract.id", primary_key=True)
    version: int = Field(primary_key=True)  # Incremental version number

    # Content storage
    content: dict = Field(sa_column=Column(JSON))  # JSON structure of contract content

    modified_by_id: UUID = Field(foreign_key="user.id")
    change_summary: Optional[str] = None
    rendered_html: Optional[str] = None
    pdf_path: Optional[str] = None

    # Relationships
    contract: Contract = Relationship(back_populates="versions")

    
