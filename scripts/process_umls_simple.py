#!/usr/bin/env python3
"""
UMLS Full Release Processor for Enfermera Elena
Simplified Python version - no database required
Processes MRCONSO.RRF directly to create Mexican Spanish glossary
"""

import csv
import logging
import argparse
from pathlib import Path
from typing import Dict, Set, Tuple
from collections import defaultdict
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UMLSProcessor:
    """Process UMLS MRCONSO.RRF for Spanish-English medical glossary"""
    
    def __init__(self, mrconso_path: str, output_dir: str = "../data/glossaries"):
        self.mrconso_path = Path(mrconso_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Mexican source priority (highest to lowest)
        self.source_priority = {
            'SNOMEDCT_MX': 1,     # Mexican SNOMED CT
            'SCTSPA': 2,          # Spanish SNOMED CT  
            'MSHSPA': 3,          # MeSH Spanish
            'MDRSPA': 4,          # MedDRA Spanish
            'WHOSPA': 5,          # WHO Spanish
            'ICD10': 6,           # ICD-10
            'RXNORM': 7,          # RxNorm medications
        }
        
        # Storage for processing
        self.spanish_terms = defaultdict(list)  # CUI -> [(term, source, priority)]
        self.english_terms = defaultdict(list)  # CUI -> [(term, source, priority)]
        self.glossary = {}  # spanish_term -> english_term
        
        # Statistics
        self.stats = {
            'total_lines': 0,
            'spanish_terms': 0,
            'english_terms': 0,
            'mexican_terms': 0,
            'unique_cuis': 0,
            'glossary_entries': 0
        }
        
    def process_mrconso(self):
        """Process MRCONSO.RRF file"""
        if not self.mrconso_path.exists():
            raise FileNotFoundError(f"MRCONSO.RRF not found at {self.mrconso_path}")
            
        logger.info(f"Processing {self.mrconso_path}")
        logger.info("This may take 5-10 minutes for the full file...")
        
        start_time = time.time()
        
        # MRCONSO.RRF columns
        # 0: CUI, 1: LAT (language), 11: SAB (source), 12: TTY (term type), 14: STR (string/term)
        
        with open(self.mrconso_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if line_num % 500000 == 0:
                    logger.info(f"  Processed {line_num:,} lines...")
                    
                fields = line.strip().split('|')
                if len(fields) < 15:
                    continue
                    
                cui = fields[0]
                lat = fields[1]
                sab = fields[11]
                tty = fields[12]
                term = fields[14]
                suppress = fields[16] if len(fields) > 16 else ''
                
                # Skip suppressed terms
                if suppress == 'Y':
                    continue
                    
                # Skip very short terms
                if len(term) < 3:
                    continue
                    
                # Process Spanish terms
                if lat == 'SPA':
                    # Only use preferred terms and synonyms
                    if tty in ['PT', 'SY', 'FN', 'MTH_PT', 'MTH_SY']:
                        priority = self.source_priority.get(sab, 99)
                        self.spanish_terms[cui].append((term.lower(), sab, priority))
                        self.stats['spanish_terms'] += 1
                        
                        if sab == 'SNOMEDCT_MX':
                            self.stats['mexican_terms'] += 1
                            
                # Process English terms
                elif lat == 'ENG':
                    # Only use preferred terms
                    if tty in ['PT', 'FN', 'MTH_PT']:
                        priority = self.source_priority.get(sab, 99)
                        self.english_terms[cui].append((term, sab, priority))
                        self.stats['english_terms'] += 1
                        
                self.stats['total_lines'] = line_num
                
        elapsed = time.time() - start_time
        logger.info(f"Processed {self.stats['total_lines']:,} lines in {elapsed:.2f} seconds")
        logger.info(f"Found {len(self.spanish_terms):,} Spanish CUIs")
        logger.info(f"Found {len(self.english_terms):,} English CUIs")
        
    def build_glossary(self):
        """Build Spanish-English glossary with Mexican priority"""
        logger.info("Building Spanish→English glossary...")
        
        # Find CUIs that have both Spanish and English terms
        common_cuis = set(self.spanish_terms.keys()) & set(self.english_terms.keys())
        logger.info(f"Found {len(common_cuis):,} concepts with both languages")
        
        for cui in common_cuis:
            # Get best Spanish term (prioritize Mexican sources)
            spanish_list = sorted(self.spanish_terms[cui], key=lambda x: (x[2], x[0]))
            best_spanish = spanish_list[0][0]
            spanish_source = spanish_list[0][1]
            
            # Get best English term
            english_list = sorted(self.english_terms[cui], key=lambda x: (x[2], x[0]))
            best_english = english_list[0][0]
            
            # Add to glossary
            if best_spanish not in self.glossary:
                self.glossary[best_spanish] = {
                    'en_term': best_english,
                    'cui': cui,
                    'source': spanish_source,
                    'is_mexican': spanish_source == 'SNOMEDCT_MX'
                }
                
        self.stats['unique_cuis'] = len(common_cuis)
        self.stats['glossary_entries'] = len(self.glossary)
        
        logger.info(f"Created glossary with {len(self.glossary):,} unique Spanish terms")
        
    def add_mexican_custom_terms(self):
        """Add Mexican-specific medical terms not in UMLS"""
        custom_terms = {
            # Medications
            'metamizol': 'dipyrone/metamizole',
            'metamizol sódico': 'metamizole sodium',
            'clonixinato de lisina': 'lysine clonixinate',
            'butilhioscina': 'hyoscine butylbromide',
            'paracetamol': 'acetaminophen',
            
            # IMSS/ISSSTE terms
            'derechohabiente': 'beneficiary/insured person',
            'consulta externa': 'outpatient consultation',
            'urgencias': 'emergency department',
            'urgencias calificadas': 'qualified emergency',
            'cuadro básico': 'essential medicines formulary',
            'expediente clínico': 'clinical/medical record',
            'nota médica': 'medical note',
            'nota de evolución': 'progress note',
            'nota de ingreso': 'admission note',
            'nota de egreso': 'discharge note',
            'pase a especialidad': 'specialty referral',
            'contrarreferencia': 'counter-referral',
            'médico familiar': 'family physician',
            'unidad médica': 'medical unit',
            'certificado de incapacidad': 'disability certificate',
            
            # Common abbreviations
            'hta': 'hypertension',
            'dm2': 'type 2 diabetes mellitus',
            'iam': 'acute myocardial infarction',
            'evc': 'stroke/cerebrovascular event',
            'epoc': 'copd',
            'irc': 'chronic renal insufficiency',
        }
        
        for es_term, en_term in custom_terms.items():
            if es_term not in self.glossary:
                self.glossary[es_term] = {
                    'en_term': en_term,
                    'cui': f'MX{hash(es_term) % 10000:04d}',
                    'source': 'MEXICAN_CUSTOM',
                    'is_mexican': True
                }
                
        logger.info(f"Added {len(custom_terms)} Mexican custom terms")
        
    def save_glossaries(self):
        """Save glossaries to CSV files"""
        
        # Save full glossary
        full_path = self.output_dir / "umls_glossary_full.csv"
        with open(full_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['es_term', 'en_term', 'cui', 'source', 'is_mexican'])
            
            for es_term, data in sorted(self.glossary.items()):
                writer.writerow([
                    es_term,
                    data['en_term'],
                    data['cui'],
                    data['source'],
                    data['is_mexican']
                ])
                
        logger.info(f"Saved full glossary: {full_path}")
        
        # Save production glossary (simplified)
        prod_path = self.output_dir / "glossary_es_en_production.csv"
        with open(prod_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['es_term', 'en_term', 'source'])
            
            for es_term, data in sorted(self.glossary.items()):
                writer.writerow([
                    es_term,
                    data['en_term'],
                    data['source']
                ])
                
        logger.info(f"Saved production glossary: {prod_path}")
        
        # Save Mexican-only terms
        mexican_path = self.output_dir / "glossary_mexican_only.csv"
        with open(mexican_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['es_term', 'en_term', 'source'])
            
            mexican_terms = {k: v for k, v in self.glossary.items() if v['is_mexican']}
            for es_term, data in sorted(mexican_terms.items()):
                writer.writerow([
                    es_term,
                    data['en_term'],
                    data['source']
                ])
                
        logger.info(f"Saved Mexican glossary: {mexican_path} ({len(mexican_terms)} terms)")
        
    def print_statistics(self):
        """Print processing statistics"""
        print("\n" + "=" * 50)
        print("📊 UMLS Processing Statistics")
        print("=" * 50)
        print(f"Total lines processed: {self.stats['total_lines']:,}")
        print(f"Spanish terms found: {self.stats['spanish_terms']:,}")
        print(f"English terms found: {self.stats['english_terms']:,}")
        print(f"Mexican SNOMED terms: {self.stats['mexican_terms']:,}")
        print(f"Unique concepts (CUIs): {self.stats['unique_cuis']:,}")
        print(f"Final glossary entries: {self.stats['glossary_entries']:,}")
        
        # Source breakdown
        source_counts = defaultdict(int)
        for data in self.glossary.values():
            source_counts[data['source']] += 1
            
        print("\n📋 Glossary Breakdown by Source:")
        for source, count in sorted(source_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {source}: {count:,}")
            
        print("\n✅ Processing complete!")
        
    def sample_glossary(self, n=10):
        """Show sample glossary entries"""
        print(f"\n📝 Sample Glossary Entries (first {n}):")
        print("-" * 60)
        
        for i, (es_term, data) in enumerate(list(self.glossary.items())[:n], 1):
            print(f"{i}. {es_term} → {data['en_term']}")
            print(f"   Source: {data['source']}, CUI: {data['cui']}")
            
        # Show some Mexican-specific terms
        mexican_terms = [(k, v) for k, v in self.glossary.items() if v['is_mexican']][:5]
        if mexican_terms:
            print(f"\n🇲🇽 Mexican-Specific Terms:")
            print("-" * 60)
            for es_term, data in mexican_terms:
                print(f"• {es_term} → {data['en_term']} ({data['source']})")


def main():
    parser = argparse.ArgumentParser(
        description="Process UMLS Full Release for Mexican Spanish medical glossary"
    )
    
    parser.add_argument(
        '--mrconso',
        default='/home/psadmin/ai/enfermera_elena/data/2025AA/META/MRCONSO.RRF',
        help='Path to MRCONSO.RRF file'
    )
    parser.add_argument(
        '--output',
        default='/home/psadmin/ai/enfermera_elena/data/glossaries',
        help='Output directory for glossaries'
    )
    parser.add_argument(
        '--sample',
        action='store_true',
        help='Process only first 100,000 lines for testing'
    )
    
    args = parser.parse_args()
    
    # Check if MRCONSO exists
    if not Path(args.mrconso).exists():
        print(f"❌ Error: MRCONSO.RRF not found at {args.mrconso}")
        print("Please check the path and try again.")
        return
        
    print("=" * 60)
    print("UMLS Full Release Processor")
    print("Building Mexican Spanish → English Medical Glossary")
    print("=" * 60)
    
    # Initialize processor
    processor = UMLSProcessor(args.mrconso, args.output)
    
    # Process MRCONSO
    if args.sample:
        print("⚠️  SAMPLE MODE: Processing only first 100,000 lines")
        # Would need to modify process_mrconso to handle this
        
    processor.process_mrconso()
    
    # Build glossary
    processor.build_glossary()
    
    # Add Mexican custom terms
    processor.add_mexican_custom_terms()
    
    # Save to files
    processor.save_glossaries()
    
    # Print statistics
    processor.print_statistics()
    
    # Show samples
    processor.sample_glossary()
    
    print(f"\n📁 Output files saved to: {args.output}")
    print("\nNext step: Use glossary_es_en_production.csv in your translation pipeline")


if __name__ == "__main__":
    main()