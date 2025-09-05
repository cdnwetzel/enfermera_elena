#!/usr/bin/env python3
"""
Enhanced UMLS Glossary Generator for Enfermera Elena
Creates multiple glossary levels:
1. Single words
2. Short phrases (2-3 words)
3. Full medical phrases
4. Abbreviations and acronyms
"""

import csv
import re
from collections import defaultdict
from pathlib import Path
import time


class EnhancedGlossaryBuilder:
    def __init__(self, mrconso_path: str):
        self.mrconso_path = mrconso_path
        self.single_words = {}  # Single word translations
        self.short_phrases = {}  # 2-3 word phrases
        self.full_phrases = {}  # Complete medical phrases
        self.abbreviations = {}  # Medical abbreviations
        
        # Priority sources for Mexican Spanish
        self.priority_sources = ['SCTSPA', 'MSHSPA', 'MDRSPA']
        
    def process_umls(self):
        """Process UMLS to extract all levels of terms"""
        print("Processing UMLS for enhanced glossary...")
        start_time = time.time()
        
        # Track terms by CUI for cross-referencing
        cui_terms = defaultdict(lambda: {'es': [], 'en': []})
        
        line_count = 0
        with open(self.mrconso_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_count += 1
                if line_count % 1000000 == 0:
                    print(f"  Processed {line_count/1000000:.0f}M lines...")
                    
                fields = line.strip().split('|')
                if len(fields) < 15:
                    continue
                    
                cui = fields[0]
                lat = fields[1]  # Language
                sab = fields[11]  # Source
                tty = fields[12]  # Term type
                term = fields[14]  # The actual term
                
                # Store Spanish and English terms by CUI
                if lat == 'SPA' and sab in self.priority_sources:
                    cui_terms[cui]['es'].append(term)
                elif lat == 'ENG':
                    cui_terms[cui]['en'].append(term)
                    
        print(f"  Found {len(cui_terms)} unique concepts")
        
        # Create translations at different levels
        for cui, terms in cui_terms.items():
            if not terms['es'] or not terms['en']:
                continue
                
            # Get the shortest/simplest terms for each language
            es_terms = sorted(terms['es'], key=len)
            en_terms = sorted(terms['en'], key=len)
            
            for es_term in es_terms[:3]:  # Take up to 3 variations
                es_lower = es_term.lower()
                en_term = en_terms[0]  # Use shortest English equivalent
                
                # Categorize by length/complexity
                es_words = es_lower.split()
                
                if len(es_words) == 1:
                    # Single word
                    if len(es_lower) > 2:  # Skip very short words
                        self.single_words[es_lower] = en_term
                        
                elif len(es_words) <= 3:
                    # Short phrase
                    self.short_phrases[es_lower] = en_term
                    # Also add individual important words
                    for word in es_words:
                        if len(word) > 4 and word not in ['para', 'con', 'sin', 'por']:
                            if word not in self.single_words:
                                # Try to find English equivalent for single word
                                self.single_words[word] = self.extract_key_word(en_term)
                                
                else:
                    # Full phrase
                    self.full_phrases[es_lower] = en_term
                    
                # Check for abbreviations (all caps or contains numbers)
                if es_term.isupper() or re.search(r'\d', es_term):
                    self.abbreviations[es_term] = en_term
                    
        elapsed = time.time() - start_time
        print(f"Processing completed in {elapsed:.1f} seconds")
        print(f"  Single words: {len(self.single_words)}")
        print(f"  Short phrases: {len(self.short_phrases)}")
        print(f"  Full phrases: {len(self.full_phrases)}")
        print(f"  Abbreviations: {len(self.abbreviations)}")
        
    def extract_key_word(self, phrase: str) -> str:
        """Extract the key medical word from an English phrase"""
        # Remove common words
        stop_words = {'the', 'of', 'and', 'or', 'via', 'with', 'for', 'by', 'to', 'in'}
        words = phrase.split()
        key_words = [w for w in words if w.lower() not in stop_words]
        return key_words[0] if key_words else phrase
        
    def add_common_medical_terms(self):
        """Add common medical terms not in UMLS or needing specific translations"""
        common_terms = {
            # Departments
            'imagenologia': 'imaging',
            'imagenología': 'imaging',
            'inhaloterapia': 'respiratory therapy',
            'laboratorio': 'laboratory',
            'farmacia': 'pharmacy',
            'urgencias': 'emergency',
            'urgencia': 'emergency',
            'hospitalización': 'hospitalization',
            'hospitalizacion': 'hospitalization',
            
            # Common procedures
            'tomografia': 'CT scan',
            'tomografía': 'CT scan',
            'radiografia': 'X-ray',
            'radiografía': 'X-ray',
            'resonancia': 'MRI',
            'ultrasonido': 'ultrasound',
            'electrocardiograma': 'electrocardiogram',
            
            # Document terms
            'fecha': 'date',
            'descripción': 'description',
            'descripcion': 'description',
            'cantidad': 'quantity',
            'importe': 'amount',
            'subtotal': 'subtotal',
            'total': 'total',
            'servicio': 'service',
            'cargos': 'charges',
            'cargo': 'charge',
            'detallado': 'detailed',
            
            # Medical terms
            'oxigeno': 'oxygen',
            'oxígeno': 'oxygen',
            'medicamento': 'medication',
            'medicamentos': 'medications',
            'administración': 'administration',
            'administracion': 'administration',
            'terapia': 'therapy',
            'intensiva': 'intensive',
            'cuidados': 'care',
            'bomba': 'pump',
            'infusion': 'infusion',
            'infusión': 'infusion',
            
            # Units
            'dia': 'day',
            'día': 'day',
            'hora': 'hour',
            'horas': 'hours',
            'por': 'per',
            'cada': 'every',
            'dosis': 'dose',
            'tableta': 'tablet',
            'ampula': 'ampule',
            'frasco': 'vial',
        }
        
        for es, en in common_terms.items():
            if es not in self.single_words:
                self.single_words[es] = en
                
        print(f"Added {len(common_terms)} common medical terms")
        
    def save_glossaries(self, output_dir: str = "data/glossaries"):
        """Save the enhanced glossaries"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save comprehensive glossary (all terms)
        all_terms = {}
        all_terms.update(self.single_words)
        all_terms.update(self.short_phrases)
        all_terms.update(self.full_phrases)
        all_terms.update(self.abbreviations)
        
        comprehensive_file = output_path / "glossary_comprehensive.csv"
        with open(comprehensive_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['es_term', 'en_term', 'type'])
            
            for term, translation in self.single_words.items():
                writer.writerow([term, translation, 'single'])
            for term, translation in self.short_phrases.items():
                writer.writerow([term, translation, 'short'])
            for term, translation in self.full_phrases.items():
                writer.writerow([term, translation, 'full'])
            for term, translation in self.abbreviations.items():
                writer.writerow([term, translation, 'abbrev'])
                
        print(f"Saved comprehensive glossary: {comprehensive_file}")
        print(f"  Total terms: {len(all_terms)}")
        
        # Save single words glossary (for fast lookup)
        single_file = output_path / "glossary_single_words.csv"
        with open(single_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['es_term', 'en_term'])
            for term, translation in self.single_words.items():
                writer.writerow([term, translation])
                
        print(f"Saved single words glossary: {single_file}")
        
        return comprehensive_file, single_file


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build enhanced UMLS glossary')
    parser.add_argument('--mrconso', 
                       default='/home/psadmin/ai/enfermera_elena/data/2025AA/META/MRCONSO.RRF',
                       help='Path to MRCONSO.RRF file')
    args = parser.parse_args()
    
    print("=" * 70)
    print("Enhanced UMLS Glossary Generator")
    print("=" * 70)
    
    builder = EnhancedGlossaryBuilder(args.mrconso)
    
    # Process UMLS
    builder.process_umls()
    
    # Add common terms
    builder.add_common_medical_terms()
    
    # Save glossaries
    comprehensive, single = builder.save_glossaries()
    
    print("\n✅ Enhanced glossaries created successfully!")
    print(f"Use {comprehensive} for comprehensive translation")
    print(f"Use {single} for quick single-word lookup")


if __name__ == "__main__":
    main()