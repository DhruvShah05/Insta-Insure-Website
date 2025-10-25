#!/bin/bash

# Installation script for PDF conversion dependencies
# Run this script to install required libraries for Twilio PDF compatibility

echo "=========================================="
echo "PDF Converter Installation Script"
echo "=========================================="
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: No virtual environment detected"
    echo "It's recommended to activate your virtual environment first:"
    echo "  source .venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Installing PDF processing libraries..."
echo ""

# Install dependencies
pip install PyPDF2 reportlab pikepdf

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "PDF conversion is now enabled for:"
echo "  ✓ Policy uploads to Google Drive"
echo "  ✓ Renewal policy uploads"
echo "  ✓ Renewal reminder documents"
echo ""
echo "All PDFs will be automatically converted to"
echo "Twilio-compatible format before upload/send."
echo ""
echo "Check PDF_CONVERSION_IMPLEMENTATION.md for details."
echo ""
