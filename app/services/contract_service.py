from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from uuid import UUID
from app.models.contract import (
    Contract, ContractStatus, ContractVersion, ContractParty
)
from app.models.organization import OrganizationUser
from app.schemas.contract import ContractCreate, ContractUpdate, ContractVersionCreate
from app.core.permission import ROLE_PERMISSIONS, Permission
from app.core.template_engine import render_template_string, create_jinja_env
import logging

logger = logging.getLogger(__name__)

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
    
    # Load relationships
    db.refresh(contract, ['owner', 'organization'])
    
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
    owned_query = select(Contract.id).where(Contract.owner_id == user_id)
    for condition in base_conditions:
        owned_query = owned_query.where(condition)
    
    # 2. Contracts where user is a party
    party_query = (
        select(Contract.id)
        .join(ContractParty, ContractParty.contract_id == Contract.id)
        .where(ContractParty.user_id == user_id)
    )
    for condition in base_conditions:
        party_query = party_query.where(condition)
    
    # 3. Contracts from organizations with permission
    org_query = None
    if org_ids_with_permission:
        org_query = select(Contract.id).where(Contract.organization_id.in_(org_ids_with_permission))
        for condition in base_conditions:
            org_query = org_query.where(condition)
    
    # Combine queries with UNION to get unique contract IDs
    contract_ids_query = owned_query.union(party_query)
    if org_query:
        contract_ids_query = contract_ids_query.union(org_query)
    
    # Get the contract IDs
    contract_ids = [row[0] for row in db.exec(contract_ids_query).all()]
    
    # Now fetch the actual Contract objects
    if not contract_ids:
        return []
    
    # Create a query to fetch the contracts by ID
    contracts_query = select(Contract).where(Contract.id.in_(contract_ids))
    
    # Apply sorting
    sort_column = getattr(Contract, sort_by, Contract.updated_at)
    if sort_desc:
        contracts_query = contracts_query.order_by(sort_column.desc())
    else:
        contracts_query = contracts_query.order_by(sort_column)
    
    # Apply pagination
    contracts_query = contracts_query.offset(skip).limit(limit)
    
    # Execute query
    contracts = db.exec(contracts_query).all()
    
    return contracts
 

def render_contract_html(content: Dict[str, Any], contract: Contract) -> str:
    """Render contract content as HTML."""
    # Format party information
    parties = []
    for party in contract.parties:
        if party.user_id:
            parties.append({"name": f"{party.user.first_name} {party.user.last_name}"})
        elif party.organization_id:
            parties.append({"name": f"{party.organization.name}"})
        else:
            parties.append({"name": f"{party.external_name}"})
    
    # Render content sections
    content_html = render_content_sections(content)
    
    # Create Jinja2 environment
    env = create_jinja_env()
    
    # Load template
    try:
        template = env.get_template("contract.html")
        
        # Render template
        html = template.render(
            contract=contract,
            parties=parties,
            content_html=content_html
        )
    except Exception as e:
        # Fallback to inline template if file not found
        logger.warning(f"Contract template file not found, using fallback: {str(e)}")
        
        # Create template
        template_str = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{{ contract.title }}</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .header { text-align: center; margin-bottom: 30px; }
                    .title { font-size: 24px; font-weight: bold; }
                    .parties { margin: 20px 0; }
                    .content { margin: 20px 0; }
                    .signatures { margin-top: 50px; }
                </style>
            </head>
            <body>
                <div class="header">
                    <div class="title">{{ contract.title }}</div>
                    <div class="date">Effective Date: {{ contract.effective_date }}</div>
                </div>
                
                <div class="parties">
                    <h3>Parties to this Agreement:</h3>
                    {% for party in parties %}
                    <div class='party'>{{ party.name }}</div>
                    {% endfor %}
                </div>
                
                <div class="content">
                    {{ content_html|safe }}
                </div>
            </body>
            </html>
        """
        
        # Render template
        html = render_template_string(template_str, contract=contract, parties=parties, content_html=content_html)
    
    return html


def render_content_sections(content: Dict[str, Any]) -> str:
    """
    Render content sections from the structured content.
    
    Args:
        content: Structured contract content
        
    Returns:
        HTML representation of content sections
    """
    # Get sections from content
    sections = content.get("sections", [])
    
    # Create Jinja2 environment
    env = create_jinja_env()
    
    # Load template
    try:
        template = env.get_template("contract_sections.html")
        
        # Render template
        html = template.render(sections=sections)
    except Exception as e:
        # Fallback to inline template if file not found
        logger.warning(f"Contract sections template file not found, using fallback: {str(e)}")
        
        # Create template for sections
        section_template_str = """
        {% for section in sections %}
        <div class="section">
            <h2>{{ section.title }}</h2>
            <div class="section-content">{{ section.text }}</div>
            
            {% if section.subsections %}
            <div class="subsections">
                {% for subsection in section.subsections %}
                <div class="subsection">
                    <h3>{{ subsection.title }}</h3>
                    <div class="subsection-content">{{ subsection.text }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
        """
        
        # Render template
        html = render_template_string(section_template_str, sections=sections)
    
    return html