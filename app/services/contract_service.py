from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
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
from app.services.pdf_service import generate_pdf

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
    db: Session, contract_id: UUID
) -> Tuple[Optional[Contract], Optional[Dict[str, Any]]]:
    """
    Get a contract with its current version content.
    
    Returns:
        Tuple of (contract, content)
    """
    # Get contract
    contract = db.get(Contract, contract_id)
    
    if not contract:
        return None, None
    
    # Load relationships
    db.refresh(contract, ['parties', 'owner', 'organization'])
    
    # Get current version content
    version = db.exec(
        select(ContractVersion).where(
            ContractVersion.contract_id == contract_id, 
            ContractVersion.version == contract.current_version
        )
    ).first()
    
    content = version.content if version else {}
        
    return contract, content

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
    """
    Render contract content as HTML.
    
    Args:
        content: Contract content
        contract: Contract model
        
    Returns:
        HTML representation of contract
    """
    try:
        # Format party information
        parties = []
        for party in contract.parties:
            if party.user:
                parties.append({"name": party.user.full_name if party.user.full_name else party.user.email})
            elif party.organization:
                parties.append({"name": party.organization.name})
            else:
                parties.append({"name": party.external_name if party.external_name else party.external_email})
        
        # Render content sections
        content_html = render_content_sections(content.get("sections", []))
        
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
            
            # Create template for contract
            contract_template_str = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{{ contract.title }}</title>
                <style>
                    body { 
                        font-family: Arial, sans-serif; 
                        margin: 40px;
                        line-height: 1.5;
                        color: #333;
                    }
                    .header { 
                        text-align: center; 
                        margin-bottom: 30px;
                        border-bottom: 1px solid #eee;
                        padding-bottom: 20px;
                    }
                    .title { 
                        font-size: 24px; 
                        font-weight: bold;
                        margin-bottom: 10px;
                    }
                    .parties { 
                        margin: 20px 0;
                        padding: 15px;
                        background-color: #f9f9f9;
                        border-radius: 5px;
                    }
                    .party {
                        margin: 5px 0;
                        padding: 5px 0;
                    }
                    .content { 
                        margin: 20px 0;
                    }
                    .section {
                        margin-bottom: 20px;
                    }
                    .section h2 {
                        border-bottom: 1px solid #eee;
                        padding-bottom: 5px;
                    }
                    .subsection {
                        margin-left: 20px;
                        margin-bottom: 15px;
                    }
                    .subsection h3 {
                        font-size: 16px;
                    }
                    .signatures { 
                        margin-top: 50px;
                        display: flex;
                        justify-content: space-between;
                    }
                    .signature-block {
                        width: 45%;
                        border-top: 1px solid #000;
                        padding-top: 5px;
                        margin-top: 70px;
                    }
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
                
                <div class="signatures">
                    {% for party in parties %}
                    <div class="signature-block">
                        <div>{{ party.name }}</div>
                        <div>Date: ________________</div>
                    </div>
                    {% endfor %}
                </div>
            </body>
            </html>
            """
            
            # Render template
            html = render_template_string(
                contract_template_str, 
                contract=contract,
                parties=parties,
                content_html=content_html
            )
        
        return html
    except Exception as e:
        logger.error(f"Error rendering contract HTML: {str(e)}")
        raise ValueError(f"Failed to render contract HTML: {str(e)}")


def render_content_sections(sections: List[Dict[str, Any]]) -> str:
    """
    Render contract content sections as HTML.
    
    Args:
        sections: List of content sections
        
    Returns:
        HTML representation of content sections
    """
    try:
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
    except Exception as e:
        logger.error(f"Error rendering content sections: {str(e)}")
        return "<p>Error rendering content sections</p>"

def generate_contract_pdf(content: Dict[str, Any], contract: Contract) -> str:
    """
    Generate PDF from contract content.
    
    Args:
        content: Contract content
        contract: Contract model
        
    Returns:
        Path to generated PDF file
    """
    # First render the contract as HTML
    html_content = render_contract_html(content, contract)
    
    # Generate PDF using the pdf_service
    filename = f"contract_{contract.id}_{contract.current_version}.pdf"
    output_path = f"storage/contracts/{contract.id}/{filename}"
    
    # Add custom CSS for contracts if needed
    css_content = """
    body {
        font-family: Arial, sans-serif;
        font-size: 12pt;
        line-height: 1.5;
        margin: 2cm;
    }
    h1 {
        font-size: 18pt;
        text-align: center;
        margin-bottom: 2cm;
    }
    h2 {
        font-size: 14pt;
        margin-top: 1.5cm;
        margin-bottom: 0.5cm;
    }
    .section {
        margin-bottom: 1cm;
    }
    .section-content {
        text-align: justify;
    }
    .footer {
        position: fixed;
        bottom: 0;
        width: 100%;
        text-align: center;
        font-size: 9pt;
        color: #666;
    }
    @page {
        @bottom-center {
            content: "Página " counter(page) " de " counter(pages);
            font-size: 9pt;
            color: #666;
        }
        @top-right {
            content: "Contrato: " string(contract-title);
            font-size: 9pt;
            color: #666;
        }
    }
    h1 {
        string-set: contract-title content();
    }
    """
    
    # Add metadata for the PDF
    metadata = {
        'title': f"Contract: {contract.title}",
        'subject': f"Contract ID: {contract.id}, Version: {contract.current_version}",
        'keywords': f"contract, {contract.template_type}, {contract.status}",
        'creator': 'Contract Management System',
    }
    
    try:
        # Generate PDF using the pdf_service
        pdf_path = generate_pdf(
            html_content=html_content,
            output_path=output_path,
            css_content=css_content,
            metadata=metadata
        )
        
        # Update the contract version with the PDF path
        # This is optional but useful for future reference
        if hasattr(contract, 'versions') and contract.versions:
            current_version = next(
                (v for v in contract.versions if v.version == contract.current_version),
                None
            )
            if current_version:
                current_version.pdf_path = pdf_path
        
        return pdf_path
    except Exception as e:
        logger.error(f"Error generating contract PDF: {str(e)}")
        raise ValueError(f"Failed to generate contract PDF: {str(e)}")

def contract_to_api_response(contract: Contract, content: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert a Contract model to an API response dictionary.
    
    Args:
        contract: Contract model
        content: Optional content to include
        
    Returns:
        Dictionary suitable for API response
    """
    return {
        "id": str(contract.id),
        "title": contract.title,
        "description": contract.description,
        "template_type": contract.template_type.value,
        "status": contract.status.value,
        "effective_date": contract.effective_date.isoformat() if contract.effective_date else None,
        "expiration_date": contract.expiration_date.isoformat() if contract.expiration_date else None,
        "organization_id": str(contract.organization_id) if contract.organization_id else None,
        "current_version": contract.current_version,
        "created_at": contract.created_at.isoformat(),
        "updated_at": contract.updated_at.isoformat() if contract.updated_at else None,
        "last_activity": contract.last_activity.isoformat() if contract.last_activity else None,
        "owner": {
            "id": str(contract.owner.id),
            "email": contract.owner.email,
            "full_name": contract.owner.full_name if hasattr(contract.owner, "full_name") else None
        },
        "organization": {
            "id": str(contract.organization.id),
            "name": contract.organization.name
        } if contract.organization else None,
        "parties": [
            {
                "id": str(party.id),
                "contract_id": str(party.contract_id),
                "party_type": party.party_type.value,
                "user_id": str(party.user_id) if party.user_id else None,
                "organization_id": str(party.organization_id) if party.organization_id else None,
                "external_name": party.external_name,
                "external_email": party.external_email,
                "signature_required": party.signature_required,
                "signature_date": party.signature_date.isoformat() if party.signature_date else None,
                "user": {
                    "id": str(party.user.id),
                    "email": party.user.email,
                    "full_name": party.user.full_name if hasattr(party.user, "full_name") else None
                } if party.user else None,
                "organization": {
                    "id": str(party.organization.id),
                    "name": party.organization.name
                } if party.organization else None
            }
            for party in contract.parties
        ],
        "current_content": content or {}
    }