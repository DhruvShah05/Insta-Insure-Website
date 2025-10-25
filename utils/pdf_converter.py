"""
PDF Conversion Utility for Twilio WhatsApp Compatibility

This module provides automated PDF conversion to ensure compatibility with Twilio WhatsApp.
It recreates PDFs using a "print to PDF" approach that resolves common issues like:
- Corrupted PDF structures
- Unsupported compression methods
- Invalid metadata
- Encoding issues
"""

import io
import os
import logging
import tempfile
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader
import pikepdf

logger = logging.getLogger(__name__)


class PDFConverter:
    """Converts PDFs to Twilio-compatible format using print-to-PDF approach"""
    
    @staticmethod
    def convert_to_twilio_compatible(input_file, output_path=None):
        """
        Convert a PDF to Twilio-compatible format
        
        Args:
            input_file: File object or path to input PDF
            output_path: Optional path for output file. If None, creates temp file
            
        Returns:
            tuple: (success: bool, output_path: str, error_message: str)
        """
        temp_output = None
        try:
            # Read input file
            if hasattr(input_file, 'read'):
                # It's a file object
                input_file.seek(0)
                input_data = input_file.read()
                input_file.seek(0)  # Reset for potential reuse
            else:
                # It's a file path
                with open(input_file, 'rb') as f:
                    input_data = f.read()
            
            # Create output path if not provided
            if output_path is None:
                temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                output_path = temp_output.name
                temp_output.close()
            
            # Method 1: Try pikepdf (most reliable for print-to-PDF simulation)
            try:
                logger.info("Attempting PDF conversion using pikepdf...")
                return PDFConverter._convert_with_pikepdf(input_data, output_path)
            except Exception as e:
                logger.warning(f"pikepdf conversion failed: {e}, trying PyPDF2...")
            
            # Method 2: Try PyPDF2 (fallback)
            try:
                logger.info("Attempting PDF conversion using PyPDF2...")
                return PDFConverter._convert_with_pypdf2(input_data, output_path)
            except Exception as e:
                logger.warning(f"PyPDF2 conversion failed: {e}, trying direct copy...")
            
            # Method 3: Direct copy as last resort
            logger.info("Using direct copy as fallback...")
            with open(output_path, 'wb') as f:
                f.write(input_data)
            
            return True, output_path, None
            
        except Exception as e:
            error_msg = f"PDF conversion failed: {str(e)}"
            logger.error(error_msg)
            
            # Clean up temp file on error
            if temp_output and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            
            return False, None, error_msg
    
    @staticmethod
    def _convert_with_pikepdf(input_data, output_path):
        """
        Convert PDF using pikepdf - simulates print-to-PDF
        This is the most reliable method for Twilio compatibility
        """
        # Open PDF with pikepdf
        pdf = pikepdf.open(io.BytesIO(input_data))
        
        # Save with optimized settings for Twilio
        pdf.save(
            output_path,
            linearize=True,  # Optimize for web viewing
            object_stream_mode=pikepdf.ObjectStreamMode.disable,  # Disable object streams
            compress_streams=True,  # Use standard compression
            stream_decode_level=pikepdf.StreamDecodeLevel.generalized,  # Decode and re-encode
            recompress_flate=True,  # Recompress using standard flate
            normalize_content=True,  # Normalize content streams
            preserve_pdfa=False,  # Don't preserve PDF/A (can cause issues)
            fix_metadata_version=True  # Fix metadata version
        )
        
        pdf.close()
        
        logger.info(f"Successfully converted PDF using pikepdf: {output_path}")
        return True, output_path, None
    
    @staticmethod
    def _convert_with_pypdf2(input_data, output_path):
        """
        Convert PDF using PyPDF2 - alternative method
        """
        # Read the PDF
        reader = PdfReader(io.BytesIO(input_data))
        writer = PdfWriter()
        
        # Copy all pages to new PDF
        for page in reader.pages:
            writer.add_page(page)
        
        # Remove potentially problematic metadata
        writer.add_metadata({
            '/Producer': 'Insta Insurance Portal',
            '/Creator': 'PDF Converter'
        })
        
        # Write to output
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        logger.info(f"Successfully converted PDF using PyPDF2: {output_path}")
        return True, output_path, None
    
    @staticmethod
    def convert_file_object(file_obj, preserve_original=True):
        """
        Convert a Flask file object to Twilio-compatible PDF
        
        Args:
            file_obj: Flask FileStorage object
            preserve_original: If True, keeps original filename
            
        Returns:
            tuple: (success: bool, converted_file_path: str, error_message: str)
        """
        try:
            # Create temp file with original filename
            original_filename = file_obj.filename
            temp_dir = tempfile.gettempdir()
            
            if preserve_original:
                # Use original filename
                base_name = os.path.splitext(original_filename)[0]
                output_filename = f"{base_name}_converted.pdf"
            else:
                output_filename = f"converted_{original_filename}"
            
            output_path = os.path.join(temp_dir, output_filename)
            
            # Convert the PDF
            success, converted_path, error = PDFConverter.convert_to_twilio_compatible(
                file_obj, 
                output_path
            )
            
            if success:
                logger.info(f"Converted file object: {original_filename} -> {output_filename}")
            
            return success, converted_path, error
            
        except Exception as e:
            error_msg = f"Error converting file object: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    @staticmethod
    def is_pdf_valid(file_path):
        """
        Check if a PDF is valid and readable
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            bool: True if PDF is valid
        """
        try:
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                # Try to read first page
                if len(reader.pages) > 0:
                    _ = reader.pages[0]
                return True
        except Exception as e:
            logger.warning(f"PDF validation failed for {file_path}: {e}")
            return False


def convert_pdf_for_twilio(input_file, output_path=None):
    """
    Convenience function to convert PDF for Twilio compatibility
    
    Args:
        input_file: File object or path to input PDF
        output_path: Optional output path
        
    Returns:
        tuple: (success: bool, output_path: str, error_message: str)
    """
    converter = PDFConverter()
    return converter.convert_to_twilio_compatible(input_file, output_path)


def convert_and_replace(file_path):
    """
    Convert a PDF file and replace the original
    
    Args:
        file_path: Path to PDF file to convert
        
    Returns:
        tuple: (success: bool, error_message: str)
    """
    try:
        # Create temp file for conversion
        temp_path = f"{file_path}.tmp"
        
        # Convert
        success, converted_path, error = convert_pdf_for_twilio(file_path, temp_path)
        
        if not success:
            return False, error
        
        # Replace original with converted
        os.replace(temp_path, file_path)
        
        logger.info(f"Successfully converted and replaced: {file_path}")
        return True, None
        
    except Exception as e:
        error_msg = f"Error in convert_and_replace: {str(e)}"
        logger.error(error_msg)
        
        # Clean up temp file if it exists
        temp_path = f"{file_path}.tmp"
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        
        return False, error_msg
