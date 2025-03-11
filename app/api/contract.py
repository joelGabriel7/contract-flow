# app/api/contracts.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select
from fastapi.responses import HTMLResponse, FileResponse
import logging
import os

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.users import User, UUID
from app.models.contract import Contract, ContractStatus, ContractVersion
from app.models.organization import OrganizationUser
from app.schemas.contract import (
    ContractCreate, ContractRead, ContractDetailRead, ContractUpdate
)
from app.services.contract_service import (
    create_contract, update_contract, get_contract_with_current_content, get_user_contracts, render_contract_html, generate_contract_pdf, contract_to_api_response
)
from app.core.permission import Permission

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
def create_contract_endpoint(
    contract_data: ContractCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Create a new contract."""
    # Check permission (CREATE_CONTRACT)
    if not current_user.has_permission(Permission.MANAGES_CONTRACT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create contracts"
        )
    
    # Handle organization-specific permissions
    if contract_data.organization_id:
        # Check if user is member of the organization
        org_user_query = select(OrganizationUser).where(
            OrganizationUser.user_id == current_user.id,
            OrganizationUser.organization_id == contract_data.organization_id
        )
        org_user = db.exec(org_user_query).first()
        
        if not org_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of the specified organization"
            )
    
    # Call create_contract service function
    try:
        contract = create_contract(db, current_user.id, contract_data)
        return contract
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=List[ContractRead])
def get_contracts(
    status: Optional[ContractStatus] = None,
    organization_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get contracts accessible to the current user."""
    # Call get_user_contracts with filters
    contracts = get_user_contracts(
        db=db,
        user_id=current_user.id,
        status=status,
        organization_id=organization_id,
        skip=skip,
        limit=limit
    )
    
    return contracts

@router.get("/{contract_id}")
def get_contract_details(
    contract_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get detailed information about a specific contract, including its content.
    """
    # Check permission
    if not current_user.has_permission(Permission.MANAGES_CONTRACT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view contract details"
        )
    
    # Get contract with content
    contract, content = get_contract_with_current_content(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found"
        )
    
    # Check if user has access to this contract
    # 1. User is owner
    if contract.owner_id == current_user.id:
        pass  # User has access
    # 2. User is a party to the contract
    elif any(party.user_id == current_user.id for party in contract.parties):
        pass  # User has access
    # 3. User has organization permission
    elif contract.organization_id:
        org_user_query = select(OrganizationUser).where(
            OrganizationUser.user_id == current_user.id,
            OrganizationUser.organization_id == contract.organization_id
        )
        org_user = db.exec(org_user_query).first()
        
        if not (org_user and org_user.role in ["admin", "editor", "viewer"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this contract"
            )
    else:
        # If we get here, user doesn't have access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this contract"
        )
    
    # Convert contract to API response
    response = contract_to_api_response(contract, content)
    
    return response

@router.get("/{contract_id}/html", response_class=HTMLResponse)
def get_contract_html(
    contract_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get contract rendered as HTML.
    """
    # Check permission
    if not current_user.has_permission(Permission.MANAGES_CONTRACT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view contracts"
        )
    
    # Get contract with content
    contract, content = get_contract_with_current_content(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found"
        )
    
    # Check if user has access to this contract
    # 1. User is owner
    if contract.owner_id == current_user.id:
        pass  # User has access
    # 2. User is a party to the contract
    elif any(party.user_id == current_user.id for party in contract.parties):
        pass  # User has access
    # 3. User has organization permission
    elif contract.organization_id:
        org_user_query = select(OrganizationUser).where(
            OrganizationUser.user_id == current_user.id,
            OrganizationUser.organization_id == contract.organization_id
        )
        org_user = db.exec(org_user_query).first()
        
        if not (org_user and org_user.role in ["admin", "editor", "viewer"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this contract"
            )
    else:
        # If we get here, user doesn't have access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this contract"
        )
    
    # Render contract as HTML
    try:
        html = render_contract_html(content, contract)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error rendering contract HTML: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error rendering contract"
        )

@router.get("/{contract_id}/pdf", response_class=FileResponse)
def get_contract_pdf(
    contract_id: UUID,
    download: bool = Query(False, description="Whether to download the file or view it in browser"),
    watermark: Optional[str] = Query(None, description="Optional watermark text to add to the PDF"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Get contract as PDF.
    
    Args:
        contract_id: ID of the contract
        download: Whether to download the file or view it in browser
        watermark: Optional watermark text to add to the PDF
        
    Returns:
        PDF file
    """
    # Check permission
    if not current_user.has_permission(Permission.MANAGES_CONTRACT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view contracts"
        )
    
    # Get contract with content
    contract, content = get_contract_with_current_content(db, contract_id)
    
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found"
        )
    
    # Check access (similar to other endpoints)
    # 1. User is owner
    if contract.owner_id == current_user.id:
        pass  # User has access
    # 2. User is a party to the contract
    elif any(party.user_id == current_user.id for party in contract.parties):
        pass  # User has access
    # 3. User has organization permission
    elif contract.organization_id:
        org_user_query = select(OrganizationUser).where(
            OrganizationUser.user_id == current_user.id,
            OrganizationUser.organization_id == contract.organization_id
        )
        org_user = db.exec(org_user_query).first()
        
        if not (org_user and org_user.role in ["admin", "editor", "viewer"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this contract"
            )
    else:
        # If we get here, user doesn't have access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this contract"
        )
    
    # Check if PDF already exists for this version
    existing_pdf = None
    if hasattr(contract, 'versions') and contract.versions:
        current_version = next(
            (v for v in contract.versions if v.version == contract.current_version),
            None
        )
        if current_version and current_version.pdf_path and os.path.exists(current_version.pdf_path):
            existing_pdf = current_version.pdf_path
    
    try:
        # Use existing PDF if available and no watermark is requested, otherwise generate a new one
        if existing_pdf and not watermark:
            pdf_path = existing_pdf
            logger.info(f"Using existing PDF for contract {contract_id}, version {contract.current_version}")
        else:
            # If watermark is requested, add it to the content
            if watermark:
                # Add watermark CSS
                content['watermark'] = watermark
            
          
            pdf_path = generate_contract_pdf(content, contract)
            
            # Update contract version with PDF path if no watermark
            if not watermark and hasattr(contract, 'versions') and contract.versions:
                current_version = next(
                    (v for v in contract.versions if v.version == contract.current_version),
                    None
                )
                if current_version:
                    current_version.pdf_path = pdf_path
                    db.add(current_version)
                    db.commit()
        
        # Set filename for download
        filename = f"{contract.title.replace(' ', '_')}_v{contract.current_version}.pdf"
        if watermark:
            filename = f"{filename.split('.')[0]}_{watermark.replace(' ', '_')}.pdf"
        
        # Return file response
        return FileResponse(
            path=pdf_path,
            filename=filename if download else None,
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Error generating contract PDF: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating contract PDF"
        )

"""

{
  "title": "Acuerdo de Servicios de Consultoría Tecnológica",
  "description": "Contrato para la prestación de servicios de consultoría en transformación digital y modernización de infraestructura IT",
  "template_type": "custom",
  "effective_date": "2024-04-20T00:00:00.000Z",
  "expiration_date": "2025-04-20T00:00:00.000Z",
  "organization_id": "53785715-7a0b-4f44-bcb5-4df6ad5bfed8",
  "parties": [
    {
      "party_type": "organization",
      "organization_id": "53785715-7a0b-4f44-bcb5-4df6ad5bfed8",
      "signature_required": true
    },
    {
      "party_type": "individual",
      "external_name": "Consultora Tecnológica Global",
      "external_email": "contratos@consultoratecnologica.com",
      "signature_required": true
    }
  ],
  "content": {
    "sections": [
      {
        "title": "ACUERDO DE SERVICIOS DE CONSULTORÍA TECNOLÓGICA",
        "text": "Este Acuerdo de Servicios de Consultoría Tecnológica (el \"Acuerdo\") se celebra entre Tu Organización (\"Cliente\") y Consultora Tecnológica Global (\"Consultor\"), con fecha efectiva del 20 de abril de 2024.",
        "type": "header"
      },
      {
        "title": "1. ALCANCE DE LOS SERVICIOS",
        "text": "El Consultor proporcionará al Cliente los siguientes servicios de consultoría tecnológica (los \"Servicios\"):",
        "type": "text",
        "subsections": [
          {
            "title": "1.1 Evaluación de Infraestructura",
            "text": "Análisis completo de la infraestructura tecnológica actual del Cliente, incluyendo hardware, software, redes, seguridad y procesos operativos."
          },
          {
            "title": "1.2 Estrategia de Transformación Digital",
            "text": "Desarrollo de una estrategia integral de transformación digital alineada con los objetivos comerciales del Cliente."
          },
          {
            "title": "1.3 Modernización de Sistemas",
            "text": "Recomendaciones detalladas para la modernización de sistemas legacy, migración a la nube y adopción de nuevas tecnologías."
          },
          {
            "title": "1.4 Implementación y Soporte",
            "text": "Asistencia en la implementación de las recomendaciones aprobadas y soporte continuo durante el período de transición."
          }
        ]
      },
      {
        "title": "2. PLAZO Y CRONOGRAMA",
        "text": "Los Servicios se prestarán durante un período de doce (12) meses a partir de la fecha efectiva de este Acuerdo, de acuerdo con el siguiente cronograma:",
        "type": "text",
        "subsections": [
          {
            "title": "2.1 Fase 1: Evaluación (Meses 1-2)",
            "text": "Análisis completo de la infraestructura actual y entrevistas con stakeholders clave."
          },
          {
            "title": "2.2 Fase 2: Planificación Estratégica (Meses 3-4)",
            "text": "Desarrollo de la estrategia de transformación digital y hoja de ruta de implementación."
          },
          {
            "title": "2.3 Fase 3: Implementación Inicial (Meses 5-8)",
            "text": "Implementación de las primeras iniciativas de modernización y transformación."
          },
          {
            "title": "2.4 Fase 4: Optimización y Soporte (Meses 9-12)",
            "text": "Refinamiento de las soluciones implementadas y soporte continuo."
          }
        ]
      },
      {
        "title": "3. HONORARIOS Y PAGOS",
        "text": "Como contraprestación por los Servicios, el Cliente pagará al Consultor los siguientes honorarios:",
        "type": "text",
        "subsections": [
          {
            "title": "3.1 Tarifa Base",
            "text": "Una tarifa base de €180,000 por los Servicios descritos en la Sección 1, pagadera en cuotas mensuales iguales de €15,000."
          },
          {
            "title": "3.2 Gastos Reembolsables",
            "text": "Reembolso de gastos razonables incurridos por el Consultor en la prestación de los Servicios, sujetos a la aprobación previa del Cliente y presentación de recibos."
          },
          {
            "title": "3.3 Servicios Adicionales",
            "text": "Cualquier servicio adicional no incluido en el alcance definido en la Sección 1 se facturará a una tarifa de €200 por hora, previa aprobación por escrito del Cliente."
          }
        ]
      },
      {
        "title": "4. ENTREGABLES",
        "text": "El Consultor proporcionará los siguientes entregables como parte de los Servicios:",
        "type": "text",
        "subsections": [
          {
            "title": "4.1 Informe de Evaluación",
            "text": "Documento detallado que analiza el estado actual de la infraestructura tecnológica del Cliente y áreas de mejora."
          },
          {
            "title": "4.2 Plan Estratégico",
            "text": "Estrategia de transformación digital completa con recomendaciones específicas, prioridades y cronograma de implementación."
          },
          {
            "title": "4.3 Informes de Progreso",
            "text": "Informes mensuales que detallan el progreso de la implementación, desafíos encontrados y próximos pasos."
          },
          {
            "title": "4.4 Documentación Técnica",
            "text": "Documentación completa de todas las soluciones implementadas, incluyendo arquitectura, configuraciones y procedimientos operativos."
          }
        ]
      },
      {
        "title": "5. RESPONSABILIDADES DEL CLIENTE",
        "text": "Para facilitar la prestación de los Servicios, el Cliente acuerda:",
        "type": "text",
        "subsections": [
          {
            "title": "5.1 Acceso a Información",
            "text": "Proporcionar acceso oportuno a toda la información, sistemas y personal necesarios para la prestación de los Servicios."
          },
          {
            "title": "5.2 Punto de Contacto",
            "text": "Designar a un representante principal que servirá como punto de contacto principal y tendrá autoridad para tomar decisiones relacionadas con los Servicios."
          },
          {
            "title": "5.3 Revisión de Entregables",
            "text": "Revisar y proporcionar retroalimentación sobre los entregables dentro de los diez (10) días hábiles siguientes a su recepción."
          }
        ]
      },
      {
        "title": "6. CONFIDENCIALIDAD",
        "text": "Cada parte mantendrá la confidencialidad de toda la información confidencial recibida de la otra parte y no utilizará dicha información excepto según sea necesario para cumplir con sus obligaciones bajo este Acuerdo. Esta obligación de confidencialidad sobrevivirá a la terminación de este Acuerdo por un período de tres (3) años.",
        "type": "text"
      },
      {
        "title": "7. PROPIEDAD INTELECTUAL",
        "text": "Todos los derechos de propiedad intelectual sobre los entregables y otros materiales creados por el Consultor en el curso de la prestación de los Servicios se transferirán al Cliente tras el pago completo de los honorarios. El Consultor conservará la propiedad de sus metodologías, herramientas y conocimientos preexistentes utilizados en la prestación de los Servicios.",
        "type": "text"
      },
      {
        "title": "8. LIMITACIÓN DE RESPONSABILIDAD",
        "text": "La responsabilidad total del Consultor bajo este Acuerdo, ya sea por incumplimiento de contrato, negligencia u otra causa, no excederá el monto total de los honorarios pagados por el Cliente bajo este Acuerdo. En ningún caso cualquiera de las partes será responsable por daños indirectos, incidentales, especiales o consecuentes.",
        "type": "text"
      },
      {
        "title": "9. TERMINACIÓN",
        "text": "Cualquiera de las partes puede terminar este Acuerdo mediante notificación por escrito con treinta (30) días de anticipación. En caso de terminación, el Cliente pagará al Consultor por todos los Servicios prestados hasta la fecha de terminación y por cualquier gasto no cancelable incurrido por el Consultor.",
        "type": "text"
      },
      {
        "title": "10. RELACIÓN DE LAS PARTES",
        "text": "El Consultor es un contratista independiente y no un empleado, agente o socio del Cliente. El Consultor será responsable de todos los impuestos, seguros y otros asuntos relacionados con su estatus como contratista independiente.",
        "type": "text"
      },
      {
        "title": "11. LEY APLICABLE Y RESOLUCIÓN DE DISPUTAS",
        "text": "Este Acuerdo se regirá e interpretará de acuerdo con las leyes de España. Cualquier disputa que surja de o en relación con este Acuerdo se resolverá mediante negociación de buena fe. Si la negociación no resuelve la disputa, las partes acuerdan someterse a mediación antes de iniciar cualquier procedimiento legal.",
        "type": "text"
      },
      {
        "title": "12. DISPOSICIONES GENERALES",
        "text": "Este Acuerdo constituye el entendimiento completo entre las partes con respecto al objeto del mismo y reemplaza todos los acuerdos y entendimientos previos. Cualquier modificación debe ser por escrito y firmada por ambas partes. Si alguna disposición de este Acuerdo se considera inválida o inaplicable, las disposiciones restantes permanecerán en pleno vigor y efecto.",
        "type": "text"
      },
      {
        "title": "13. FIRMAS",
        "text": "EN FE DE LO CUAL, las partes han ejecutado este Acuerdo a través de sus representantes debidamente autorizados en la fecha indicada anteriormente.",
        "type": "text"
      }
    ],
    "change_summary": "Creación inicial del acuerdo de servicios de consultoría tecnológica"
  }
}


"""