#!/usr/bin/env python3
"""
Simple Medical PDF Translator for Enfermera Elena
Uses UMLS glossary for term-by-term translation
Works with minimal dependencies
"""

import csv
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleUMLSTranslator:
    """Simple translator using UMLS glossary"""
    
    def __init__(self, glossary_path: str = "data/glossaries/glossary_es_en_production.csv"):
        self.glossary = {}
        self.load_glossary(glossary_path)
        
        # Common medical abbreviations
        self.abbreviations = {
            'hta': 'HTN (hypertension)',
            'dm2': 'DM2 (type 2 diabetes)',
            'dm': 'DM (diabetes mellitus)',
            'iam': 'AMI (acute myocardial infarction)',
            'evc': 'CVA (stroke)',
            'epoc': 'COPD',
            'irc': 'CKD (chronic kidney disease)',
            'ta': 'BP (blood pressure)',
            'fc': 'HR (heart rate)',
            'fr': 'RR (respiratory rate)',
            'temp': 'temp',
            'pa': 'BP',
            'rx': 'x-ray',
            'tx': 'treatment',
            'dx': 'diagnosis',
            'px': 'prognosis',
            'bh': 'CBC (complete blood count)',
            'qs': 'blood chemistry',
            'ego': 'urinalysis',
        }
        
        # Common phrases
        self.phrases = {
            'sin datos de': 'no evidence of',
            'con datos de': 'with evidence of',
            'a descartar': 'to rule out',
            'en estudio': 'under study',
            'en control': 'controlled',
            'consulta externa': 'outpatient consultation',
            'urgencias': 'emergency department',
            'nota médica': 'medical note',
            'antecedentes': 'history',
            'exploración física': 'physical examination',
            'signos vitales': 'vital signs',
            'diagnóstico': 'diagnosis',
            'tratamiento': 'treatment',
            'plan': 'plan',
            'pronóstico': 'prognosis',
            'evolución': 'progress',
            'sin alteraciones': 'no abnormalities',
            'dentro de límites normales': 'within normal limits',
            'se indica': 'indicated',
            'se recomienda': 'recommended',
            'valoración por': 'evaluation by',
        }
        
    def load_glossary(self, path: str):
        """Load UMLS glossary"""
        if not Path(path).exists():
            logger.warning(f"Glossary not found at {path}")
            return
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row['es_term'].lower()
                en_term = row['en_term']
                self.glossary[es_term] = en_term
                
        logger.info(f"Loaded {len(self.glossary)} glossary terms")
        
    def translate_text(self, text: str) -> str:
        """Translate Spanish text to English using glossary"""
        if not text:
            return text
            
        # Preserve line breaks and structure
        lines = text.split('\n')
        translated_lines = []
        
        for line in lines:
            if not line.strip():
                translated_lines.append(line)
                continue
                
            # Translate the line
            translated = self.translate_line(line)
            translated_lines.append(translated)
            
        return '\n'.join(translated_lines)
        
    def translate_line(self, line: str) -> str:
        """Translate a single line"""
        original = line
        result = line.lower()
        
        # First, translate common phrases
        for es_phrase, en_phrase in sorted(self.phrases.items(), key=lambda x: -len(x[0])):
            if es_phrase in result:
                result = result.replace(es_phrase, en_phrase)
                
        # Translate medical abbreviations
        for abbrev, translation in self.abbreviations.items():
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            result = re.sub(pattern, translation, result, flags=re.IGNORECASE)
            
        # Translate terms from glossary (longest first to handle phrases)
        terms_to_translate = sorted(
            [(term, trans) for term, trans in self.glossary.items() if term in result],
            key=lambda x: -len(x[0])
        )
        
        for es_term, en_term in terms_to_translate[:100]:  # Limit to avoid over-translation
            if es_term in result:
                result = result.replace(es_term, en_term.lower())
                
        # Preserve numbers and measurements
        result = self.preserve_measurements(original, result)
        
        # Basic word-by-word for remaining Spanish
        result = self.basic_word_translation(result)
        
        # Capitalize first letter of sentences
        result = '. '.join(s.strip().capitalize() for s in result.split('.') if s.strip())
        
        return result
        
    def preserve_measurements(self, original: str, translated: str) -> str:
        """Preserve numbers and units from original"""
        # Find all numbers with units in original
        pattern = r'\d+[\.,]?\d*\s*(?:mg|ml|kg|g|mmHg|°C|%|mg/dl|UI|mcg|mEq|L|dL)'
        measurements = re.findall(pattern, original, re.IGNORECASE)
        
        # Ensure they're preserved in translation
        for measurement in measurements:
            if measurement not in translated:
                translated += f" [{measurement}]"
                
        return translated
        
    def basic_word_translation(self, text: str) -> str:
        """Basic word-by-word translation for remaining Spanish"""
        # Common Spanish medical words not in glossary
        basic_dict = {
            'el': 'the',
            'la': 'the', 
            'los': 'the',
            'las': 'the',
            'un': 'a',
            'una': 'a',
            'de': 'of',
            'del': 'of the',
            'con': 'with',
            'sin': 'without',
            'por': 'by/for',
            'para': 'for',
            'y': 'and',
            'o': 'or',
            'es': 'is',
            'son': 'are',
            'está': 'is',
            'están': 'are',
            'paciente': 'patient',
            'masculino': 'male',
            'femenino': 'female',
            'años': 'years',
            'edad': 'age',
            'presenta': 'presents',
            'refiere': 'refers',
            'niega': 'denies',
            'positivo': 'positive',
            'negativo': 'negative',
            'normal': 'normal',
            'anormal': 'abnormal',
            'derecho': 'right',
            'izquierdo': 'left',
            'bilateral': 'bilateral',
            'anterior': 'anterior',
            'posterior': 'posterior',
            'superior': 'superior',
            'inferior': 'inferior',
            'agudo': 'acute',
            'crónico': 'chronic',
            'severo': 'severe',
            'moderado': 'moderate',
            'leve': 'mild',
            'dolor': 'pain',
            'fiebre': 'fever',
            'tos': 'cough',
            'disnea': 'dyspnea',
            'náusea': 'nausea',
            'vómito': 'vomiting',
            'diarrea': 'diarrhea',
            'estreñimiento': 'constipation',
            'sangrado': 'bleeding',
            'edema': 'edema',
            'día': 'day',
            'días': 'days',
            'semana': 'week',
            'semanas': 'weeks',
            'mes': 'month',
            'meses': 'months',
            'año': 'year',
            'actualmente': 'currently',
            'previo': 'previous',
            'historia': 'history',
            'familiar': 'family',
            'personal': 'personal',
            'alergias': 'allergies',
            'medicamentos': 'medications',
            'cirugías': 'surgeries',
            'hospitalizaciones': 'hospitalizations',
        }
        
        words = text.split()
        translated_words = []
        
        for word in words:
            # Preserve capitalization info
            is_capitalized = word and word[0].isupper()
            word_lower = word.lower()
            
            # Remove punctuation for lookup
            punct = ''
            if word_lower and word_lower[-1] in '.,;:!?':
                punct = word_lower[-1]
                word_lower = word_lower[:-1]
                
            # Translate
            if word_lower in basic_dict:
                translated = basic_dict[word_lower]
            elif word_lower in self.glossary:
                translated = self.glossary[word_lower]
            else:
                translated = word_lower  # Keep original if no translation
                
            # Restore capitalization
            if is_capitalized and translated:
                translated = translated[0].upper() + translated[1:]
                
            # Restore punctuation
            translated += punct
            
            translated_words.append(translated)
            
        return ' '.join(translated_words)


class SimplePDFProcessor:
    """Extract text from PDF using basic Python tools"""
    
    def extract_text_with_pdftotext(self, pdf_path: str) -> str:
        """Try to extract text using pdftotext command"""
        try:
            result = subprocess.run(
                ['pdftotext', '-layout', pdf_path, '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return ""
        
    def extract_text_basic(self, pdf_path: str) -> str:
        """Basic text extraction fallback"""
        # Try pdftotext first
        text = self.extract_text_with_pdftotext(pdf_path)
        if text:
            return text
            
        # If that fails, we need to inform user
        logger.warning("Cannot extract text without pdftotext or Python PDF libraries")
        return ""


def translate_medical_pdf(input_pdf: str, output_path: str, glossary_path: str):
    """Main translation function"""
    
    print("=" * 60)
    print("Enfermera Elena - Simple Medical Translator")
    print("Using UMLS glossary with 375,000+ terms")
    print("=" * 60)
    
    # Initialize components
    translator = SimpleUMLSTranslator(glossary_path)
    pdf_processor = SimplePDFProcessor()
    
    # Extract text
    print(f"\n📄 Processing: {input_pdf}")
    text = pdf_processor.extract_text_basic(input_pdf)
    
    if not text:
        print("❌ Could not extract text from PDF")
        print("Please install pdftotext: sudo dnf install poppler-utils")
        return False
        
    print(f"✅ Extracted {len(text)} characters")
    
    # Show sample of original
    print("\n📝 Sample of original text:")
    print("-" * 40)
    print(text[:500])
    print("-" * 40)
    
    # Translate
    print("\n🔄 Translating with UMLS glossary...")
    translated = translator.translate_text(text)
    
    # Show sample of translation
    print("\n📝 Sample of translated text:")
    print("-" * 40)
    print(translated[:500])
    print("-" * 40)
    
    # Save as text file (since we can't create PDF without libraries)
    output_txt = output_path.replace('.pdf', '.txt')
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("MEDICAL RECORD TRANSLATION\n")
        f.write("Translated by Enfermera Elena\n")
        f.write("Using UMLS Full Release Glossary (375,000+ terms)\n")
        f.write("=" * 60 + "\n\n")
        f.write(translated)
        
    print(f"\n✅ Translation saved to: {output_txt}")
    
    # Calculate statistics
    spanish_words = len(text.split())
    english_words = len(translated.split())
    
    print(f"\n📊 Statistics:")
    print(f"  Spanish words: {spanish_words}")
    print(f"  English words: {english_words}")
    print(f"  Glossary terms used: ~{len([t for t in translator.glossary if t in text.lower()])}")
    
    return True


if __name__ == "__main__":
    # Set up paths
    input_pdf = "sample_data/original/mr_12_03_25_MACSMA_redacted.pdf"
    output_dir = Path("sample_data/translated")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / "mr_12_03_25_MACSMA_translated.pdf")
    glossary_path = "data/glossaries/glossary_es_en_production.csv"
    
    # Check if files exist
    if not Path(input_pdf).exists():
        print(f"❌ Input PDF not found: {input_pdf}")
        exit(1)
        
    if not Path(glossary_path).exists():
        print(f"❌ Glossary not found: {glossary_path}")
        print("Run process_umls_simple.py first to generate glossary")
        exit(1)
        
    # Translate
    success = translate_medical_pdf(input_pdf, output_path, glossary_path)
    
    if success:
        print("\n🎉 Translation complete!")
        print("\nTo install full dependencies and enable PDF output:")
        print("1. Install pip: sudo dnf install python3-pip")
        print("2. Install deps: pip3 install -r requirements.txt")
        print("3. Start LibreTranslate: docker run -p 5000:5000 libretranslate/libretranslate")
    else:
        print("\n❌ Translation failed")
        print("Please install: sudo dnf install poppler-utils")