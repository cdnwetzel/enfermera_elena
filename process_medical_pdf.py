#!/usr/bin/env python3
"""
End-to-End Medical PDF Processing Pipeline for Enfermera Elena
Processes 87-page Mexican medical PDFs with UMLS Full Release glossary
"""

import os
import sys
import logging
import argparse
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Import our modules
from pdf.extractor import extract_page_texts
from pdf.classifier import classify_pages
from ocr.tesseract import TesseractOCREngine
from deid.rules_mexico import MexicanPHIDeidentifier
from mt.libretranslate_adapter import LibreTranslateAdapter
from mt.alia_adapter import ALIAMedicalTranslator
from reid.reinserter import PHIReinserter
from pdf.writer import PDFWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MedicalPDFProcessor:
    """
    Complete pipeline for processing Mexican medical PDFs
    Using UMLS Full Release glossary for accurate translation
    """
    
    def __init__(self, 
                 umls_glossary_path: str,
                 translation_backend: str = "libretranslate",
                 use_ocr: bool = True,
                 max_pages: Optional[int] = None):
        """
        Initialize the processor
        
        Args:
            umls_glossary_path: Path to UMLS glossary CSV
            translation_backend: 'libretranslate', 'alia', or 'openai'
            use_ocr: Whether to OCR scanned pages
            max_pages: Maximum pages to process (None for all)
        """
        self.umls_glossary_path = Path(umls_glossary_path)
        self.translation_backend = translation_backend
        self.use_ocr = use_ocr
        self.max_pages = max_pages
        
        # Validate glossary exists
        if not self.umls_glossary_path.exists():
            logger.warning(f"UMLS glossary not found at {umls_glossary_path}")
            logger.info("Run process_umls_full_release.sh first to generate glossary")
            
        # Initialize components
        self.init_components()
        
    def init_components(self):
        """Initialize pipeline components"""
        
        # OCR engine for scanned pages
        if self.use_ocr:
            self.ocr = TesseractOCREngine()
            
        # PHI de-identification
        self.deid = MexicanPHIDeidentifier()
        
        # Translation with UMLS glossary
        if self.translation_backend == "alia":
            self.translator = ALIAMedicalTranslator(
                glossary_path=str(self.umls_glossary_path)
            )
        elif self.translation_backend == "openai":
            from mt.openai_adapter import OpenAISecureAdapter
            self.translator = OpenAISecureAdapter(
                glossary_path=str(self.umls_glossary_path),
                validate_phi=True
            )
        else:  # Default to LibreTranslate
            self.translator = LibreTranslateAdapter(
                glossary_path=str(self.umls_glossary_path)
            )
            
        # PHI re-insertion
        self.reid = PHIReinserter()
        
        # PDF writer
        self.pdf_writer = PDFWriter()
        
        logger.info(f"Pipeline initialized with {self.translation_backend} backend")
        
    def process_pdf(self, 
                   input_path: str,
                   output_path: str) -> Dict:
        """
        Process complete PDF through pipeline
        
        Args:
            input_path: Path to input PDF
            output_path: Path to output translated PDF
            
        Returns:
            Processing statistics
        """
        start_time = time.time()
        stats = {
            'input_file': input_path,
            'output_file': output_path,
            'pages_processed': 0,
            'pages_ocr': 0,
            'pages_digital': 0,
            'phi_tokens_found': 0,
            'translation_time': 0,
            'total_time': 0,
            'errors': []
        }
        
        try:
            logger.info(f"Processing PDF: {input_path}")
            
            # Step 1: Extract and classify pages
            logger.info("Step 1: Extracting and classifying pages...")
            page_texts = extract_page_texts(input_path, self.max_pages)
            page_types = classify_pages(input_path, self.max_pages)
            
            stats['pages_processed'] = len(page_texts)
            stats['pages_digital'] = sum(1 for t in page_types if t == 'digital')
            stats['pages_ocr'] = sum(1 for t in page_types if t == 'scanned')
            
            logger.info(f"  Found {stats['pages_processed']} pages")
            logger.info(f"  Digital: {stats['pages_digital']}, Scanned: {stats['pages_ocr']}")
            
            # Step 2: OCR scanned pages if needed
            if self.use_ocr and stats['pages_ocr'] > 0:
                logger.info("Step 2: OCR processing scanned pages...")
                
                for i, page_type in enumerate(page_types):
                    if page_type == 'scanned':
                        logger.info(f"  OCR page {i+1}...")
                        # OCR this page
                        ocr_text = self.ocr.ocr_page(input_path, i)
                        page_texts[i] = ocr_text
            else:
                logger.info("Step 2: OCR skipped (no scanned pages or OCR disabled)")
                
            # Step 3: De-identify PHI
            logger.info("Step 3: De-identifying PHI...")
            deidentified_texts = []
            phi_mappings = []
            
            for i, text in enumerate(page_texts):
                if text.strip():
                    deid_text, phi_map = self.deid.deidentify(text)
                    deidentified_texts.append(deid_text)
                    phi_mappings.append(phi_map)
                    stats['phi_tokens_found'] += len(phi_map)
                else:
                    deidentified_texts.append('')
                    phi_mappings.append({})
                    
            logger.info(f"  Found and replaced {stats['phi_tokens_found']} PHI tokens")
            
            # Step 4: Translate with UMLS glossary
            logger.info("Step 4: Translating with UMLS medical glossary...")
            trans_start = time.time()
            translated_texts = []
            
            # Process in batches for efficiency
            batch_size = 5
            for i in range(0, len(deidentified_texts), batch_size):
                batch = deidentified_texts[i:i+batch_size]
                logger.info(f"  Translating pages {i+1}-{min(i+batch_size, len(deidentified_texts))}...")
                
                if self.translation_backend == "alia":
                    # ALIA handles batches natively
                    batch_translated = self.translator.translate_batch(
                        batch,
                        mode='medical'
                    )
                else:
                    # Other backends process one by one
                    batch_translated = []
                    for text in batch:
                        if text.strip():
                            translated = self.translator.translate(text)
                            batch_translated.append(translated)
                        else:
                            batch_translated.append('')
                            
                translated_texts.extend(batch_translated)
                
            stats['translation_time'] = time.time() - trans_start
            logger.info(f"  Translation completed in {stats['translation_time']:.2f} seconds")
            
            # Step 5: Re-insert PHI
            logger.info("Step 5: Re-inserting PHI tokens...")
            final_texts = []
            
            for i, (translated, phi_map) in enumerate(zip(translated_texts, phi_mappings)):
                if translated and phi_map:
                    final_text = self.reid.reinsert(translated, phi_map)
                    final_texts.append(final_text)
                else:
                    final_texts.append(translated)
                    
            # Step 6: Generate output PDF
            logger.info("Step 6: Generating output PDF...")
            self.pdf_writer.create_pdf(
                final_texts,
                output_path,
                source_pdf=input_path,
                metadata={
                    'Title': 'Medical Document (Translated)',
                    'Subject': 'Spanish to English Medical Translation',
                    'Creator': 'Enfermera Elena',
                    'Producer': 'UMLS Full Release Glossary'
                }
            )
            
            stats['total_time'] = time.time() - start_time
            
            logger.info(f"✅ Processing complete!")
            logger.info(f"  Output: {output_path}")
            logger.info(f"  Total time: {stats['total_time']:.2f} seconds")
            logger.info(f"  Pages/minute: {(stats['pages_processed'] * 60 / stats['total_time']):.1f}")
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            stats['errors'].append(str(e))
            raise
            
        return stats
        
    def process_batch(self, pdf_files: List[str], output_dir: str) -> List[Dict]:
        """
        Process multiple PDFs
        
        Args:
            pdf_files: List of input PDF paths
            output_dir: Directory for output files
            
        Returns:
            List of processing statistics
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        all_stats = []
        
        for pdf_file in pdf_files:
            input_path = Path(pdf_file)
            output_path = Path(output_dir) / f"{input_path.stem}_translated.pdf"
            
            logger.info(f"\nProcessing {input_path.name}...")
            stats = self.process_pdf(str(input_path), str(output_path))
            all_stats.append(stats)
            
        return all_stats


class UMLSGlossaryValidator:
    """Validate UMLS glossary coverage for a document"""
    
    def __init__(self, glossary_path: str):
        self.glossary = self.load_glossary(glossary_path)
        
    def load_glossary(self, path: str) -> Dict[str, str]:
        """Load UMLS glossary"""
        import csv
        glossary = {}
        
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row['es_term'].lower()
                en_term = row['en_term']
                glossary[es_term] = en_term
                
        return glossary
        
    def check_coverage(self, spanish_text: str) -> Dict:
        """Check how many medical terms are covered by glossary"""
        import re
        
        # Extract potential medical terms (multi-word and single)
        words = re.findall(r'\b[a-záéíóúñ]+\b', spanish_text.lower())
        
        # Also check 2-word and 3-word phrases
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
        trigrams = [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words)-2)]
        
        all_terms = words + bigrams + trigrams
        
        covered = []
        not_covered = []
        
        for term in all_terms:
            if term in self.glossary:
                covered.append(term)
            elif len(term) > 4:  # Only track longer uncovered terms
                not_covered.append(term)
                
        # Remove duplicates
        covered = list(set(covered))
        not_covered = list(set(not_covered))
        
        return {
            'total_terms': len(set(all_terms)),
            'covered_terms': len(covered),
            'coverage_rate': len(covered) / len(set(all_terms)) if all_terms else 0,
            'sample_covered': covered[:10],
            'sample_not_covered': not_covered[:10]
        }


def main():
    parser = argparse.ArgumentParser(
        description="Process Mexican medical PDFs with UMLS Full Release glossary"
    )
    
    parser.add_argument(
        'input',
        help='Input PDF file or directory'
    )
    parser.add_argument(
        '-o', '--output',
        default='output',
        help='Output file or directory'
    )
    parser.add_argument(
        '--glossary',
        default='data/glossaries/glossary_es_en_production.csv',
        help='Path to UMLS glossary CSV'
    )
    parser.add_argument(
        '--backend',
        choices=['libretranslate', 'alia', 'openai'],
        default='libretranslate',
        help='Translation backend to use'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        help='Maximum pages to process (default: all)'
    )
    parser.add_argument(
        '--no-ocr',
        action='store_true',
        help='Skip OCR for scanned pages'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate glossary coverage only'
    )
    parser.add_argument(
        '--sample',
        action='store_true',
        help='Process only first 5 pages as sample'
    )
    
    args = parser.parse_args()
    
    # If validate mode, just check coverage
    if args.validate:
        print("Validating UMLS glossary coverage...")
        validator = UMLSGlossaryValidator(args.glossary)
        
        # Extract text from PDF for validation
        texts = extract_page_texts(args.input, max_pages=5)
        sample_text = '\n'.join(texts)
        
        coverage = validator.check_coverage(sample_text)
        print(f"\nGlossary Coverage Analysis:")
        print(f"  Total terms analyzed: {coverage['total_terms']}")
        print(f"  Terms in glossary: {coverage['covered_terms']}")
        print(f"  Coverage rate: {coverage['coverage_rate']*100:.1f}%")
        print(f"\n  Sample covered terms: {', '.join(coverage['sample_covered'][:5])}")
        print(f"  Sample uncovered terms: {', '.join(coverage['sample_not_covered'][:5])}")
        return
        
    # Sample mode - process only first 5 pages
    if args.sample:
        args.max_pages = 5
        print("SAMPLE MODE: Processing first 5 pages only")
        
    # Initialize processor
    processor = MedicalPDFProcessor(
        umls_glossary_path=args.glossary,
        translation_backend=args.backend,
        use_ocr=not args.no_ocr,
        max_pages=args.max_pages
    )
    
    # Process input
    input_path = Path(args.input)
    
    if input_path.is_file():
        # Single PDF
        output_path = args.output
        if not output_path.endswith('.pdf'):
            output_path = Path(args.output) / f"{input_path.stem}_translated.pdf"
            
        print(f"\nProcessing: {input_path}")
        print(f"Output: {output_path}")
        print(f"Using: {args.backend} backend with UMLS glossary")
        print("-" * 50)
        
        stats = processor.process_pdf(str(input_path), str(output_path))
        
        # Print summary
        print("\n" + "=" * 50)
        print("PROCESSING COMPLETE")
        print("=" * 50)
        print(f"Pages processed: {stats['pages_processed']}")
        print(f"  - Digital text: {stats['pages_digital']}")
        print(f"  - OCR required: {stats['pages_ocr']}")
        print(f"PHI tokens found: {stats['phi_tokens_found']}")
        print(f"Translation time: {stats['translation_time']:.2f}s")
        print(f"Total time: {stats['total_time']:.2f}s")
        print(f"Speed: {stats['pages_processed'] * 60 / stats['total_time']:.1f} pages/min")
        
        if stats['errors']:
            print(f"\n⚠️ Errors: {stats['errors']}")
        else:
            print(f"\n✅ Success! Output: {output_path}")
            
    else:
        # Directory of PDFs
        pdf_files = list(input_path.glob('*.pdf'))
        print(f"Found {len(pdf_files)} PDF files to process")
        
        all_stats = processor.process_batch(
            [str(f) for f in pdf_files],
            args.output
        )
        
        # Print summary
        print("\n" + "=" * 50)
        print("BATCH PROCESSING COMPLETE")
        print("=" * 50)
        print(f"Files processed: {len(all_stats)}")
        
        total_pages = sum(s['pages_processed'] for s in all_stats)
        total_time = sum(s['total_time'] for s in all_stats)
        
        print(f"Total pages: {total_pages}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Average speed: {total_pages * 60 / total_time:.1f} pages/min")
        
        errors = [s for s in all_stats if s['errors']]
        if errors:
            print(f"\n⚠️ Files with errors: {len(errors)}")
        else:
            print(f"\n✅ All files processed successfully!")


if __name__ == "__main__":
    main()