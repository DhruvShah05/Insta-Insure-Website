"""
Filename sanitization utilities for Twilio WhatsApp media URLs.

Twilio has strict requirements for media filenames:
- No spaces
- Keep file names to 20 characters or less (excluding extension)
- Avoid special characters: ~ ! @ # $ % ^ & * ( ) [ ] { }
- Must return a valid Content-Type header
- Must include Content-Disposition header
"""

import re
from typing import Tuple


def sanitize_filename_for_twilio(filename: str, max_length: int = 20) -> str:
    """
    Sanitize a filename to meet Twilio's WhatsApp media requirements.
    
    Args:
        filename: Original filename (can include extension)
        max_length: Maximum length for base name (default 20, per Twilio guidelines)
    
    Returns:
        Sanitized filename safe for Twilio media URLs
    
    Examples:
        >>> sanitize_filename_for_twilio("My Policy Document.pdf")
        'My_Policy_Document.pdf'
        
        >>> sanitize_filename_for_twilio("Test@File#123!.pdf")
        'Test_File_123.pdf'
        
        >>> sanitize_filename_for_twilio("Very Long Filename That Exceeds Twenty Characters.pdf")
        'Very_Long_Filename_T.pdf'
    """
    if not filename:
        return "document.pdf"
    
    # Split filename and extension
    name_parts = filename.rsplit('.', 1)
    base_name = name_parts[0] if len(name_parts) > 1 else filename
    extension = name_parts[1] if len(name_parts) > 1 else 'pdf'
    
    # Replace spaces and special characters with underscores
    # Only allow alphanumeric, hyphens, and underscores
    safe_base = re.sub(r'[^a-zA-Z0-9\-_]', '_', base_name)
    
    # Remove multiple consecutive underscores
    safe_base = re.sub(r'_+', '_', safe_base)
    
    # Remove leading/trailing underscores
    safe_base = safe_base.strip('_')
    
    # Ensure we have something
    if not safe_base:
        safe_base = "document"
    
    # Limit base name to max_length characters
    if len(safe_base) > max_length:
        safe_base = safe_base[:max_length].strip('_')
    
    # Ensure extension is clean too
    safe_extension = re.sub(r'[^a-zA-Z0-9]', '', extension)
    if not safe_extension:
        safe_extension = 'pdf'
    
    # Reconstruct filename
    return f"{safe_base}.{safe_extension}"


def create_policy_filename(insurance_company: str, product_name: str) -> str:
    """
    Create a sanitized filename for a policy document.
    
    Args:
        insurance_company: Name of insurance company
        product_name: Name of insurance product
    
    Returns:
        Sanitized filename suitable for Twilio
    """
    company = insurance_company or 'Policy'
    product = product_name or 'Document'
    
    # Create base filename
    base_filename = f"{company}_{product}.pdf"
    
    return sanitize_filename_for_twilio(base_filename)


def validate_filename_for_twilio(filename: str) -> Tuple[bool, str]:
    """
    Validate if a filename meets Twilio's requirements.
    
    Args:
        filename: Filename to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not filename:
        return False, "Filename is empty"
    
    # Split filename and extension
    name_parts = filename.rsplit('.', 1)
    base_name = name_parts[0] if len(name_parts) > 1 else filename
    
    # Check for spaces
    if ' ' in filename:
        return False, "Filename contains spaces"
    
    # Check for special characters
    if re.search(r'[~!@#$%^&*()\[\]{}]', filename):
        return False, "Filename contains special characters"
    
    # Check length (excluding extension)
    if len(base_name) > 20:
        return False, f"Base filename too long ({len(base_name)} chars, max 20)"
    
    return True, "Valid"


def get_response_headers_for_pdf(filename: str) -> dict:
    """
    Get the required HTTP headers for serving a PDF to Twilio.
    
    Args:
        filename: Name of the file being served
    
    Returns:
        Dictionary of headers
    """
    return {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'inline; filename="{filename}"',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'Access-Control-Allow-Origin': '*'
    }
