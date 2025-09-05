#!/usr/bin/env python3
"""
Medical Record Processing Pipeline for Enfermera Elena
Handles extraction, translation, and quality analysis for single or batch processing
"""

import os
import sys
import subprocess
import argparse
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import csv


class MedicalRecordProcessor:
    """Process medical records through the full pipeline"""
    
    def __init__(self, verbose: bool = False, mode: str = "sequential"):
        """
        Initialize processor
        
        Args:
            verbose: Print detailed progress
            mode: "sequential" (extract→translate one at a time) or 
                  "batch" (extract all, then translate all)
        """
        self.verbose = verbose
        self.mode = mode
        self.glossary = None
        self.results = []
        
        # Directory structure
        self.dirs = {
            'original': Path('medical_records/original'),
            'extracted': Path('medical_records/extracted'),
            'translated': Path('medical_records/translated'),
            'quality': Path('medical_records/quality')
        }
        
        # Ensure directories exist
        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
            
    def log(self, message: str, level: str = "INFO"):
        """Print log message if verbose"""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")
            
    def extract_text(self, pdf_path: Path) -> Optional[Path]:
        """
        Extract text from PDF using pdftotext
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Path to extracted text file or None if failed
        """
        # Generate output filename
        base_name = pdf_path.stem
        output_path = self.dirs['extracted'] / f"{base_name}_extracted.txt"
        
        self.log(f"Extracting: {pdf_path.name}")
        
        # Run pdftotext with layout preservation
        cmd = ['pdftotext', '-layout', str(pdf_path), str(output_path)]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Verify output file exists and has content
            if output_path.exists() and output_path.stat().st_size > 0:
                self.log(f"  ✓ Extracted to: {output_path.name}")
                return output_path
            else:
                self.log(f"  ✗ Extraction produced empty file", "ERROR")
                return None
                
        except subprocess.CalledProcessError as e:
            self.log(f"  ✗ Extraction failed: {e.stderr}", "ERROR")
            return None
            
    def translate_document(self, text_path: Path) -> Optional[Path]:
        """
        Translate extracted text document
        
        Args:
            text_path: Path to extracted text file
            
        Returns:
            Path to translated file or None if failed
        """
        # Load glossary if not already loaded
        if self.glossary is None:
            self.load_glossary()
            
        # Generate output filename
        base_name = text_path.stem.replace('_extracted', '')
        output_path = self.dirs['translated'] / f"{base_name}_translated.txt"
        
        self.log(f"Translating: {text_path.name}")
        
        # Read original text
        with open(text_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
            
        # Import and use the translation function
        from translate_medical_record import translate_medical_document
        
        try:
            translated = translate_medical_document(original_text, self.glossary)
            
            # Save translation
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated)
                
            self.log(f"  ✓ Translated to: {output_path.name}")
            return output_path
            
        except Exception as e:
            self.log(f"  ✗ Translation failed: {str(e)}", "ERROR")
            return None
            
    def analyze_quality(self, original_path: Path, translated_path: Path) -> Optional[Dict]:
        """
        Analyze translation quality
        
        Args:
            original_path: Path to original extracted text
            translated_path: Path to translated text
            
        Returns:
            Quality metrics dictionary or None if failed
        """
        self.log(f"Analyzing quality: {translated_path.name}")
        
        # Import analyzer
        from translation_quality_analyzer import TranslationQualityAnalyzer
        
        try:
            # Load files
            with open(original_path, 'r', encoding='utf-8') as f:
                original_text = f.read()
            with open(translated_path, 'r', encoding='utf-8') as f:
                translated_text = f.read()
                
            # Analyze
            analyzer = TranslationQualityAnalyzer()
            analysis = analyzer.analyze_translation(original_text, translated_text)
            
            # Save quality report
            base_name = translated_path.stem.replace('_translated', '')
            quality_path = self.dirs['quality'] / f"{base_name}_quality.json"
            
            # Extract overall confidence from analysis
            overall_confidence = analysis.get('total_confidence', 0.75)
            
            # Create summary for JSON
            quality_data = {
                'file': base_name,
                'timestamp': datetime.now().isoformat(),
                'overall_confidence': overall_confidence,
                'statistics': analysis.get('statistics', {}),
                'critical_issues': len(analysis.get('critical_issues', [])),
                'warnings': len(analysis.get('warnings', []))
            }
            
            with open(quality_path, 'w', encoding='utf-8') as f:
                json.dump(quality_data, f, indent=2)
                
            self.log(f"  ✓ Quality score: {overall_confidence:.1%}")
            return quality_data
            
        except Exception as e:
            import traceback
            self.log(f"  ✗ Quality analysis failed: {str(e)}", "ERROR")
            if self.verbose:
                print(traceback.format_exc())
            return None
            
    def load_glossary(self):
        """Load UMLS glossary for translation"""
        # Use comprehensive glossary if available
        from pathlib import Path
        glossary_path = "data/glossaries/glossary_comprehensive.csv"
        if not Path(glossary_path).exists():
            glossary_path = "data/glossaries/glossary_es_en_production.csv"
        self.log(f"Loading glossary: {glossary_path}")
        
        self.glossary = {}
        with open(glossary_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row['es_term'].lower()
                en_term = row['en_term']
                self.glossary[es_term] = en_term
                
        self.log(f"  Loaded {len(self.glossary)} terms")
        
    def process_single(self, pdf_path: Path) -> Dict:
        """
        Process a single PDF through the entire pipeline
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Processing results dictionary
        """
        result = {
            'file': pdf_path.name,
            'status': 'started',
            'extracted': None,
            'translated': None,
            'quality': None,
            'errors': []
        }
        
        # Step 1: Extract
        extracted_path = self.extract_text(pdf_path)
        if extracted_path:
            result['extracted'] = str(extracted_path)
            
            # Step 2: Translate
            translated_path = self.translate_document(extracted_path)
            if translated_path:
                result['translated'] = str(translated_path)
                
                # Step 3: Analyze quality
                quality = self.analyze_quality(extracted_path, translated_path)
                if quality:
                    result['quality'] = quality
                    result['status'] = 'completed'
                else:
                    result['status'] = 'quality_failed'
                    result['errors'].append('Quality analysis failed')
            else:
                result['status'] = 'translation_failed'
                result['errors'].append('Translation failed')
        else:
            result['status'] = 'extraction_failed'
            result['errors'].append('Text extraction failed')
            
        return result
        
    def process_batch(self, pdf_files: List[Path]) -> List[Dict]:
        """
        Process multiple PDFs
        
        Args:
            pdf_files: List of PDF file paths
            
        Returns:
            List of processing results
        """
        results = []
        
        if self.mode == "sequential":
            # Process each file completely before moving to next
            for i, pdf_path in enumerate(pdf_files, 1):
                print(f"\n{'='*60}")
                print(f"Processing file {i}/{len(pdf_files)}: {pdf_path.name}")
                print('='*60)
                
                result = self.process_single(pdf_path)
                results.append(result)
                
                if result['status'] == 'completed':
                    print(f"✅ Success: Confidence {result['quality']['overall_confidence']:.1%}")
                else:
                    print(f"❌ Failed: {result['status']}")
                    
        else:  # batch mode
            # Extract all first
            print(f"\n{'='*60}")
            print("PHASE 1: Extracting all PDFs")
            print('='*60)
            
            extracted_files = []
            for i, pdf_path in enumerate(pdf_files, 1):
                print(f"\n[{i}/{len(pdf_files)}] {pdf_path.name}")
                extracted = self.extract_text(pdf_path)
                if extracted:
                    extracted_files.append((pdf_path, extracted))
                    
            # Then translate all
            print(f"\n{'='*60}")
            print("PHASE 2: Translating all documents")
            print('='*60)
            
            translated_files = []
            for i, (pdf_path, extracted_path) in enumerate(extracted_files, 1):
                print(f"\n[{i}/{len(extracted_files)}] {extracted_path.name}")
                translated = self.translate_document(extracted_path)
                if translated:
                    translated_files.append((pdf_path, extracted_path, translated))
                    
            # Finally analyze quality for all
            print(f"\n{'='*60}")
            print("PHASE 3: Analyzing translation quality")
            print('='*60)
            
            for i, (pdf_path, extracted_path, translated_path) in enumerate(translated_files, 1):
                print(f"\n[{i}/{len(translated_files)}] {translated_path.name}")
                quality = self.analyze_quality(extracted_path, translated_path)
                
                result = {
                    'file': pdf_path.name,
                    'status': 'completed' if quality else 'quality_failed',
                    'extracted': str(extracted_path),
                    'translated': str(translated_path),
                    'quality': quality,
                    'errors': [] if quality else ['Quality analysis failed']
                }
                results.append(result)
                
        return results
        
    def generate_summary_report(self, results: List[Dict]) -> None:
        """
        Generate summary report of batch processing
        
        Args:
            results: List of processing results
        """
        print(f"\n{'='*60}")
        print("PROCESSING SUMMARY")
        print('='*60)
        
        # Count statuses
        completed = sum(1 for r in results if r['status'] == 'completed')
        failed = len(results) - completed
        
        print(f"\nTotal files processed: {len(results)}")
        print(f"✅ Successful: {completed}")
        print(f"❌ Failed: {failed}")
        
        if completed > 0:
            # Calculate average confidence
            confidences = [r['quality']['overall_confidence'] 
                          for r in results 
                          if r['status'] == 'completed']
            avg_confidence = sum(confidences) / len(confidences)
            
            print(f"\nAverage confidence score: {avg_confidence:.1%}")
            print(f"Highest confidence: {max(confidences):.1%}")
            print(f"Lowest confidence: {min(confidences):.1%}")
            
        if failed > 0:
            print("\nFailed files:")
            for r in results:
                if r['status'] != 'completed':
                    print(f"  - {r['file']}: {r['status']}")
                    
        # Save summary to file
        summary_path = self.dirs['quality'] / 'batch_summary.json'
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_files': len(results),
                'completed': completed,
                'failed': failed,
                'results': results
            }, f, indent=2)
            
        print(f"\n📊 Detailed summary saved to: {summary_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Process medical records through extraction, translation, and quality analysis'
    )
    
    parser.add_argument(
        'input',
        nargs='+',
        help='PDF file(s) to process or directory containing PDFs'
    )
    
    parser.add_argument(
        '--mode',
        choices=['sequential', 'batch'],
        default='sequential',
        help='Processing mode: sequential (complete each file) or batch (phase-based)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed progress'
    )
    
    parser.add_argument(
        '--output-dir',
        help='Custom output directory (default: medical_records/)'
    )
    
    args = parser.parse_args()
    
    # Collect PDF files
    pdf_files = []
    for input_path in args.input:
        path = Path(input_path)
        
        if path.is_file() and path.suffix.lower() == '.pdf':
            pdf_files.append(path)
        elif path.is_dir():
            # Find all PDFs in directory
            pdfs = list(path.glob('*.pdf')) + list(path.glob('*.PDF'))
            pdf_files.extend(pdfs)
        else:
            print(f"Warning: Skipping {input_path} (not a PDF or directory)")
            
    if not pdf_files:
        print("Error: No PDF files found to process")
        sys.exit(1)
        
    print(f"Found {len(pdf_files)} PDF file(s) to process")
    
    # Initialize processor
    processor = MedicalRecordProcessor(verbose=args.verbose, mode=args.mode)
    
    # Process files
    if len(pdf_files) == 1:
        # Single file
        result = processor.process_single(pdf_files[0])
        
        print(f"\n{'='*60}")
        print("PROCESSING COMPLETE")
        print('='*60)
        
        if result['status'] == 'completed':
            print(f"✅ Success!")
            print(f"   Extracted: {result['extracted']}")
            print(f"   Translated: {result['translated']}")
            print(f"   Confidence: {result['quality']['overall_confidence']:.1%}")
        else:
            print(f"❌ Failed: {result['status']}")
            if result['errors']:
                print(f"   Errors: {', '.join(result['errors'])}")
    else:
        # Batch processing
        results = processor.process_batch(pdf_files)
        processor.generate_summary_report(results)


if __name__ == "__main__":
    main()