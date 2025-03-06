from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlmodel import Session, select
from uuid import UUID
from app.models.contract import (
    Contract, ContractStatus, ContractVersion, ContractParty
)
from app.models.users import User
from app.models.organization import Organization
from app.schemas.contract import ContractCreate, ContractUpdate, ContractVersionCreate
from app.core.permission import ROLE_PERMISSIONS, Permission
from app.models.organization import OrganizationUser

def create_contract(db: Session, user_id: UUID, contract_data: ContractCreate) -> Contract:
    """
    Create a new contract with initial content and parties.
    
    Args:
        db: Database session
        user_id: ID of the user creating the contract
        contract_data: Contract creation data
        
    Returns:
        Newly created contract
    """
    # [CHALLENGE 13] Implement contract creation
    # Requirements:
    # - Create Contract instance with data from contract_data
    # - Set owner_id to user_id
    # - Set status to DRAFT
    # - Set current_version to 1
    # - Set last_activity tracking fields
    
    contract = Contract(
        title=contract_data.title,
        description=contract_data.description,
        template_type=contract_data.template_type,
        effective_date=contract_data.effective_date,
        expiration_date=contract_data.expiration_date,
        organization_id=contract_data.organization_id,
        status=ContractStatus.DRAFT,
        owner_id=user_id,
        current_version=1,
        last_activity_by_id=user_id,
        last_activity=datetime.now(timezone.utc)
    )
    db.add(contract)
    db.flush()
    # [CHALLENGE 14] Create initial version
    # Requirements:
    # - Create ContractVersion with version=1
    # - Use content from contract_data
    # - Set modified_by_id to user_id
    # - Add appropriate change_summary
    version = ContractVersion(
        contract_id=contract.id,
        version=1,
        modified_by_id=user_id,
        change_summary=contract_data.content.get('change_summary', "Initial contract creation"),
        content=contract_data.content,
    )
    db.add(version)
    # [CHALLENGE 15] Create contract parties
    # Requirements:
    # - Create ContractParty instances for each party in contract_data.parties
    # - Add all parties to database session
    for party in contract_data.parties:
        contract_party = ContractParty(
            contract_id=contract.id,
            party_type=party.party_type,
            user_id=party.user_id,
            organization_id=party.organization_id,
            external_name=party.external_name,
            external_email=party.external_email,
            signature_required=party.signature_required,
        )
        db.add(contract_party)

    db.commit()
    db.refresh(contract)
    

    return contract


def update_contract(
    db: Session, 
    contract_id: UUID, 
    user_id: UUID, 
    contract_data: ContractUpdate
) -> Contract:
    """Update contract metadata (not content)."""
    # [CHALLENGE 16] Implement contract update
    # Requirements:
    # - Get contract by ID
    contract = db.exec(select(Contract).where(Contract.id == contract_id)).one_or_none()
    if not contract:
        raise ValueError("Contract not found")
    # - Update fields from contract_data if provided
    for field, value in contract_data.model_dump().items():
        if value is not None:
            setattr(contract, field, value)
    # - Validate status transition if status is changing
    if contract.status != contract_data.status:
        if contract.status == ContractStatus.ACTIVE and contract_data.status != ContractStatus.ACTIVE:
            raise ValueError("Cannot change status from ACTIVE to non-ACTIVE")
    # - Update activity tracking fields
    contract.last_activity_by_id = user_id
    contract.last_activity = datetime.now(timezone.utc)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract



def create_contract_version(
    db: Session, 
    contract_id: UUID, 
    user_id: UUID, 
    version_data: ContractVersionCreate
) -> ContractVersion:
    """Create a new version of contract content."""
    # [CHALLENGE 17] Implement version creation
    # Requirements:
    # - Get contract by ID
    contract = db.exec(select(Contract).where(Contract.id == contract_id)).one_or_none()
    if not contract:
        raise ValueError("Contract not found")
    # - Create new version with incremented version number
    version   = ContractVersion(
        contract_id=contract_id,
        version=contract.current_version + 1,
        modified_by_id=user_id,
        change_summary=version_data.change_summary,
        content=version_data.content,
    )
    db.add(version)

    contract.current_version = version.version
    contract.last_activity_by_id = user_id 
    contract.last_activity = datetime.now(timezone.utc)
   
    db.add(contract)
    db.commit()
    db.refresh(contract)

    return version


def get_contract_with_current_content(
    db: Session, contract_id:  UUID
) -> Optional[Contract]:
    """Get a contract with its current version content."""
    # Get contract
    contract = db.get(Contract, contract_id)
    
    if not contract:
        return None
    
    # Load relationships
    db.refresh(contract, ['parties', 'owner', 'organization'])
    
    # [CHALLENGE 18] Get current version content
    # Requirements:
    # - Query ContractVersion for current version
    version = db.exec(
        select(ContractVersion).where(
            ContractVersion.contract_id == contract_id, 
            ContractVersion.version == contract.current_version
        )
    ).first()
    # - Add content to contract as 'current_content' attribute
    if version:
        setattr(contract, 'current_content', version.content)
    else:
        setattr(contract, 'current_content', {})
    return contract

def get_user_contracts(
    db: Session, 
    user_id: UUID,
    status: Optional[ContractStatus] = None,
    organization_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "updated_at",
    sort_desc: bool = True
) -> List[Contract]:
    """
    Get contracts accessible to a user using an optimized query approach.
    
    Args:
        db: Database session
        user_id: ID of the user
        status: Optional filter by contract status
        organization_id: Optional filter by organization
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        sort_by: Field to sort by
        sort_desc: Whether to sort in descending order
        
    Returns:
        List of contracts accessible to the user
    """
    # Get organizations where user has VIEW_MEMBERS permission
    org_users = db.exec(
        select(OrganizationUser).where(
            OrganizationUser.user_id == user_id
        )
    ).all()
    
    org_ids_with_permission = [
        org_user.organization_id for org_user in org_users
        if ROLE_PERMISSIONS[org_user.role] & Permission.VIEW_MEMBERS
    ]
    
    # Base conditions that apply to all queries
    base_conditions = []
    if status:
        base_conditions.append(Contract.status == status)
    if organization_id:
        base_conditions.append(Contract.organization_id == organization_id)
    
    # 1. Contracts owned by the user
    owned_query = select(Contract).where(Contract.owner_id == user_id)
    for condition in base_conditions:
        owned_query = owned_query.where(condition)
    
    # 2. Contracts where user is a party
    party_query = (
        select(Contract)
        .join(ContractParty, ContractParty.contract_id == Contract.id)
        .where(ContractParty.user_id == user_id)
    )
    for condition in base_conditions:
        party_query = party_query.where(condition)
    
    # 3. Contracts from organizations with permission
    org_query = None
    if org_ids_with_permission:
        org_query = select(Contract).where(Contract.organization_id.in_(org_ids_with_permission))
        for condition in base_conditions:
            org_query = org_query.where(condition)
    
    # Combine queries with UNION
    final_query = owned_query.union(party_query)
    if org_query:
        final_query = final_query.union(org_query)
    
    # Apply sorting
    sort_column = getattr(Contract, sort_by)
    if sort_desc:
        final_query = final_query.order_by(sort_column.desc())
    else:
        final_query = final_query.order_by(sort_column)
    
    # Apply pagination
    final_query = final_query.offset(skip).limit(limit)
    
    # Execute query
    contracts = db.exec(final_query).all()
    
    return contracts
 
