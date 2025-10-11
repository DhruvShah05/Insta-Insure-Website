from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import os

def create_test_pdf():
    """Create a test PDF file for WhatsApp template testing"""
    
    # Create the PDF file path
    pdf_path = "static/test_policy_document.pdf"
    
    # Ensure static directory exists
    os.makedirs("static", exist_ok=True)
    
    # Create PDF document
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Content for the PDF
    content = []
    
    # Title
    title = Paragraph("<b>INSTA INSURANCE CONSULTANCY</b>", styles['Title'])
    content.append(title)
    content.append(Spacer(1, 20))
    
    # Policy Document Header
    header = Paragraph("<b>INSURANCE POLICY DOCUMENT - TEST</b>", styles['Heading1'])
    content.append(header)
    content.append(Spacer(1, 20))
    
    # Policy Details
    policy_details = """
    <b>Policy Holder:</b> Test Customer<br/>
    <b>Policy Number:</b> TEST123456<br/>
    <b>Insurance Company:</b> Test Insurance Ltd.<br/>
    <b>Product:</b> Health Insurance<br/>
    <b>Policy Start Date:</b> 08/10/2025<br/>
    <b>Policy End Date:</b> 08/10/2026<br/>
    <b>Premium Amount:</b> ₹10,000<br/>
    """
    
    details = Paragraph(policy_details, styles['Normal'])
    content.append(details)
    content.append(Spacer(1, 30))
    
    # Terms and Conditions
    terms_header = Paragraph("<b>Terms and Conditions:</b>", styles['Heading2'])
    content.append(terms_header)
    content.append(Spacer(1, 10))
    
    terms_text = """
    1. This is a test policy document created for WhatsApp template testing purposes.<br/>
    2. This document is for testing the media URL functionality.<br/>
    3. All information in this document is for testing only.<br/>
    4. Please contact Insta Insurance Consultancy for actual policy documents.<br/>
    """
    
    terms = Paragraph(terms_text, styles['Normal'])
    content.append(terms)
    content.append(Spacer(1, 30))
    
    # Footer
    footer_text = """
    <b>Contact Information:</b><br/>
    Insta Insurance Consultancy<br/>
    Email: info@instainsure.co.in<br/>
    Website: https://admin.instainsure.co.in<br/>
    <br/>
    <i>This is a test document for WhatsApp template validation.</i>
    """
    
    footer = Paragraph(footer_text, styles['Normal'])
    content.append(footer)
    
    # Build the PDF
    doc.build(content)
    
    print(f"✅ Test PDF created successfully: {pdf_path}")
    return pdf_path

if __name__ == "__main__":
    create_test_pdf()
