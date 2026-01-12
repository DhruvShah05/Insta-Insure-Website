#!/usr/bin/env python
"""
Test script for Gemini PDF extraction
Run this to verify the Gemini API is working correctly
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

def test_gemini_basic():
    """Test basic Gemini API connectivity"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in environment")
        sys.exit(1)
    
    print(f"API Key found: {api_key[:10]}...")
    
    client = genai.Client(api_key=api_key)
    
    # Simple text test first
    print("\n1. Testing basic text generation...")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Say hello in one word"]
        )
        print(f"   Success! Response: {response.text}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    # Test JSON output
    print("\n2. Testing JSON output mode...")
    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Return a JSON object with a single key 'greeting' and value 'hello'"],
            config=config
        )
        print(f"   Success! Response: {response.text}")
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    # Test with inline PDF bytes
    print("\n3. Testing PDF processing...")
    
    # Check if test PDF exists
    test_pdf_path = "static/test_policy_document.pdf"
    if not os.path.exists(test_pdf_path):
        print(f"   No test PDF found at {test_pdf_path}")
        print("   Creating a simple test with dummy PDF bytes...")
        
        # Create minimal PDF bytes (this won't be a valid PDF but tests the API call)
        # Use the create_test_pdf script if available
        try:
            from create_test_pdf import create_test_pdf
            create_test_pdf()
            print(f"   Created test PDF at {test_pdf_path}")
        except Exception as e:
            print(f"   Could not create test PDF: {e}")
            print("   Skipping PDF test")
            return
    
    try:
        with open(test_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        print(f"   PDF size: {len(pdf_bytes)} bytes")
        
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
        )
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                "Extract any text from this PDF and return as JSON: {\"text\": \"extracted text here\"}"
            ],
            config=config
        )
        print(f"   Success! Response: {response.text[:200]}...")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_basic()
