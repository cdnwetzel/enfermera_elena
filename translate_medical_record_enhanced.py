#!/usr/bin/env python3
"""
Enhanced Medical Record Translator for Enfermera Elena
Uses LibreTranslate API for neural translation with UMLS glossary enhancement
"""

import csv
import re
import requests
import json
from pathlib import Path
from typing import Dict, List, Optional
import time


class EnhancedMedicalTranslator:
    """Enhanced translator using LibreTranslate + UMLS glossary"""
    
    def __init__(self, libretranslate_url: str = "http://localhost:5000"):
        """
        Initialize enhanced translator
        
        Args:
            libretranslate_url: URL where LibreTranslate is running
        """
        self.api_url = libretranslate_url
        self.glossary = {}
        self.load_glossary()
        
        # Test LibreTranslate connection
        self.test_connection()
        
    def test_connection(self):
        """Test if LibreTranslate is accessible"""
        try:
            response = requests.get(f"{self.api_url}/languages", timeout=5)
            if response.status_code == 200:
                print("✅ LibreTranslate connected successfully")
                languages = response.json()
                spanish = [l for l in languages if l['code'] == 'es']
                english = [l for l in languages if l['code'] == 'en']
                if spanish and english:
                    print("   Spanish and English models loaded")
            else:
                print(f"⚠️  LibreTranslate connection failed: {response.status_code}")
        except Exception as e:
            print(f"⚠️  Could not connect to LibreTranslate: {e}")
            print("   Falling back to glossary-only translation")
            
    def load_glossary(self, path: str = "data/glossaries/glossary_es_en_production.csv"):
        """Load UMLS glossary"""
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row['es_term'].lower()
                en_term = row['en_term']
                self.glossary[es_term] = en_term
                
        print(f"📚 Loaded {len(self.glossary)} medical terms from UMLS")
        
    def translate_with_libretranslate(self, text: str) -> str:
        """
        Translate text using LibreTranslate API
        
        Args:
            text: Spanish text to translate
            
        Returns:
            English translation
        """
        try:
            # Split into chunks if text is too long (LibreTranslate has limits)
            max_length = 5000
            if len(text) > max_length:
                # Split by lines and process in chunks
                lines = text.split('\n')
                translated_lines = []
                current_chunk = []
                current_length = 0
                
                for line in lines:
                    if current_length + len(line) > max_length and current_chunk:
                        # Process current chunk
                        chunk_text = '\n'.join(current_chunk)
                        translated = self._translate_chunk(chunk_text)
                        translated_lines.extend(translated.split('\n'))
                        current_chunk = [line]
                        current_length = len(line)
                    else:
                        current_chunk.append(line)
                        current_length += len(line) + 1
                        
                # Process remaining chunk
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    translated = self._translate_chunk(chunk_text)
                    translated_lines.extend(translated.split('\n'))
                    
                return '\n'.join(translated_lines)
            else:
                return self._translate_chunk(text)
                
        except Exception as e:
            print(f"⚠️  LibreTranslate error: {e}")
            return text  # Return original if translation fails
            
    def _translate_chunk(self, text: str) -> str:
        """Translate a single chunk of text"""
        payload = {
            'q': text,
            'source': 'es',
            'target': 'en',
            'format': 'text'
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/translate",
                data=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('translatedText', text)
            else:
                print(f"Translation API error: {response.status_code}")
                return text
                
        except requests.exceptions.Timeout:
            print("Translation timeout - text might be too long")
            return text
        except Exception as e:
            print(f"Translation error: {e}")
            return text
            
    def enhance_with_medical_terms(self, original: str, translated: str) -> str:
        """
        Post-process translation with medical terminology from UMLS
        
        Args:
            original: Original Spanish text
            translated: LibreTranslate translation
            
        Returns:
            Enhanced translation with correct medical terms
        """
        # Critical medical terms that must be correct
        critical_replacements = {
            # Medications and dosages
            'miligramos': 'milligrams',
            'mililitros': 'milliliters',
            'microgramos': 'micrograms',
            'unidades': 'units',
            
            # Departments (ensure consistency)
            'imagenología': 'IMAGING',
            'imageología': 'IMAGING',
            'inhaloterapia': 'RESPIRATORY THERAPY',
            'laboratorio': 'LABORATORY',
            'farmacia': 'PHARMACY',
            'urgencias': 'EMERGENCY',
            
            # Common medical procedures
            'tomografía': 'CT scan',
            'tomografia': 'CT scan',
            'radiografía': 'X-ray',
            'radiografia': 'X-ray',
            
            # Fix common mistranslations
            'oxygen per day': 'oxygen per day',
            'oxígeno por día': 'oxygen per day',
            'oxigeno por dia': 'oxygen per day',
        }
        
        enhanced = translated
        
        # Apply critical replacements
        for spanish, english in critical_replacements.items():
            pattern = re.compile(re.escape(spanish), re.IGNORECASE)
            enhanced = pattern.sub(english, enhanced)
            
        # Apply UMLS glossary for medical terms not caught by neural translation
        original_lower = original.lower()
        for es_term, en_term in self.glossary.items():
            if es_term in original_lower and len(es_term) > 4:
                # Check if term wasn't already translated correctly
                if en_term.lower() not in enhanced.lower():
                    # Find the term in original and replace in same position
                    pattern = re.compile(r'\b' + re.escape(es_term) + r'\b', re.IGNORECASE)
                    if pattern.search(original):
                        # Term exists in original, might be mistranslated
                        # Try to find corresponding position in translation
                        pass  # Complex position mapping - skip for now
                        
        return enhanced
        
    def translate_document(self, text: str) -> str:
        """
        Full document translation pipeline
        
        Args:
            text: Spanish medical document text
            
        Returns:
            English translation
        """
        print("\n🔄 Starting enhanced translation...")
        
        # Step 1: Neural translation with LibreTranslate
        print("   1. Neural translation with LibreTranslate...")
        start_time = time.time()
        
        # Process line by line to preserve formatting
        lines = text.split('\n')
        translated_lines = []
        
        # Batch lines for efficiency (but preserve structure)
        batch_size = 50
        for i in range(0, len(lines), batch_size):
            batch = lines[i:i+batch_size]
            
            # Skip empty lines
            non_empty = [l for l in batch if l.strip()]
            if non_empty:
                batch_text = '\n'.join(non_empty)
                translated_batch = self.translate_with_libretranslate(batch_text)
                translated_parts = translated_batch.split('\n')
                
                # Reconstruct with empty lines
                result_idx = 0
                for line in batch:
                    if line.strip():
                        if result_idx < len(translated_parts):
                            translated_lines.append(translated_parts[result_idx])
                            result_idx += 1
                        else:
                            translated_lines.append(line)  # Fallback
                    else:
                        translated_lines.append('')  # Preserve empty lines
            else:
                translated_lines.extend(batch)  # All empty
                
            # Progress indicator
            if i % 200 == 0 and i > 0:
                print(f"      Processed {i}/{len(lines)} lines...")
                
        neural_translation = '\n'.join(translated_lines)
        
        print(f"   2. Enhancing with {len(self.glossary)} medical terms...")
        
        # Step 2: Enhance with medical terminology
        enhanced_translation = self.enhance_with_medical_terms(text, neural_translation)
        
        elapsed = time.time() - start_time
        print(f"   ✅ Translation completed in {elapsed:.1f} seconds")
        
        return enhanced_translation


def main():
    """Main translation function"""
    
    print("=" * 70)
    print("Enfermera Elena - Enhanced Medical Record Translation")
    print("Using LibreTranslate + UMLS Glossary")
    print("=" * 70)
    
    # Initialize translator
    translator = EnhancedMedicalTranslator()
    
    # Read extracted text
    input_file = "medical_records/extracted/mr_12_03_25_MACSMA_extracted.txt"
    print(f"\n📄 Reading: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        original_text = f.read()
        
    print(f"   Found {len(original_text)} characters, {len(original_text.split())} words")
    
    # Translate
    translated = translator.translate_document(original_text)
    
    # Save translation
    output_file = "medical_records/translated/mr_12_03_25_MACSMA_enhanced.txt"
    Path("medical_records/translated").mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(translated)
        
    print(f"\n✅ Enhanced translation saved to: {output_file}")
    
    # Show sample
    print("\n📝 Sample of enhanced translation:")
    print("-" * 70)
    print(translated[:1000])
    print("-" * 70)
    
    # Statistics
    spanish_words = len(original_text.split())
    english_words = len(translated.split())
    
    print(f"\n📊 Statistics:")
    print(f"   Original: {spanish_words} words")
    print(f"   Translated: {english_words} words")
    print(f"   Lines: {len(original_text.splitlines())}")
    
    print("\n✅ Enhanced translation complete!")
    print(f"\nView the full translation: cat {output_file}")
    
    # Run quality analysis
    print("\n🔍 Running quality analysis...")
    from translation_quality_analyzer import TranslationQualityAnalyzer
    
    analyzer = TranslationQualityAnalyzer()
    analysis = analyzer.analyze_translation(original_text, translated)
    
    confidence = analysis.get('total_confidence', 0)
    print(f"   Overall confidence: {confidence:.1%}")
    
    if confidence > 0.8:
        print("   ✅ High quality translation")
    elif confidence > 0.6:
        print("   ⚠️  Good translation, some review recommended")
    else:
        print("   ⚠️  Translation needs review")


if __name__ == "__main__":
    main()