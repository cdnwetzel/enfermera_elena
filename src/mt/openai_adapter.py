#!/usr/bin/env python3
"""
OpenAI Adapter with PHI Protection for Enfermera Elena
CRITICAL: Only use with fully de-identified text unless BAA is in place
"""

import re
import os
import json
import logging
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
import time

# OpenAI import with fallback
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI library not installed. Install with: pip install openai")

logger = logging.getLogger(__name__)


class PHIValidator:
    """Strict PHI detection and validation"""
    
    def __init__(self):
        # Mexican PHI patterns
        self.mexican_phi_patterns = {
            'CURP': re.compile(r'[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d'),
            'RFC': re.compile(r'[A-Z]{4}\d{6}[A-Z0-9]{3}'),
            'NSS': re.compile(r'\b\d{11}\b'),
            'INE': re.compile(r'IDMEX\d{13}'),
        }
        
        # US PHI patterns
        self.us_phi_patterns = {
            'SSN': re.compile(r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b'),
            'MRN': re.compile(r'MRN[\s:]*\d{6,}'),
            'DEA': re.compile(r'[A-Z]{2}\d{7}'),
        }
        
        # Generic PHI patterns
        self.generic_phi_patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone_mx': re.compile(r'\+?52[\s-]?\d{2,3}[\s-]?\d{3,4}[\s-]?\d{4}'),
            'phone_us': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            'date': re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b'),
            'address': re.compile(r'\b\d{1,5}\s+[A-Za-z\s]+\b(Street|St|Avenue|Ave|Calle|Av|Avenida)'),
        }
        
        # Names detection (basic)
        self.name_indicators = [
            'Sr.', 'Sra.', 'Dr.', 'Dra.', 'Lic.', 'Ing.',
            'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'MD', 'RN'
        ]
        
    def detect_phi(self, text: str) -> Dict[str, List[str]]:
        """
        Detect potential PHI in text
        Returns dict of PHI type -> list of matches
        """
        detected = {}
        
        # Check Mexican PHI
        for phi_type, pattern in self.mexican_phi_patterns.items():
            matches = pattern.findall(text)
            if matches:
                detected[f"mexican_{phi_type}"] = matches
                
        # Check US PHI
        for phi_type, pattern in self.us_phi_patterns.items():
            matches = pattern.findall(text)
            if matches:
                detected[f"us_{phi_type}"] = matches
                
        # Check generic PHI
        for phi_type, pattern in self.generic_phi_patterns.items():
            matches = pattern.findall(text)
            if matches:
                detected[f"generic_{phi_type}"] = matches[:5]  # Limit to first 5
                
        # Check for potential names
        for indicator in self.name_indicators:
            if indicator in text:
                detected['name_indicator'] = [indicator]
                break
                
        return detected
        
    def validate_deidentified(self, text: str) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate that text is properly de-identified
        Returns (is_safe, detected_phi)
        """
        detected = self.detect_phi(text)
        
        # Check if only placeholders remain
        placeholder_pattern = re.compile(r'__PHI_[A-Z]+_\d+__')
        placeholders = placeholder_pattern.findall(text)
        
        # Remove placeholders and check again
        text_without_placeholders = placeholder_pattern.sub('', text)
        detected_after = self.detect_phi(text_without_placeholders)
        
        is_safe = len(detected_after) == 0
        
        return is_safe, detected_after


class OpenAISecureAdapter:
    """
    OpenAI translation with strict PHI protection and medical context
    WARNING: Requires BAA for PHI processing - only use with de-identified text
    """
    
    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "gpt-4",
                 temperature: float = 0.3,
                 max_tokens: int = 4000,
                 glossary_path: Optional[str] = None,
                 validate_phi: bool = True,
                 require_baa: bool = False):
        """
        Initialize OpenAI adapter with security controls
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model to use (gpt-4, gpt-3.5-turbo)
            temperature: Generation temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
            glossary_path: Path to medical glossary CSV
            validate_phi: Whether to validate PHI removal
            require_baa: Whether BAA is required (set True for production)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not installed")
            
        # API setup
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required")
            
        openai.api_key = self.api_key
        
        # Model configuration
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Security settings
        self.validate_phi = validate_phi
        self.require_baa = require_baa
        self.phi_validator = PHIValidator()
        
        # PHI placeholder pattern
        self.phi_pattern = re.compile(r'__PHI_[A-Z]+_\d+__')
        
        # Load glossary
        self.glossary = {}
        if glossary_path and Path(glossary_path).exists():
            self.load_glossary(glossary_path)
            
        # Translation cache (for cost optimization)
        self.cache = {}
        self.cache_hits = 0
        self.api_calls = 0
        
        # Audit log
        self.audit_log = []
        
        logger.info(f"OpenAI adapter initialized with model {model}")
        if self.require_baa:
            logger.warning("BAA required mode - ensure BAA is in place!")
            
    def load_glossary(self, glossary_path: str):
        """Load medical glossary for terminology guidance"""
        import csv
        
        with open(glossary_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row.get('es_term', '').lower().strip()
                en_term = row.get('en_term', '').strip()
                if es_term and en_term:
                    self.glossary[es_term] = en_term
                    
        logger.info(f"Loaded {len(self.glossary)} glossary entries")
        
    def create_system_prompt(self, include_glossary: bool = True) -> str:
        """Create system prompt with medical context and rules"""
        prompt = """You are a medical translator specializing in Mexican Spanish to US English translation.

CRITICAL RULES:
1. NEVER translate or modify any __PHI_*__ placeholders - keep them exactly as they appear
2. Use standard US medical terminology
3. Preserve all medical measurements and units
4. Maintain clinical tone and precision
5. Expand Mexican medical abbreviations when clear

MEXICAN MEDICAL CONTEXT:
- IMSS/ISSSTE: Mexican health insurance systems
- Derechohabiente: Beneficiary/insured person
- Consulta externa: Outpatient visit
- Urgencias: Emergency room
- Expediente clínico: Clinical/medical record

MEDICATION NOTES:
- Metamizol → Dipyrone (note: restricted in US)
- Clonixinato de lisina → Lysine clonixinate
- Paracetamol → Acetaminophen
"""
        
        if include_glossary and self.glossary:
            # Add top glossary terms to prompt
            glossary_sample = list(self.glossary.items())[:20]
            glossary_text = "\nKEY TERMS:\n"
            for es, en in glossary_sample:
                glossary_text += f"- {es} → {en}\n"
            prompt += glossary_text
            
        prompt += "\nTranslate the following medical text from Mexican Spanish to US English:"
        
        return prompt
        
    def validate_and_clean(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Validate text is safe and extract metadata
        Returns (cleaned_text, metadata)
        """
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'has_phi_placeholders': False,
            'detected_phi': {},
            'is_safe': True
        }
        
        # Check for PHI placeholders
        placeholders = self.phi_pattern.findall(text)
        metadata['has_phi_placeholders'] = len(placeholders) > 0
        metadata['placeholder_count'] = len(placeholders)
        
        # Validate PHI removal if required
        if self.validate_phi:
            is_safe, detected_phi = self.phi_validator.validate_deidentified(text)
            metadata['is_safe'] = is_safe
            metadata['detected_phi'] = detected_phi
            
            if not is_safe and self.require_baa:
                raise ValueError(f"PHI detected without BAA: {detected_phi}")
            elif not is_safe:
                logger.warning(f"Potential PHI detected: {detected_phi}")
                
        return text, metadata
        
    def verify_placeholder_integrity(self, original: str, translated: str) -> bool:
        """Verify all PHI placeholders are preserved exactly"""
        original_placeholders = sorted(self.phi_pattern.findall(original))
        translated_placeholders = sorted(self.phi_pattern.findall(translated))
        
        if original_placeholders != translated_placeholders:
            logger.error(f"Placeholder mismatch!")
            logger.error(f"Original: {original_placeholders}")
            logger.error(f"Translated: {translated_placeholders}")
            return False
            
        return True
        
    def apply_glossary_corrections(self, text: str) -> str:
        """Apply glossary-based corrections to translation"""
        corrected = text
        
        # Simple glossary enforcement (can be improved)
        for es_term, en_term in self.glossary.items():
            # Check if Spanish term still exists (shouldn't happen)
            if es_term in corrected.lower():
                # Replace with English term
                pattern = re.compile(re.escape(es_term), re.IGNORECASE)
                corrected = pattern.sub(en_term, corrected)
                
        return corrected
        
    def translate(self, 
                 text: str,
                 use_cache: bool = True,
                 retry_on_error: bool = True,
                 max_retries: int = 3) -> str:
        """
        Translate medical text with PHI protection
        
        Args:
            text: Text to translate (must be de-identified)
            use_cache: Whether to use translation cache
            retry_on_error: Whether to retry on API errors
            max_retries: Maximum number of retry attempts
            
        Returns:
            Translated text with PHI placeholders preserved
        """
        if not text or not text.strip():
            return text
            
        # Check cache
        if use_cache:
            cache_key = hashlib.md5(text.encode()).hexdigest()
            if cache_key in self.cache:
                self.cache_hits += 1
                logger.debug(f"Cache hit (total: {self.cache_hits})")
                return self.cache[cache_key]
                
        try:
            # Validate and clean text
            cleaned_text, metadata = self.validate_and_clean(text)
            
            if not metadata['is_safe'] and self.require_baa:
                logger.error("Unsafe text rejected - PHI detected without BAA")
                return text  # Return original
                
            # Create messages for API
            messages = [
                {"role": "system", "content": self.create_system_prompt()},
                {"role": "user", "content": cleaned_text}
            ]
            
            # API call with retry logic
            retries = 0
            while retries <= max_retries:
                try:
                    response = openai.ChatCompletion.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        n=1,
                        stop=None
                    )
                    
                    self.api_calls += 1
                    break
                    
                except openai.error.RateLimitError:
                    retries += 1
                    if retries > max_retries:
                        raise
                    wait_time = 2 ** retries  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s")
                    time.sleep(wait_time)
                    
                except openai.error.OpenAIError as e:
                    logger.error(f"OpenAI API error: {e}")
                    if not retry_on_error or retries >= max_retries:
                        raise
                    retries += 1
                    
            # Extract translation
            translated = response.choices[0].message.content.strip()
            
            # Verify placeholder integrity
            if metadata['has_phi_placeholders']:
                if not self.verify_placeholder_integrity(text, translated):
                    logger.error("Placeholder integrity check failed")
                    return text  # Return original on integrity failure
                    
            # Apply glossary corrections
            if self.glossary:
                translated = self.apply_glossary_corrections(translated)
                
            # Update cache
            if use_cache:
                self.cache[cache_key] = translated
                
            # Log for audit
            self.audit_log.append({
                'timestamp': metadata['timestamp'],
                'model': self.model,
                'tokens_used': response.usage.total_tokens,
                'cached': False,
                'safe': metadata['is_safe']
            })
            
            return translated
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text  # Return original on error
            
    def translate_batch(self, 
                       texts: List[str],
                       batch_size: int = 5) -> List[str]:
        """Translate multiple texts with batching for efficiency"""
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            for text in batch:
                translated = self.translate(text)
                results.append(translated)
                
            # Small delay between batches to avoid rate limits
            if i + batch_size < len(texts):
                time.sleep(0.5)
                
        return results
        
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            'api_calls': self.api_calls,
            'cache_hits': self.cache_hits,
            'cache_size': len(self.cache),
            'cache_hit_rate': self.cache_hits / (self.api_calls + self.cache_hits) if (self.api_calls + self.cache_hits) > 0 else 0,
            'audit_log_size': len(self.audit_log)
        }
        
    def estimate_cost(self, text: str) -> float:
        """Estimate API cost for translation"""
        # Rough token estimation (1 token ≈ 4 chars)
        estimated_tokens = len(text) / 4
        
        # Pricing (as of 2024, verify current rates)
        if 'gpt-4' in self.model:
            input_cost = 0.03 / 1000  # $0.03 per 1K tokens
            output_cost = 0.06 / 1000  # $0.06 per 1K tokens
        else:  # GPT-3.5
            input_cost = 0.001 / 1000
            output_cost = 0.002 / 1000
            
        # Assume output is similar length to input
        estimated_cost = (estimated_tokens * input_cost) + (estimated_tokens * output_cost)
        
        return estimated_cost


def create_test_suite():
    """Create test cases for PHI protection validation"""
    test_cases = [
        {
            'name': 'Basic PHI preservation',
            'input': 'El paciente __PHI_NAME_001__ tiene __PHI_AGE_001__ años.',
            'expected_phi': ['__PHI_NAME_001__', '__PHI_AGE_001__']
        },
        {
            'name': 'Medical terms with PHI',
            'input': 'Paciente __PHI_NAME_001__ con HTA y DM2. NSS: __PHI_ID_001__',
            'expected_phi': ['__PHI_NAME_001__', '__PHI_ID_001__']
        },
        {
            'name': 'Detect unmasked CURP',
            'input': 'CURP: HEGG930815MDFRRN09',
            'should_fail': True
        },
        {
            'name': 'Detect unmasked NSS',
            'input': 'NSS del paciente: 12345678901',
            'should_fail': True
        }
    ]
    
    return test_cases


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenAI Adapter for Medical Translation")
    parser.add_argument('--test', action='store_true', help='Run safety tests')
    parser.add_argument('--text', type=str, help='Text to translate')
    parser.add_argument('--dry-run', action='store_true', help='Validate without calling API')
    parser.add_argument('--glossary', type=str, help='Path to glossary CSV')
    parser.add_argument('--require-baa', action='store_true', help='Require BAA compliance')
    
    args = parser.parse_args()
    
    if args.test:
        # Run test suite
        print("Running PHI protection tests...\n")
        
        validator = PHIValidator()
        test_cases = create_test_suite()
        
        for test in test_cases:
            print(f"Test: {test['name']}")
            is_safe, detected = validator.validate_deidentified(test['input'])
            
            if test.get('should_fail'):
                if not is_safe:
                    print("  ✅ Correctly detected PHI")
                else:
                    print("  ❌ Failed to detect PHI")
            else:
                if is_safe:
                    print("  ✅ Validated as safe")
                else:
                    print(f"  ❌ False positive: {detected}")
                    
            print()
            
    elif args.text or args.dry_run:
        # Initialize adapter
        try:
            adapter = OpenAISecureAdapter(
                glossary_path=args.glossary,
                require_baa=args.require_baa
            )
        except ImportError:
            print("OpenAI library not installed. Install with: pip install openai")
            exit(1)
        except ValueError as e:
            print(f"Configuration error: {e}")
            exit(1)
            
        if args.text:
            test_text = args.text
        else:
            # Default test text
            test_text = """
            Paciente __PHI_NAME_001__ de __PHI_AGE_001__ años.
            Diagnóstico: HTA controlada, DM2.
            Medicamentos: Metformina 850mg c/12h, Losartán 50mg c/24h.
            Próxima cita: consulta externa en 2 meses.
            """
            
        print(f"Original:\n{test_text}\n")
        
        if args.dry_run:
            # Just validate
            is_safe, detected = adapter.phi_validator.validate_deidentified(test_text)
            print(f"PHI Validation: {'SAFE' if is_safe else 'UNSAFE'}")
            if detected:
                print(f"Detected PHI: {detected}")
                
            cost = adapter.estimate_cost(test_text)
            print(f"Estimated cost: ${cost:.4f}")
        else:
            # Translate
            translated = adapter.translate(test_text)
            print(f"Translated:\n{translated}\n")
            
            # Show stats
            stats = adapter.get_stats()
            print(f"Stats: {stats}")
            
    else:
        parser.print_help()