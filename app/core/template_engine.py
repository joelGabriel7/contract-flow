"""
Template engine configuration for the application.
"""
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Create Jinja2 environment
def create_jinja_env(templates_dir: str = "templates"):
    """
    Create a Jinja2 environment.
    
    Args:
        templates_dir: Directory containing template files
        
    Returns:
        Jinja2 Environment
    """
    # Create directory if it doesn't exist
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create environment
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    return env

# Helper function to render a template string
def render_template_string(template_string: str, **context):
    """
    Render a template string with the given context.
    
    Args:
        template_string: Template string to render
        context: Variables to use in the template
        
    Returns:
        Rendered string
    """
    from jinja2 import Template
    template = Template(template_string)
    return template.render(**context) 