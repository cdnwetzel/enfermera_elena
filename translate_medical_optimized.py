#!/usr/bin/env python3
"""
Optimized Medical Record Translator for Enfermera Elena
High-performance translation with 1.2M term glossary
"""

import re
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import pickle

class OptimizedMedicalTranslator:
    def __init__(self, glossary_dir: str = "data/glossaries"):
        self.glossary_dir = Path(glossary_dir)
        self.cache_file = self.glossary_dir / "glossary_cache.pkl"
        
        # Tiered glossary system for performance
        self.critical_terms = {}  # Priority 1: Critical medical terms
        self.common_terms = {}    # Priority 2: Common medical words
        self.full_glossary = {}   # Priority 3: Complete glossary
        
        # Pre-compiled patterns for efficiency
        self.number_pattern = re.compile(r'\b\d+[\d.,]*\b')
        self.dosage_pattern = re.compile(r'\b\d+\s*(?:mg|g|ml|cc|mcg|ug|UI|U)\b', re.IGNORECASE)
        self.time_pattern = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm|hrs?)?\b')
        
        self.load_optimized_glossaries()
    
    def load_optimized_glossaries(self):
        """Load glossaries with caching and tiering"""
        print("Loading optimized glossaries...")
        start = time.time()
        
        # Try to load from cache first
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.critical_terms = cache_data['critical']
                    self.common_terms = cache_data['common']
                    self.full_glossary = cache_data['full']
                    print(f"✓ Loaded from cache in {time.time()-start:.1f}s")
                    self._print_stats()
                    return
            except:
                print("Cache invalid, rebuilding...")
        
        # Build tiered glossaries
        self._build_tiered_glossaries()
        
        # Save to cache
        cache_data = {
            'critical': self.critical_terms,
            'common': self.common_terms,
            'full': self.full_glossary
        }
        with open(self.cache_file, 'wb') as f:
            pickle.dump(cache_data, f)
        
        print(f"✓ Glossaries loaded in {time.time()-start:.1f}s")
        self._print_stats()
    
    def _build_tiered_glossaries(self):
        """Build tiered glossary system"""
        
        # Critical medical terms (always check these)
        critical_keywords = {
            'alergia', 'alergico', 'diabetes', 'hipertension', 'cancer',
            'urgencia', 'emergencia', 'critico', 'grave', 'severo',
            'infarto', 'paro', 'hemorragia', 'fractura', 'trauma',
            'cirugia', 'operacion', 'anestesia', 'intubacion',
            'medicamento', 'dosis', 'contraindicacion', 'reaccion'
        }
        
        # Common medical terms (check frequently)
        common_keywords = {
            'paciente', 'medico', 'enfermera', 'hospital', 'clinica',
            'diagnostico', 'tratamiento', 'examen', 'prueba', 'analisis',
            'dolor', 'fiebre', 'tos', 'nausea', 'vomito', 'diarrea',
            'sangre', 'orina', 'glucosa', 'presion', 'temperatura',
            'fecha', 'hora', 'dia', 'mes', 'año', 'edad'
        }
        
        # Load comprehensive glossary
        comprehensive_path = self.glossary_dir / "glossary_comprehensive.csv"
        if comprehensive_path.exists():
            import csv
            with open(comprehensive_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    es_term = row['es_term'].lower().strip()
                    en_term = row['en_term'].strip()
                    
                    # Skip empty or invalid entries
                    if not es_term or not en_term or len(es_term) < 2:
                        continue
                    
                    # Categorize by importance
                    if any(keyword in es_term for keyword in critical_keywords):
                        self.critical_terms[es_term] = en_term
                    elif any(keyword in es_term for keyword in common_keywords):
                        self.common_terms[es_term] = en_term
                    elif len(es_term.split()) == 1:  # Single words
                        self.common_terms[es_term] = en_term
                    else:
                        self.full_glossary[es_term] = en_term
        
        # Load single words for better coverage
        single_words_path = self.glossary_dir / "glossary_single_words.csv"
        if single_words_path.exists():
            import csv
            with open(single_words_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    es_term = row['es_term'].lower().strip()
                    en_term = row['en_term'].strip()
                    if es_term and en_term and len(es_term) >= 3:
                        if es_term not in self.common_terms:
                            self.common_terms[es_term] = en_term
    
    def _print_stats(self):
        """Print glossary statistics"""
        print(f"  Critical terms: {len(self.critical_terms):,}")
        print(f"  Common terms: {len(self.common_terms):,}")
        print(f"  Full glossary: {len(self.full_glossary):,}")
        print(f"  Total unique: {len(set(self.critical_terms) | set(self.common_terms) | set(self.full_glossary)):,}")
    
    def translate_line_optimized(self, line: str) -> Tuple[str, float]:
        """Translate a single line with optimized performance"""
        if not line.strip():
            return line, 1.0
        
        # Preserve critical content
        preserved = {}
        placeholder_counter = 0
        working_line = line
        
        # Preserve numbers, dosages, times (process in reverse to maintain positions)
        for pattern in [self.dosage_pattern, self.time_pattern, self.number_pattern]:
            matches = list(pattern.finditer(working_line))
            for match in reversed(matches):
                placeholder = f"__PRESERVE_{placeholder_counter}__"
                preserved[placeholder] = match.group()
                working_line = working_line[:match.start()] + placeholder + working_line[match.end():]
                placeholder_counter += 1
        
        translated = working_line
        confidence = 0.0
        matches_found = 0
        
        # Split into words for efficient matching
        words = translated.lower().split()
        word_count = len(words)
        
        # Phase 1: Translate critical terms (highest priority)
        for es_term, en_term in self.critical_terms.items():
            if es_term in translated.lower():
                pattern = re.compile(r'\b' + re.escape(es_term) + r'\b', re.IGNORECASE)
                if pattern.search(translated):
                    translated = pattern.sub(en_term, translated)
                    matches_found += 1
        
        # Phase 2: Translate common single words
        translated_words = []
        for word in translated.split():
            # Skip placeholders
            if word.startswith('__PRESERVE_') and word.endswith('__'):
                translated_words.append(word)
                continue
                
            word_lower = word.lower().strip('.,;:!?')
            if word_lower in self.common_terms:
                # Preserve original punctuation
                prefix = word[:len(word) - len(word.lstrip('.,;:!?'))]
                suffix = word[len(word.rstrip('.,;:!?')):]
                translated_words.append(prefix + self.common_terms[word_lower] + suffix)
                matches_found += 1
            else:
                translated_words.append(word)
        translated = ' '.join(translated_words)
        
        # Phase 3: Basic Spanish connectors (fast replacement)
        basic_replacements = [
            (' de ', ' of '), (' del ', ' of the '),
            (' la ', ' the '), (' el ', ' the '),
            (' los ', ' the '), (' las ', ' the '),
            (' y ', ' and '), (' o ', ' or '),
            (' por ', ' by '), (' para ', ' for '),
            (' con ', ' with '), (' sin ', ' without '),
        ]
        for sp, en in basic_replacements:
            translated = translated.replace(sp, en)
        
        # Restore preserved content
        for placeholder, original in preserved.items():
            translated = translated.replace(placeholder, original)
        
        # Calculate confidence
        if word_count > 0:
            confidence = min(0.95, 0.5 + (matches_found / word_count))
        
        return translated, confidence
    
    def translate_document(self, input_path: str, output_path: str = None) -> Dict:
        """Translate entire document with performance optimization"""
        print(f"\n📄 Translating: {input_path}")
        start_time = time.time()
        
        # Read input
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"  Processing {len(lines)} lines...")
        
        # Translate with progress tracking
        translated_lines = []
        total_confidence = 0.0
        line_count = 0
        
        for i, line in enumerate(lines):
            if i % 50 == 0 and i > 0:
                print(f"  Progress: {i}/{len(lines)} lines ({i*100/len(lines):.1f}%)")
            
            translated, confidence = self.translate_line_optimized(line)
            translated_lines.append(translated)
            
            if line.strip():
                total_confidence += confidence
                line_count += 1
        
        # Calculate average confidence
        avg_confidence = total_confidence / line_count if line_count > 0 else 0
        
        # Save translation
        if not output_path:
            output_path = input_path.replace('_extracted.txt', '_translated.txt')
            output_path = output_path.replace('/extracted/', '/translated/')
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(translated_lines)
        
        elapsed = time.time() - start_time
        
        result = {
            'input': input_path,
            'output': output_path,
            'lines': len(lines),
            'time': f"{elapsed:.1f}s",
            'confidence': f"{avg_confidence:.1%}",
            'words_per_second': len(' '.join(lines).split()) / elapsed
        }
        
        print(f"✓ Translation complete in {elapsed:.1f}s")
        print(f"  Average confidence: {avg_confidence:.1%}")
        print(f"  Performance: {result['words_per_second']:.0f} words/sec")
        print(f"  Output: {output_path}")
        
        return result

def main():
    """Main function"""
    print("="*70)
    print("Enfermera Elena - Optimized Medical Translation")
    print("="*70)
    
    # Initialize translator
    translator = OptimizedMedicalTranslator()
    
    # Translate the example document
    input_file = "medical_records/extracted/mr_12_03_25_MACSMA_redacted_extracted.txt"
    
    if not Path(input_file).exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    # Perform translation
    result = translator.translate_document(input_file)
    
    # Show sample
    output_file = result['output']
    with open(output_file, 'r', encoding='utf-8') as f:
        sample = f.read(1000)
    
    print("\n📝 Sample of translation:")
    print("-"*70)
    print(sample)
    print("-"*70)
    
    print("\n✅ Translation complete!")
    print(f"View full translation: cat {output_file}")

if __name__ == "__main__":
    main()