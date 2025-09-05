#!/usr/bin/env python3
"""
Production-Ready Medical Document Processor for Enfermera Elena
Handles: OCR, PHI detection, and translation for Mexican medical records
"""

import os
import re
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum

# OCR imports
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# Load environment
env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")

from openai import OpenAI

# Import our PHI detector
from phi_detector_enhanced import SpanishMedicalPHIDetector, PHIType

class PageType(Enum):
    """Types of pages in medical documents"""
    DIGITAL = "born_digital"      # Text extractable PDF
    SCANNED = "scanned"           # Needs OCR
    HANDWRITTEN = "handwritten"   # Skip for now
    MIXED = "mixed"               # Has both typed and handwritten

class MedicalDocumentProcessor:
    """
    Complete pipeline for processing Mexican medical documents
    """
    
    def __init__(self):
        # Initialize components
        self.phi_detector = SpanishMedicalPHIDetector()
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Configuration
        self.chunk_size = 20  # Lines per translation chunk
        self.max_tokens = 2000  # Safe limit for GPT-3.5
        self.ocr_lang = 'spa'  # Spanish OCR
        
        # Tracking
        self.audit_log = []
        self.processing_stats = {}
        
        print("✓ Medical Document Processor initialized")
        print("  • PHI detection: Enabled")
        print("  • OCR support: Enabled (Tesseract)")
        print("  • Translation: OpenAI GPT-3.5")
    
    def detect_page_type(self, image: Image.Image) -> PageType:
        """
        Detect the type of page content
        Uses OCR confidence and text patterns
        """
        try:
            # Get OCR data with confidence scores
            ocr_data = pytesseract.image_to_data(
                image, 
                lang=self.ocr_lang,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence for non-empty text
            confidences = [
                conf for conf, text in zip(ocr_data['conf'], ocr_data['text'])
                if text.strip() and conf > 0
            ]
            
            if not confidences:
                return PageType.HANDWRITTEN
            
            avg_confidence = sum(confidences) / len(confidences)
            
            # Decision logic
            if avg_confidence > 85:
                # High confidence = likely digital or good scan
                return PageType.DIGITAL
            elif avg_confidence > 60:
                # Medium confidence = scanned document
                return PageType.SCANNED
            elif avg_confidence > 30:
                # Low confidence = mixed or poor quality
                return PageType.MIXED
            else:
                # Very low confidence = likely handwritten
                return PageType.HANDWRITTEN
                
        except Exception as e:
            print(f"  Error detecting page type: {e}")
            return PageType.SCANNED
    
    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[str, Dict]:
        """
        Extract text from PDF, using OCR when needed
        Returns: (extracted_text, metadata)
        """
        print(f"\n📄 Processing PDF: {pdf_path}")
        
        extracted_text = []
        metadata = {
            'total_pages': 0,
            'digital_pages': 0,
            'scanned_pages': 0,
            'handwritten_pages': 0,
            'ocr_applied': False,
            'processing_time': 0
        }
        
        start_time = time.time()
        
        # First try direct text extraction
        try:
            import subprocess
            result = subprocess.run(
                ['pdftotext', pdf_path, '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and len(result.stdout.strip()) > 100:
                # Successful text extraction
                extracted_text.append(result.stdout)
                metadata['digital_pages'] = len(result.stdout.split('\f'))  # Form feeds = pages
                print(f"  ✓ Extracted text from {metadata['digital_pages']} digital pages")
            else:
                # Need OCR
                print("  ℹ Text extraction failed, using OCR...")
                metadata['ocr_applied'] = True
                
                # Convert PDF to images
                images = convert_from_path(pdf_path, dpi=200)
                metadata['total_pages'] = len(images)
                
                for i, image in enumerate(images):
                    print(f"  Processing page {i+1}/{len(images)}...")
                    
                    # Detect page type
                    page_type = self.detect_page_type(image)
                    
                    if page_type == PageType.HANDWRITTEN:
                        metadata['handwritten_pages'] += 1
                        print(f"    ⚠️ Page {i+1}: Handwritten, skipping")
                        extracted_text.append(f"\n[PAGE {i+1}: HANDWRITTEN - MANUAL REVIEW REQUIRED]\n")
                    else:
                        # Apply OCR
                        if page_type == PageType.SCANNED:
                            metadata['scanned_pages'] += 1
                        else:
                            metadata['digital_pages'] += 1
                        
                        try:
                            page_text = pytesseract.image_to_string(
                                image,
                                lang=self.ocr_lang,
                                config='--psm 6'  # Uniform block of text
                            )
                            extracted_text.append(page_text)
                            print(f"    ✓ Page {i+1}: {page_type.value}, {len(page_text)} chars")
                        except Exception as e:
                            print(f"    ❌ Page {i+1}: OCR failed - {e}")
                            extracted_text.append(f"\n[PAGE {i+1}: OCR FAILED]\n")
                            
        except Exception as e:
            print(f"  ❌ Error processing PDF: {e}")
            return "", metadata
        
        metadata['processing_time'] = time.time() - start_time
        
        # Combine all extracted text
        final_text = '\n'.join(extracted_text)
        
        print(f"\n  Summary:")
        print(f"    • Total pages: {metadata.get('total_pages', 'N/A')}")
        print(f"    • Digital pages: {metadata['digital_pages']}")
        print(f"    • Scanned pages: {metadata['scanned_pages']}")
        print(f"    • Handwritten pages: {metadata['handwritten_pages']}")
        print(f"    • Processing time: {metadata['processing_time']:.1f}s")
        print(f"    • Total text extracted: {len(final_text)} characters")
        
        return final_text, metadata
    
    def translate_with_phi_protection(self, text: str) -> Tuple[str, Dict]:
        """
        Translate text with PHI protection
        Returns: (translated_text, translation_metadata)
        """
        print("\n🔒 Applying PHI protection...")
        
        # Detect and remove PHI
        phi_matches = self.phi_detector.detect_phi(text)
        sanitized_text, phi_map = self.phi_detector.sanitize_text(text)
        
        print(f"  • Found {len(phi_matches)} PHI items")
        print(f"  • Types: {', '.join(set(m.phi_type.value for m in phi_matches))}")
        
        # Log PHI handling
        self._log_phi_handling(text, phi_matches, 'translation')
        
        # Translate sanitized text
        print("\n🌐 Translating sanitized text...")
        lines = sanitized_text.split('\n')
        translated_parts = []
        api_calls = 0
        
        for i in range(0, len(lines), self.chunk_size):
            chunk = lines[i:i+self.chunk_size]
            chunk_text = '\n'.join(chunk)
            
            if not chunk_text.strip():
                translated_parts.append(chunk_text)
                continue
            
            progress = min(100, (i + self.chunk_size) * 100 // len(lines))
            print(f"  Progress: {progress}% ({i}/{len(lines)} lines)")
            
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a medical translator specializing in Mexican Spanish to English.
                            Translate accurately, preserving all placeholders like [NAME_0], [DATE_1], etc.
                            Maintain document structure, medical terminology, and numerical values."""
                        },
                        {
                            "role": "user",
                            "content": f"Translate to English, keeping all [PLACEHOLDER_N] markers:\n\n{chunk_text}"
                        }
                    ],
                    temperature=0.1,
                    max_tokens=self.max_tokens
                )
                
                translated_parts.append(response.choices[0].message.content)
                api_calls += 1
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"  ⚠️ Translation error: {e}")
                translated_parts.append(chunk_text)  # Keep original if translation fails
        
        # Combine translated parts
        translated_sanitized = '\n'.join(translated_parts)
        
        # Restore PHI
        print("\n🔓 Restoring PHI to translated text...")
        translated_final = self.phi_detector.restore_phi(translated_sanitized, phi_map)
        
        metadata = {
            'phi_items_protected': len(phi_matches),
            'api_calls': api_calls,
            'lines_processed': len(lines)
        }
        
        return translated_final, metadata
    
    def process_document(self, input_path: str, output_dir: str = None) -> Dict:
        """
        Complete processing pipeline for medical documents
        """
        print("\n" + "="*70)
        print(f"MEDICAL DOCUMENT PROCESSING - PRODUCTION")
        print("="*70)
        
        start_time = time.time()
        
        # Determine file type and output path
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = Path('medical_records/processed')
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        output_name = input_path.stem + '_processed.txt'
        output_path = output_dir / output_name
        
        # Process based on file type
        if input_path.suffix.lower() == '.pdf':
            # Extract text from PDF (with OCR if needed)
            text, extraction_metadata = self.extract_text_from_pdf(str(input_path))
        elif input_path.suffix.lower() in ['.txt', '.text']:
            # Direct text file
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()
            extraction_metadata = {'digital_pages': 1}
        else:
            raise ValueError(f"Unsupported file type: {input_path.suffix}")
        
        if not text.strip():
            print("❌ No text extracted from document")
            return {'status': 'failed', 'reason': 'no_text_extracted'}
        
        # Translate with PHI protection
        translated_text, translation_metadata = self.translate_with_phi_protection(text)
        
        # Save output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        
        # Calculate final statistics
        total_time = time.time() - start_time
        
        # Generate processing report
        report = {
            'status': 'success',
            'input_file': str(input_path),
            'output_file': str(output_path),
            'timestamp': datetime.now().isoformat(),
            'processing_time': f"{total_time:.1f}s",
            'extraction': extraction_metadata,
            'translation': translation_metadata,
            'estimated_cost': f"${translation_metadata['api_calls'] * 0.002:.2f}",  # Rough estimate
            'audit_log': self.audit_log[-10:]  # Last 10 entries
        }
        
        # Save metadata
        metadata_path = output_path.with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print("\n" + "="*70)
        print("✅ PROCESSING COMPLETE")
        print("="*70)
        print(f"  • Output: {output_path}")
        print(f"  • Time: {total_time:.1f} seconds")
        print(f"  • PHI Protected: {translation_metadata['phi_items_protected']} items")
        print(f"  • API Calls: {translation_metadata['api_calls']}")
        print(f"  • Estimated Cost: ${translation_metadata['api_calls'] * 0.002:.2f}")
        
        if extraction_metadata.get('handwritten_pages', 0) > 0:
            print(f"  ⚠️ {extraction_metadata['handwritten_pages']} handwritten pages require manual review")
        
        return report
    
    def _log_phi_handling(self, text: str, phi_matches: List, operation: str):
        """Log PHI handling for HIPAA compliance"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'document_hash': hashlib.sha256(text.encode()).hexdigest()[:16],
            'phi_count': len(phi_matches),
            'phi_types': list(set(m.phi_type.value for m in phi_matches)),
            'user': os.getenv('USER', 'unknown'),
            'purpose': 'medical_translation'
        }
        
        self.audit_log.append(log_entry)
        
        # Also save to persistent audit log file
        audit_file = Path('audit_log.jsonl')
        with open(audit_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')


def main():
    """Test the production system"""
    print("Enfermera Elena - Production Medical Document Processor")
    print("Supports: PDF (digital & scanned), PHI protection, HIPAA compliance")
    
    processor = MedicalDocumentProcessor()
    
    # Test with the existing extracted text file
    test_file = "medical_records/extracted/mr_12_03_25_MACSMA_redacted_extracted.txt"
    
    if Path(test_file).exists():
        report = processor.process_document(test_file)
    else:
        print(f"Test file not found: {test_file}")
    
    # For PDF testing (when you have a PDF ready):
    # report = processor.process_document("path/to/medical.pdf")


if __name__ == "__main__":
    main()