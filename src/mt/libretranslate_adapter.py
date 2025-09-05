#!/usr/bin/env python3
"""
LibreTranslate Adapter for Enfermera Elena
Provides on-premise translation with PHI protection and medical term handling
"""

import re
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class LibreTranslateAdapter:
    """
    On-premise translation using LibreTranslate with medical enhancements
    Preserves PHI placeholders and enforces medical glossary
    """
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5000,
                 api_key: Optional[str] = None,
                 glossary_path: Optional[str] = None,
                 timeout: int = 30):
        """
        Initialize LibreTranslate adapter
        
        Args:
            host: LibreTranslate server host
            port: LibreTranslate server port
            api_key: Optional API key for rate limiting
            glossary_path: Path to CSV glossary file
            timeout: Request timeout in seconds
        """
        self.base_url = f"http://{host}:{port}"
        self.api_key = api_key
        self.timeout = timeout
        
        # PHI placeholder pattern
        self.phi_pattern = re.compile(r'__PHI_[A-Z]+_\d+__')
        
        # Never translate patterns
        self.never_translate = [
            self.phi_pattern,
            re.compile(r'\bCURP\b'),
            re.compile(r'\bRFC\b'),
            re.compile(r'\bNSS\b'),
            re.compile(r'\bIMSS\b'),
            re.compile(r'\bISSSTE\b'),
        ]
        
        # Load glossary if provided
        self.glossary = {}
        self.reverse_glossary = {}
        if glossary_path and Path(glossary_path).exists():
            self.load_glossary(glossary_path)
            
        # Medical abbreviation expansions
        self.abbreviations = {
            'HTA': 'Hipertensión Arterial',
            'DM2': 'Diabetes Mellitus Tipo 2',
            'DM': 'Diabetes Mellitus',
            'IAM': 'Infarto Agudo al Miocardio',
            'EVC': 'Evento Vascular Cerebral',
            'ACV': 'Accidente Cerebrovascular',
            'EPOC': 'Enfermedad Pulmonar Obstructiva Crónica',
            'IRC': 'Insuficiencia Renal Crónica',
            'IRA': 'Insuficiencia Renal Aguda',
            'HAS': 'Hipertensión Arterial Sistémica',
            'CA': 'Cáncer',
            'Tx': 'Tratamiento',
            'Dx': 'Diagnóstico',
            'Rx': 'Radiografía',
            'TAC': 'Tomografía Axial Computarizada',
            'RM': 'Resonancia Magnética',
            'ECG': 'Electrocardiograma',
            'PA': 'Presión Arterial',
            'FC': 'Frecuencia Cardíaca',
            'FR': 'Frecuencia Respiratoria',
            'Temp': 'Temperatura',
            'SatO2': 'Saturación de Oxígeno',
            'TA': 'Tensión Arterial',
        }
        
        # Check server availability
        self.check_server()
        
    def check_server(self) -> bool:
        """Check if LibreTranslate server is available"""
        try:
            response = requests.get(f"{self.base_url}/languages", timeout=5)
            if response.status_code == 200:
                languages = response.json()
                has_spanish = any(lang['code'] == 'es' for lang in languages)
                has_english = any(lang['code'] == 'en' for lang in languages)
                
                if has_spanish and has_english:
                    logger.info("LibreTranslate server available with ES/EN support")
                    return True
                else:
                    logger.error("LibreTranslate server missing ES or EN language support")
                    return False
        except requests.exceptions.RequestException as e:
            logger.error(f"LibreTranslate server not available: {e}")
            logger.info("Start server with: docker run -p 5000:5000 libretranslate/libretranslate")
            return False
            
    def load_glossary(self, glossary_path: str):
        """Load medical glossary from CSV file"""
        import csv
        
        with open(glossary_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row.get('es_term', '').lower().strip()
                en_term = row.get('en_term', '').strip()
                
                if es_term and en_term:
                    self.glossary[es_term] = en_term
                    # Also store reverse for validation
                    self.reverse_glossary[en_term.lower()] = es_term
                    
        logger.info(f"Loaded {len(self.glossary)} glossary entries")
        
    def expand_abbreviations(self, text: str) -> str:
        """Expand medical abbreviations before translation"""
        expanded = text
        
        # Sort by length to avoid partial replacements
        for abbrev in sorted(self.abbreviations.keys(), key=len, reverse=True):
            # Use word boundaries to avoid partial matches
            pattern = rf'\b{re.escape(abbrev)}\b'
            expansion = self.abbreviations[abbrev]
            
            # Add abbreviation in parentheses for clarity
            replacement = f"{expansion} ({abbrev})"
            expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)
            
        return expanded
        
    def extract_protected_tokens(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Extract and replace protected tokens (PHI, special terms)
        Returns cleaned text and token mapping
        """
        tokens = {}
        cleaned = text
        
        # Extract PHI placeholders
        phi_matches = self.phi_pattern.findall(text)
        for i, match in enumerate(phi_matches):
            token = f"__TOKEN_{i:04d}__"
            tokens[token] = match
            cleaned = cleaned.replace(match, token)
            
        # Extract other protected patterns
        for j, pattern in enumerate(self.never_translate[1:], start=len(phi_matches)):
            matches = pattern.findall(cleaned)
            for match in matches:
                token = f"__TOKEN_{j:04d}__"
                tokens[token] = match
                cleaned = re.sub(pattern, token, cleaned, count=1)
                
        return cleaned, tokens
        
    def restore_protected_tokens(self, text: str, tokens: Dict[str, str]) -> str:
        """Restore protected tokens after translation"""
        restored = text
        
        # Restore in reverse order to handle nested tokens
        for token in sorted(tokens.keys(), reverse=True):
            original = tokens[token]
            restored = restored.replace(token, original)
            
        return restored
        
    def apply_glossary_pre(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Apply glossary before translation by replacing with unique tokens
        Returns modified text and token mapping
        """
        glossary_tokens = {}
        modified = text.lower()
        
        # Sort by length to match longer phrases first
        sorted_terms = sorted(self.glossary.keys(), key=len, reverse=True)
        
        for es_term in sorted_terms:
            if es_term in modified:
                # Create unique token
                token_id = hashlib.md5(es_term.encode()).hexdigest()[:8]
                token = f"__GLOSS_{token_id}__"
                
                # Store the English translation
                glossary_tokens[token] = self.glossary[es_term]
                
                # Replace in text (case-insensitive)
                pattern = re.compile(re.escape(es_term), re.IGNORECASE)
                modified = pattern.sub(token, modified)
                
        return modified, glossary_tokens
        
    def apply_glossary_post(self, text: str, glossary_tokens: Dict[str, str]) -> str:
        """Replace glossary tokens with their translations"""
        result = text
        
        for token, translation in glossary_tokens.items():
            result = result.replace(token, translation)
            
        return result
        
    def validate_translation(self, source: str, target: str) -> bool:
        """
        Validate translation quality and PHI preservation
        Returns True if translation is acceptable
        """
        # Check PHI preservation
        source_phi = self.phi_pattern.findall(source)
        target_phi = self.phi_pattern.findall(target)
        
        if set(source_phi) != set(target_phi):
            logger.error(f"PHI mismatch! Source: {source_phi}, Target: {target_phi}")
            return False
            
        # Check for untranslated Spanish (basic check)
        spanish_indicators = ['el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'y', 'o']
        words = target.lower().split()
        spanish_count = sum(1 for word in words if word in spanish_indicators)
        
        if len(words) > 10 and spanish_count > len(words) * 0.3:
            logger.warning("Translation may be incomplete - high Spanish word count")
            
        return True
        
    def translate_batch(self, texts: List[str], 
                       source: str = "es", 
                       target: str = "en") -> List[str]:
        """Translate multiple texts efficiently"""
        results = []
        
        for text in texts:
            translated = self.translate(text, source, target)
            results.append(translated)
            
        return results
        
    def translate(self, text: str, 
                 source: str = "es", 
                 target: str = "en",
                 apply_medical: bool = True) -> str:
        """
        Translate text with medical enhancements and PHI protection
        
        Args:
            text: Source text to translate
            source: Source language code
            target: Target language code
            apply_medical: Whether to apply medical processing
            
        Returns:
            Translated text with PHI preserved
        """
        if not text or not text.strip():
            return text
            
        try:
            # Step 1: Expand abbreviations if medical processing enabled
            if apply_medical:
                text = self.expand_abbreviations(text)
                
            # Step 2: Extract protected tokens (PHI, special terms)
            cleaned_text, protected_tokens = self.extract_protected_tokens(text)
            
            # Step 3: Apply glossary pre-processing
            if apply_medical and self.glossary:
                cleaned_text, glossary_tokens = self.apply_glossary_pre(cleaned_text)
            else:
                glossary_tokens = {}
                
            # Step 4: Call LibreTranslate API
            payload = {
                "q": cleaned_text,
                "source": source,
                "target": target,
                "format": "text"
            }
            
            if self.api_key:
                payload["api_key"] = self.api_key
                
            response = requests.post(
                f"{self.base_url}/translate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Translation failed: {response.status_code} - {response.text}")
                return text  # Return original on failure
                
            translated = response.json()["translatedText"]
            
            # Step 5: Apply glossary post-processing
            if glossary_tokens:
                translated = self.apply_glossary_post(translated, glossary_tokens)
                
            # Step 6: Restore protected tokens
            translated = self.restore_protected_tokens(translated, protected_tokens)
            
            # Step 7: Validate translation
            if not self.validate_translation(text, translated):
                logger.warning("Translation validation failed, returning original")
                return text
                
            return translated
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text  # Return original on error
            

class MedicalContextEnhancer:
    """Add medical context and validate terminology"""
    
    def __init__(self):
        self.medical_patterns = {
            'medications': re.compile(r'\b\d+\s*mg\b|\b\d+\s*ml\b|\b\d+\s*UI\b'),
            'vitals': re.compile(r'\b\d+/\d+\s*mmHg\b|\b\d+\s*lpm\b|\b\d+\.?\d*°C\b'),
            'labs': re.compile(r'\b\d+\.?\d*\s*mg/dl\b|\b\d+\.?\d*\s*mmol/L\b'),
        }
        
    def add_context_markers(self, text: str) -> str:
        """Add context markers for medical content"""
        marked = text
        
        # Mark medication mentions
        if self.medical_patterns['medications'].search(text):
            marked = f"[MEDICATION CONTEXT] {marked}"
            
        # Mark vital signs
        if self.medical_patterns['vitals'].search(text):
            marked = f"[VITALS CONTEXT] {marked}"
            
        return marked
        

def create_docker_compose():
    """Generate docker-compose.yml for LibreTranslate"""
    config = """version: '3.8'

services:
  libretranslate:
    image: libretranslate/libretranslate:latest
    container_name: enfermera_elena_translator
    ports:
      - "5000:5000"
    environment:
      - LT_LOAD_ONLY=es,en
      - LT_DISABLE_FILES_TRANSLATION=true
      - LT_CHAR_LIMIT=5000
      - LT_REQ_LIMIT=0
      - LT_BATCH_LIMIT=0
      - LT_GA_ID=
    volumes:
      - ./data/libretranslate:/home/libretranslate/.local
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/languages"]
      interval: 30s
      timeout: 10s
      retries: 3
"""
    
    with open('docker-compose.yml', 'w') as f:
        f.write(config)
        
    print("Docker Compose file created. Start with: docker-compose up -d")


if __name__ == "__main__":
    # Test the adapter
    import argparse
    
    parser = argparse.ArgumentParser(description="LibreTranslate Adapter for Medical Translation")
    parser.add_argument('--test', action='store_true', help='Run test translation')
    parser.add_argument('--setup', action='store_true', help='Create Docker Compose file')
    parser.add_argument('--text', type=str, help='Text to translate')
    parser.add_argument('--glossary', type=str, help='Path to glossary CSV')
    
    args = parser.parse_args()
    
    if args.setup:
        create_docker_compose()
        
    elif args.test or args.text:
        # Initialize adapter
        adapter = LibreTranslateAdapter(
            glossary_path=args.glossary
        )
        
        if args.text:
            test_text = args.text
        else:
            # Default test with medical content and PHI
            test_text = """
            El paciente __PHI_NAME_001__ presenta HTA controlada con 
            Losartán 50mg c/12hrs. PA: 130/80 mmHg. 
            Diagnóstico: DM2 e IAM previo.
            NSS: __PHI_ID_002__
            """
            
        print(f"Original:\n{test_text}\n")
        
        translated = adapter.translate(test_text)
        
        print(f"Translated:\n{translated}\n")
        
        # Verify PHI preservation
        original_phi = adapter.phi_pattern.findall(test_text)
        translated_phi = adapter.phi_pattern.findall(translated)
        
        print(f"PHI Preserved: {original_phi == translated_phi}")
        print(f"Original PHI: {original_phi}")
        print(f"Translated PHI: {translated_phi}")
        
    else:
        parser.print_help()