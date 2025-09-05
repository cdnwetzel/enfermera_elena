#!/usr/bin/env python3
"""
Quick Test Script for Enfermera Elena
Test with first few pages while UMLS processes
"""

import sys
import logging
from pathlib import Path

# Simple test without full UMLS (uses seed glossary)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_basic_pipeline():
    """Test basic pipeline components"""
    print("=" * 60)
    print("Enfermera Elena - Quick Component Test")
    print("=" * 60)
    
    # Check for PDF file
    pdf_files = list(Path(".").glob("*.pdf"))
    if not pdf_files:
        pdf_files = list(Path("data").glob("*.pdf")) if Path("data").exists() else []
        
    if pdf_files:
        print(f"✅ Found {len(pdf_files)} PDF files")
        test_pdf = pdf_files[0]
        print(f"   Using: {test_pdf}")
    else:
        print("⚠️  No PDF files found in current directory")
        print("   Place your 87-page PDF here to test")
        return
        
    # Check for glossary
    glossary_paths = [
        Path("data/glossaries/glossary_es_en_production.csv"),
        Path("data/glossaries/seed_glossary.csv"),
    ]
    
    glossary = None
    for path in glossary_paths:
        if path.exists():
            glossary = path
            print(f"✅ Found glossary: {glossary}")
            break
            
    if not glossary:
        print("⚠️  No glossary found. Creating seed glossary...")
        # Generate seed glossary
        from scripts.generate_seed_glossary import SeedGlossaryGenerator
        gen = SeedGlossaryGenerator()
        gen.generate_full_glossary()
        glossary = Path("data/glossaries/seed_glossary.csv")
        print(f"✅ Created seed glossary: {glossary}")
        
    # Test PDF text extraction
    print("\n📄 Testing PDF text extraction...")
    try:
        import pdfplumber
        
        with pdfplumber.open(test_pdf) as pdf:
            num_pages = len(pdf.pages)
            print(f"   Total pages: {num_pages}")
            
            # Check first page
            first_page_text = pdf.pages[0].extract_text()
            if first_page_text:
                print(f"   Page 1: {len(first_page_text)} chars extracted")
                print(f"   Sample: {first_page_text[:100]}...")
            else:
                print("   Page 1: No text (likely scanned)")
                
    except Exception as e:
        print(f"❌ PDF extraction failed: {e}")
        
    # Test translation backend
    print("\n🔤 Testing translation backend...")
    
    # Check LibreTranslate
    import requests
    try:
        response = requests.get("http://localhost:5000/languages", timeout=2)
        if response.status_code == 200:
            print("✅ LibreTranslate is running")
        else:
            print("⚠️  LibreTranslate not responding")
    except:
        print("⚠️  LibreTranslate not available")
        print("   Start with: docker run -p 5000:5000 libretranslate/libretranslate")
        
    # Show next steps
    print("\n" + "=" * 60)
    print("📋 Next Steps:")
    print("=" * 60)
    print("1. Wait for UMLS processing to complete (~5-10 minutes)")
    print("2. Start LibreTranslate if not running:")
    print("   docker run -d -p 5000:5000 libretranslate/libretranslate --load-only es,en")
    print("3. Process your PDF:")
    print(f"   python process_medical_pdf.py {test_pdf} --sample")
    print("   (--sample processes only first 5 pages for testing)")


if __name__ == "__main__":
    test_basic_pipeline()