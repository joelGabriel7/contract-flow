import json
import os
from typing import Dict, List, Optional, Any
import logging
import copy

from app.models.contract import ContractTemplateType
from app.core.template_engine import render_template_string

logger = logging.getLogger(__name__)


class TemplateService:
    """
    Service for managing contract templates.
    
    This service handles:
    - Loading template definitions
    - Generating content structures from templates
    - Managing custom templates
    - Validating template data
    """
    
    def __init__(self, templates_dir: str = "templates"):
        """
        Initialize the template service.
        
        Args:
            templates_dir: Directory containing template definitions
        """
        self.templates_dir = templates_dir
        self.templates = {}
        self.load_templates()
    
    def load_templates(self) -> None:
        """
        Load all template definitions from the templates directory.
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.templates_dir, exist_ok=True)
            
            # Load built-in templates
            self._load_built_in_templates()
            
            # Load custom templates from files
            for filename in os.listdir(self.templates_dir):
                if filename.endswith(".json"):
                    template_path = os.path.join(self.templates_dir, filename)
                    with open(template_path, "r") as f:
                        template_data = json.load(f)
                        
                        # Validate template structure
                        if self._validate_template_structure(template_data):
                            template_id = template_data.get("id")
                            self.templates[template_id] = template_data
            
            logger.info(f"Loaded {len(self.templates)} templates")
        
        except Exception as e:
            logger.error(f"Error loading templates: {str(e)}")
            # Load built-in templates as fallback
            self._load_built_in_templates()
    
    def _load_built_in_templates(self) -> None:
        """
        Load built-in template definitions.
        """
        # NDA template
        self.templates[ContractTemplateType.NDA] = {
            "id": ContractTemplateType.NDA,
            "name": "Non-Disclosure Agreement",
            "description": "Standard confidentiality agreement to protect proprietary information.",
            "version": "1.0",
            "structure": self._get_nda_structure(),
            "variables": [
                {"name": "confidential_information_definition", "type": "text", "required": True},
                {"name": "disclosure_purpose", "type": "text", "required": True},
                {"name": "exclusions", "type": "text", "required": False},
                {"name": "term_years", "type": "number", "required": True, "default": 1},
                {"name": "governing_law", "type": "text", "required": True}
            ]
        }
        
        # Freelance template
        self.templates[ContractTemplateType.FREELANCE] = {
            "id": ContractTemplateType.FREELANCE,
            "name": "Freelance Service Agreement",
            "description": "Contract for hiring independent contractors and freelancers.",
            "version": "1.0",
            "structure": self._get_freelance_structure(),
            "variables": [
                {"name": "service_description", "type": "text", "required": True},
                {"name": "deliverables", "type": "list", "required": True},
                {"name": "payment_terms", "type": "text", "required": True},
                {"name": "hourly_rate", "type": "number", "required": False},
                {"name": "fixed_fee", "type": "number", "required": False},
                {"name": "timeline", "type": "text", "required": True},
                {"name": "intellectual_property", "type": "text", "required": True},
                {"name": "termination_notice_days", "type": "number", "required": True, "default": 14}
            ]
        }
        
        # Collaboration template
        self.templates[ContractTemplateType.COLLABORATION] = {
            "id": ContractTemplateType.COLLABORATION,
            "name": "Collaboration Agreement",
            "description": "Agreement for joint business ventures and project collaboration.",
            "version": "1.0",
            "structure": self._get_collaboration_structure(),
            "variables": [
                {"name": "project_description", "type": "text", "required": True},
                {"name": "roles_responsibilities", "type": "text", "required": True},
                {"name": "resource_commitments", "type": "text", "required": True},
                {"name": "revenue_sharing", "type": "text", "required": False},
                {"name": "intellectual_property", "type": "text", "required": True},
                {"name": "term_months", "type": "number", "required": True, "default": 12},
                {"name": "termination_conditions", "type": "text", "required": True}
            ]
        }
    
    def _validate_template_structure(self, template_data: Dict[str, Any]) -> bool:
        """
        Validate template structure.
        
        Args:
            template_data: Template definition data
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ["id", "name", "structure", "variables"]
        
        # Check required fields
        for field in required_fields:
            if field not in template_data:
                logger.error(f"Template missing required field: {field}")
                return False
        
        # Check structure format
        if not isinstance(template_data["structure"], dict) or "sections" not in template_data["structure"]:
            logger.error("Template structure format is invalid")
            return False
        
        # Check variables format
        if not isinstance(template_data["variables"], list):
            logger.error("Template variables format is invalid")
            return False
        
        return True
    
    def get_template(self, template_type: ContractTemplateType) -> Optional[Dict[str, Any]]:
        """
        Get a template definition by type.
        
        Args:
            template_type: Type of template to retrieve
            
        Returns:
            Template definition or None if not found
        """
        return self.templates.get(template_type)
    
    def get_all_templates(self) -> List[Dict[str, Any]]:
        """
        Get all available templates.
        
        Returns:
            List of template definitions
        """
        return list(self.templates.values())
    
    def create_template_instance(
        self, 
        template_type: ContractTemplateType, 
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a content instance from a template with provided variables.
        
        Args:
            template_type: Type of template to use
            variables: Values for template variables
            
        Returns:
            Content structure with variables applied
            
        Raises:
            ValueError: If template not found or variables invalid
        """
        template = self.get_template(template_type)
        
        if not template:
            raise ValueError(f"Template not found: {template_type}")
        
        # Validate required variables
        self._validate_variables(template, variables)
        
        # Apply variables to structure
        content = self._apply_variables(template["structure"], variables)
        
        # Add metadata
        content["meta"] = {
            "template_id": template["id"],
            "template_version": template.get("version", "1.0"),
            "created_from_template": True
        }
        
        return content
    
    def _validate_variables(self, template: Dict[str, Any], variables: Dict[str, Any]) -> None:
        """
        Validate that all required variables are provided.
        
        Args:
            template: Template definition
            variables: Variables to validate
            
        Raises:
            ValueError: If required variables are missing
        """
        missing_vars = []
        
        for var_def in template["variables"]:
            if var_def.get("required", False):
                if var_def["name"] not in variables:
                    # Check if default exists
                    if "default" not in var_def:
                        missing_vars.append(var_def["name"])
        
        if missing_vars:
            raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")
    
    def _apply_variables(self, structure: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply variables to the template structure.
        
        Args:
            structure: Template structure
            variables: Variables to apply
            
        Returns:
            Content structure with variables applied
        """
        # Create a deep copy of the structure
        content = copy.deepcopy(structure)
        
        # Helper function to replace variables in text using Jinja2
        def replace_variables(text, variables):
            if not isinstance(text, str):
                return text
                
            # Replace {{var.name}} with {{name}} for Jinja2 compatibility
            for var_name in variables.keys():
                placeholder = f"{{{{var.{var_name}}}}}"
                if placeholder in text:
                    text = text.replace(placeholder, f"{{{{ {var_name} }}}}")
            
            # Render with Jinja2
            return render_template_string(text, **variables)
        
        # Helper function to process nested dictionaries
        def process_dict(d, variables):
            for key, value in d.items():
                if isinstance(value, dict):
                    process_dict(value, variables)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            process_dict(item, variables)
                        elif isinstance(item, str):
                            d[key][i] = replace_variables(item, variables)
                elif isinstance(value, str):
                    d[key] = replace_variables(value, variables)
        
        # Process the content structure
        process_dict(content, variables)
        
        return content
    
    def save_custom_template(self, template_data: Dict[str, Any]) -> str:
        """
        Save a custom template.
        
        Args:
            template_data: Template definition
            
        Returns:
            ID of the saved template
            
        Raises:
            ValueError: If template data is invalid
        """
        # Validate template structure
        if not self._validate_template_structure(template_data):
            raise ValueError("Invalid template structure")
        
        # Ensure template ID is set to CUSTOM
        template_data["id"] = f"custom_{template_data.get('id', 'template')}"
        
        # Save to file
        filename = f"{template_data['id']}.json"
        file_path = os.path.join(self.templates_dir, filename)
        
        with open(file_path, "w") as f:
            json.dump(template_data, f, indent=2)
        
        # Add to loaded templates
        self.templates[template_data["id"]] = template_data
        
        return template_data["id"]
    
    def delete_custom_template(self, template_id: str) -> bool:
        """
        Delete a custom template.
        
        Args:
            template_id: ID of template to delete
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            ValueError: If attempting to delete a built-in template
        """
        # Check if template exists
        if template_id not in self.templates:
            return False
        
        # Check if it's a built-in template
        if template_id in [t.value for t in ContractTemplateType]:
            raise ValueError("Cannot delete built-in template")
        
        # Remove from loaded templates
        del self.templates[template_id]
        
        # Delete file if exists
        filename = f"{template_id}.json"
        file_path = os.path.join(self.templates_dir, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        
        return False
    
    # Template structure definitions
    def _get_nda_structure(self) -> Dict[str, Any]:
        """Get the structure for an NDA template."""
        return {
            "sections": [
                {
                    "title": "Confidentiality Agreement",
                    "text": "This Non-Disclosure Agreement (\"Agreement\") is entered into by and between the parties identified below, effective as of the date of last signature.",
                    "type": "header"
                },
                {
                    "title": "1. Definition of Confidential Information",
                    "text": "{{var.confidential_information_definition}}",
                    "type": "text"
                },
                {
                    "title": "2. Purpose",
                    "text": "The Recipient shall use the Confidential Information only for: {{var.disclosure_purpose}}",
                    "type": "text"
                },
                {
                    "title": "3. Non-Disclosure Obligations",
                    "text": "Recipient agrees to keep all Confidential Information strictly confidential and shall not disclose such information to any third party without prior written consent from the Discloser.",
                    "type": "text",
                    "subsections": [
                        {
                            "title": "3.1 Standard of Care",
                            "text": "Recipient shall protect the Confidential Information with the same degree of care as it uses to protect its own confidential information, but in no event less than reasonable care."
                        },
                        {
                            "title": "3.2 Limited Disclosure",
                            "text": "Recipient may disclose Confidential Information only to its employees, agents or representatives who need to know such information for the Purpose and who are bound by confidentiality obligations no less restrictive than those in this Agreement."
                        }
                    ]
                },
                {
                    "title": "4. Exclusions",
                    "text": "This Agreement does not apply to information that: (a) is or becomes publicly available through no fault of the Recipient; (b) was rightfully known to Recipient prior to disclosure by Discloser; (c) is rightfully obtained by Recipient from a third party without restriction; (d) is independently developed by Recipient without use of Discloser's Confidential Information; or (e) is required to be disclosed by law or court order, provided Recipient gives Discloser reasonable notice to allow Discloser to contest such requirement. {{var.exclusions}}",
                    "type": "text"
                },
                {
                    "title": "5. Term and Termination",
                    "text": "This Agreement shall remain in effect for a period of {{var.term_years}} years from the Effective Date. The confidentiality obligations shall survive termination of this Agreement.",
                    "type": "text"
                },
                {
                    "title": "6. Return of Materials",
                    "text": "Upon Discloser's request or upon termination of this Agreement, Recipient shall promptly return or destroy all Confidential Information and any copies thereof.",
                    "type": "text"
                },
                {
                    "title": "7. Governing Law",
                    "text": "This Agreement shall be governed by and construed in accordance with the laws of {{var.governing_law}}, without regard to its conflict of law principles.",
                    "type": "text"
                },
                {
                    "title": "8. Entire Agreement",
                    "text": "This Agreement constitutes the entire understanding between the parties concerning the subject matter hereof and supersedes all prior discussions, agreements and representations.",
                    "type": "text"
                }
            ]
        }
    
    def _get_freelance_structure(self) -> Dict[str, Any]:
        """Get the structure for a freelance services template."""
        return {
            "sections": [
                {
                    "title": "Freelance Service Agreement",
                    "text": "This Freelance Service Agreement (\"Agreement\") is entered into by and between the parties identified below, effective as of the date of last signature.",
                    "type": "header"
                },
                {
                    "title": "1. Services",
                    "text": "The Freelancer agrees to provide the following services (\"Services\") to the Client: {{var.service_description}}",
                    "type": "text"
                },
                {
                    "title": "2. Deliverables",
                    "text": "The Freelancer shall deliver the following: {{var.deliverables}}",
                    "type": "text"
                },
                {
                    "title": "3. Payment Terms",
                    "text": "{{var.payment_terms}}",
                    "type": "text",
                    "subsections": [
                        {
                            "title": "3.1 Rates",
                            "text": "Hourly Rate: ${{var.hourly_rate}} per hour\nFixed Fee: ${{var.fixed_fee}}"
                        },
                        {
                            "title": "3.2 Invoicing",
                            "text": "Freelancer shall submit invoices [frequency], and Client shall pay all undisputed amounts within 30 days of receipt of invoice."
                        },
                        {
                            "title": "3.3 Expenses",
                            "text": "Client shall reimburse Freelancer for pre-approved, reasonable expenses incurred in performing the Services."
                        }
                    ]
                },
                {
                    "title": "4. Timeline",
                    "text": "{{var.timeline}}",
                    "type": "text"
                },
                {
                    "title": "5. Independent Contractor Status",
                    "text": "Freelancer is an independent contractor, not an employee of Client. Freelancer is responsible for all taxes, insurance, and business expenses related to the Services.",
                    "type": "text"
                },
                {
                    "title": "6. Intellectual Property",
                    "text": "{{var.intellectual_property}}",
                    "type": "text"
                },
                {
                    "title": "7. Confidentiality",
                    "text": "Freelancer shall maintain the confidentiality of Client's confidential information and shall not disclose such information without Client's prior written consent.",
                    "type": "text"
                },
                {
                    "title": "8. Termination",
                    "text": "Either party may terminate this Agreement with {{var.termination_notice_days}} days written notice. Upon termination, Client shall pay for all Services performed up to the termination date.",
                    "type": "text"
                },
                {
                    "title": "9. Limitation of Liability",
                    "text": "Neither party shall be liable for indirect, special, or consequential damages arising out of this Agreement.",
                    "type": "text"
                },
                {
                    "title": "10. Warranty",
                    "text": "Freelancer warrants that the Services will be performed in a professional and workmanlike manner in accordance with industry standards.",
                    "type": "text"
                }
            ]
        }
    
    def _get_collaboration_structure(self) -> Dict[str, Any]:
        """Get the structure for a collaboration agreement template."""
        return {
            "sections": [
                {
                    "title": "Collaboration Agreement",
                    "text": "This Collaboration Agreement (\"Agreement\") is entered into by and between the parties identified below, effective as of the date of last signature.",
                    "type": "header"
                },
                {
                    "title": "1. Project Description",
                    "text": "The parties agree to collaborate on the following project (\"Project\"): {{var.project_description}}",
                    "type": "text"
                },
                {
                    "title": "2. Roles and Responsibilities",
                    "text": "{{var.roles_responsibilities}}",
                    "type": "text"
                },
                {
                    "title": "3. Resources and Contributions",
                    "text": "Each party agrees to contribute the following resources to the Project: {{var.resource_commitments}}",
                    "type": "text"
                },
                {
                    "title": "4. Revenue Sharing",
                    "text": "{{var.revenue_sharing}}",
                    "type": "text"
                },
                {
                    "title": "5. Intellectual Property",
                    "text": "{{var.intellectual_property}}",
                    "type": "text",
                    "subsections": [
                        {
                            "title": "5.1 Pre-existing IP",
                            "text": "Each party retains ownership of its pre-existing intellectual property used in the Project."
                        },
                        {
                            "title": "5.2 Project IP",
                            "text": "Intellectual property created specifically for the Project shall be owned as specified in this section."
                        },
                        {
                            "title": "5.3 Licensing",
                            "text": "Each party grants the other a non-exclusive license to use its intellectual property solely for purposes of the Project."
                        }
                    ]
                },
                {
                    "title": "6. Term and Termination",
                    "text": "This Agreement shall remain in effect for a period of {{var.term_months}} months from the Effective Date, unless terminated earlier in accordance with this Agreement.",
                    "type": "text"
                },
                {
                    "title": "7. Termination Conditions",
                    "text": "This Agreement may be terminated under the following conditions: {{var.termination_conditions}}",
                    "type": "text"
                },
                {
                    "title": "8. Confidentiality",
                    "text": "Each party shall maintain the confidentiality of the other party's confidential information and shall not disclose such information without prior written consent.",
                    "type": "text"
                },
                {
                    "title": "9. Non-Competition",
                    "text": "During the term of this Agreement and for six months thereafter, neither party shall engage in activities that directly compete with the Project without the written consent of the other party.",
                    "type": "text"
                },
                {
                    "title": "10. Dispute Resolution",
                    "text": "Any disputes arising out of this Agreement shall be resolved through good faith negotiation. If negotiation fails, disputes shall be submitted to mediation before litigation.",
                    "type": "text"
                }
            ]
        }