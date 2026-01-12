# routes/agentic_policy.py
"""
Agentic Policy Routes
API endpoints for AI-powered policy document processing
"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
import logging

from gemini_policy_extractor import policy_extractor

logger = logging.getLogger(__name__)

agentic_policy_bp = Blueprint("agentic_policy", __name__, url_prefix="/agentic")


@agentic_policy_bp.route("/upload", methods=["POST"])
@login_required
def upload_and_extract():
    """
    Upload a policy document and extract information using Gemini AI.
    
    Expects:
        - policy_document: PDF file in request.files
        
    Returns:
        JSON with extracted policy data, client matching info, and fields needing review
    """
    try:
        if "policy_document" not in request.files:
            return jsonify({
                "success": False,
                "error": "No policy document uploaded"
            }), 400
        
        file = request.files["policy_document"]
        
        if not file.filename:
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400
        
        # Check file extension
        allowed_extensions = {"pdf"}
        file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if file_ext not in allowed_extensions:
            return jsonify({
                "success": False,
                "error": f"Invalid file type. Only PDF files are supported."
            }), 400
        
        # Read file bytes
        pdf_bytes = file.read()
        
        if len(pdf_bytes) == 0:
            return jsonify({
                "success": False,
                "error": "Empty file uploaded"
            }), 400
        
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(pdf_bytes) > max_size:
            return jsonify({
                "success": False,
                "error": "File too large. Maximum size is 10MB."
            }), 400
        
        logger.info(f"Processing policy document: {file.filename} ({len(pdf_bytes)} bytes)")
        
        # Extract policy information using Gemini
        result = policy_extractor.extract_from_pdf(pdf_bytes, file.filename)
        
        if not result.success:
            return jsonify({
                "success": False,
                "error": result.error or "Extraction failed"
            }), 500
        
        return jsonify(result.to_dict())
        
    except Exception as e:
        logger.error(f"Error processing policy document: {e}")
        return jsonify({
            "success": False,
            "error": f"An error occurred: {str(e)}"
        }), 500


@agentic_policy_bp.route("/lookup_client", methods=["POST"])
@login_required
def lookup_client():
    """
    Look up an existing client in the database.
    
    Expects JSON body:
        - name: Client name to search for
        - phone: Optional phone number
        - email: Optional email
        
    Returns:
        JSON with matching client info or not found message
    """
    try:
        data = request.get_json()
        
        if not data or not data.get("name"):
            return jsonify({
                "success": False,
                "error": "Client name is required"
            }), 400
        
        result = policy_extractor.lookup_client(
            name=data.get("name"),
            phone=data.get("phone"),
            email=data.get("email")
        )
        
        return jsonify({
            "success": True,
            **result
        })
        
    except Exception as e:
        logger.error(f"Error looking up client: {e}")
        return jsonify({
            "success": False,
            "error": f"Lookup failed: {str(e)}"
        }), 500


@agentic_policy_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for agentic policy service"""
    import os
    api_key_configured = bool(os.environ.get("GEMINI_API_KEY"))
    return jsonify({
        "status": "ok",
        "service": "agentic_policy",
        "gemini_api_configured": api_key_configured
    })
