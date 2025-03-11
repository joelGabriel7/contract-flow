import os
import uuid
from typing import Optional
import logging

from weasyprint import HTML, CSS

logger = logging.getLogger(__name__)

def generate_pdf(
    html_content: str,
    output_path: Optional[str] = None,
    css_content: Optional[str] = None
) -> str:
    """Generate a PDF from HTML content."""
    try:
        # Create output directory if needed
        if output_path:
            directory = os.path.dirname(output_path)
            os.makedirs(directory, exist_ok=True)
        else:
            filename = f"{uuid.uuid4()}.pdf"
            directory = 'storage/contracts'
            os.makedirs(directory, exist_ok=True)
            output_path = os.path.join(directory, filename)

        # Create WeasyPrint HTML object
        html = HTML(string=html_content)
        
        # Apply CSS if provided
        stylesheet = []
        if css_content:
            stylesheet.append(CSS(string=css_content))
            
        # Add default metadata
        html.write_pdf(
            output_path, 
            stylesheets=stylesheet,
        )
        
        # Log success and return path
        logger.info(f"PDF generated successfully at {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise ValueError(f"Failed to generate PDF: {str(e)}")