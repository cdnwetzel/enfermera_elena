#!/usr/bin/env python3
"""
ALIA-40b Adapter for Enfermera Elena
Spanish-native LLM for medical translation via vLLM
"""

import re
import json
import logging
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
import requests
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TranslationMode(Enum):
    """Translation modes for different use cases"""
    DIRECT = "direct"  # Simple translation
    MEDICAL = "medical"  # Medical context with terminology
    CLINICAL = "clinical"  # Clinical notes with abbreviations
    ADMINISTRATIVE = "administrative"  # IMSS/ISSSTE documents


@dataclass
class MedicalContext:
    """Medical context for enhanced translation"""
    document_type: str = "general"
    institution: str = "IMSS"
    specialty: str = "general"
    include_glossary: bool = True
    expand_abbreviations: bool = True
    preserve_format: bool = True


class ALIAMedicalTranslator:
    """
    ALIA-40b medical translator with vLLM backend
    Optimized for Mexican Spanish medical documents
    """
    
    def __init__(self,
                 vllm_url: str = "http://localhost:8504",
                 model_name: str = "ALIA-40b",
                 timeout: int = 60,
                 max_retries: int = 3,
                 cache_enabled: bool = True,
                 glossary_path: Optional[str] = None):
        """
        Initialize ALIA translator
        
        Args:
            vllm_url: vLLM server URL
            model_name: Model name for API calls
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            cache_enabled: Enable translation caching
            glossary_path: Path to medical glossary CSV
        """
        self.vllm_url = vllm_url.rstrip('/')
        self.model_name = model_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_enabled = cache_enabled
        
        # PHI placeholder pattern
        self.phi_pattern = re.compile(r'__PHI_[A-Z]+_\d+__')
        
        # Translation cache
        self.cache = {} if cache_enabled else None
        self.cache_hits = 0
        self.api_calls = 0
        
        # Medical glossary
        self.glossary = {}
        if glossary_path and Path(glossary_path).exists():
            self.load_glossary(glossary_path)
            
        # Mexican medical abbreviations
        self.abbreviations = {
            'HTA': 'Hipertensión Arterial',
            'HAS': 'Hipertensión Arterial Sistémica',
            'DM': 'Diabetes Mellitus',
            'DM2': 'Diabetes Mellitus Tipo 2',
            'DM1': 'Diabetes Mellitus Tipo 1',
            'IAM': 'Infarto Agudo al Miocardio',
            'IMA': 'Infarto al Miocardio Agudo',
            'EVC': 'Evento Vascular Cerebral',
            'ECV': 'Evento Cerebro Vascular',
            'ACV': 'Accidente Cerebrovascular',
            'EPOC': 'Enfermedad Pulmonar Obstructiva Crónica',
            'IRC': 'Insuficiencia Renal Crónica',
            'IRA': 'Insuficiencia Renal Aguda',
            'IVU': 'Infección de Vías Urinarias',
            'IVRS': 'Infección de Vías Respiratorias Superiores',
            'IVRI': 'Infección de Vías Respiratorias Inferiores',
            'CA': 'Cáncer',
            'Ca': 'Cáncer',
            'Cx': 'Cirugía',
            'Qx': 'Quirúrgico',
            'Tx': 'Tratamiento',
            'Dx': 'Diagnóstico',
            'Rx': 'Radiografía',
            'TAC': 'Tomografía Axial Computarizada',
            'RM': 'Resonancia Magnética',
            'USG': 'Ultrasonografía',
            'ECG': 'Electrocardiograma',
            'EKG': 'Electrocardiograma',
            'BH': 'Biometría Hemática',
            'QS': 'Química Sanguínea',
            'EGO': 'Examen General de Orina',
            'PFH': 'Pruebas de Función Hepática',
            'PFR': 'Pruebas de Función Renal',
            'VSG': 'Velocidad de Sedimentación Globular',
            'PCR': 'Proteína C Reactiva',
            'TA': 'Tensión Arterial',
            'PA': 'Presión Arterial',
            'FC': 'Frecuencia Cardíaca',
            'FR': 'Frecuencia Respiratoria',
            'T': 'Temperatura',
            'SatO2': 'Saturación de Oxígeno',
            'SpO2': 'Saturación de Oxígeno',
        }
        
        # Mexican medication mappings
        self.medications = {
            'metamizol': 'dipyrone/metamizole',
            'metamizol sódico': 'metamizole sodium',
            'neo-melubrina': 'dipyrone',
            'paracetamol': 'acetaminophen',
            'tempra': 'acetaminophen',
            'clonixinato de lisina': 'lysine clonixinate',
            'dolac': 'lysine clonixinate',
            'ketorolaco': 'ketorolac',
            'butilhioscina': 'hyoscine butylbromide',
            'buscapina': 'hyoscine butylbromide',
            'salbutamol': 'albuterol',
            'ambroxol': 'ambroxol (mucolytic)',
            'trimetoprim con sulfametoxazol': 'trimethoprim-sulfamethoxazole',
            'complejo b': 'vitamin B complex',
        }
        
        # IMSS/ISSSTE terminology
        self.institutional_terms = {
            'derechohabiente': 'beneficiary/insured person',
            'consulta externa': 'outpatient consultation',
            'urgencias': 'emergency department',
            'urgencias calificadas': 'qualified emergency',
            'hospitalización': 'hospitalization',
            'expediente clínico': 'clinical record',
            'historia clínica': 'medical history',
            'nota médica': 'medical note',
            'nota de evolución': 'progress note',
            'nota de ingreso': 'admission note',
            'nota de egreso': 'discharge note',
            'receta médica': 'medical prescription',
            'certificado de incapacidad': 'disability certificate',
            'cuadro básico': 'essential medicines formulary',
            'pase a especialidad': 'specialty referral',
            'contrarreferencia': 'counter-referral',
            'médico familiar': 'family physician',
            'médico tratante': 'attending physician',
            'unidad médica': 'medical unit',
            'turno matutino': 'morning shift',
            'turno vespertino': 'evening shift',
            'turno nocturno': 'night shift',
        }
        
        # Check server availability
        self.check_server()
        
    def check_server(self) -> bool:
        """Check if vLLM server is available"""
        try:
            response = requests.get(
                f"{self.vllm_url}/v1/models",
                timeout=5
            )
            if response.status_code == 200:
                models = response.json()
                logger.info(f"vLLM server available with models: {models}")
                return True
        except requests.exceptions.RequestException as e:
            logger.error(f"vLLM server not available: {e}")
            logger.info("Start server with: ./scripts/deploy_alia_vllm.sh")
            return False
            
    def load_glossary(self, glossary_path: str):
        """Load medical glossary from CSV"""
        import csv
        
        with open(glossary_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row.get('es_term', '').lower().strip()
                en_term = row.get('en_term', '').strip()
                if es_term and en_term:
                    self.glossary[es_term] = en_term
                    
        logger.info(f"Loaded {len(self.glossary)} glossary entries")
        
    def create_medical_prompt(self, 
                             text: str,
                             context: MedicalContext) -> str:
        """
        Create specialized prompt for medical translation
        
        Args:
            text: Spanish medical text
            context: Medical context for translation
            
        Returns:
            Formatted prompt for ALIA
        """
        # Base instruction
        prompt = f"""Eres un traductor médico especializado en documentos del sistema de salud mexicano.
Tu tarea es traducir del español mexicano médico al inglés médico estadounidense.

CONTEXTO DEL DOCUMENTO:
- Tipo: {context.document_type}
- Institución: {context.institution}
- Especialidad: {context.specialty}

INSTRUCCIONES CRÍTICAS:
1. PRESERVA EXACTAMENTE todos los marcadores __PHI_*__ sin modificarlos
2. Traduce terminología médica mexicana a equivalentes estadounidenses
3. Expande abreviaturas médicas mexicanas cuando sea apropiado
4. Mantén el tono clínico profesional
5. Conserva medidas y unidades (mg, ml, mmHg)
"""
        
        # Add medication mappings if relevant
        if 'medicam' in text.lower() or 'fármaco' in text.lower():
            prompt += """
MEDICAMENTOS MEXICANOS → US:
- Metamizol → Dipyrone (note: restricted in US)
- Paracetamol → Acetaminophen
- Clonixinato de lisina → Lysine clonixinate
- Butilhioscina → Hyoscine butylbromide
- Salbutamol → Albuterol
"""
        
        # Add abbreviation expansions if requested
        if context.expand_abbreviations:
            prompt += """
ABREVIATURAS COMUNES:
- HTA/HAS → Hypertension
- DM2 → Type 2 Diabetes Mellitus
- IAM → Acute Myocardial Infarction
- EVC → Stroke/Cerebrovascular Event
- EPOC → COPD
- IRC → Chronic Renal Insufficiency
"""
        
        # Add institutional terms if IMSS/ISSSTE document
        if context.institution in ['IMSS', 'ISSSTE']:
            prompt += """
TÉRMINOS INSTITUCIONALES:
- Derechohabiente → Beneficiary/Insured person
- Consulta externa → Outpatient consultation
- Urgencias → Emergency department
- Expediente clínico → Clinical/Medical record
- Cuadro básico → Essential medicines formulary
"""
        
        # Add the text to translate
        prompt += f"""
TEXTO MÉDICO EN ESPAÑOL:
{text}

TRADUCCIÓN AL INGLÉS MÉDICO:"""
        
        return prompt
        
    def extract_placeholders(self, text: str) -> Tuple[str, List[str]]:
        """
        Extract and validate PHI placeholders
        
        Returns:
            Tuple of (text, list of placeholders)
        """
        placeholders = self.phi_pattern.findall(text)
        return text, placeholders
        
    def validate_placeholders(self, 
                            original_placeholders: List[str],
                            translated_text: str) -> bool:
        """
        Validate all PHI placeholders are preserved
        
        Returns:
            True if all placeholders intact, False otherwise
        """
        translated_placeholders = self.phi_pattern.findall(translated_text)
        
        original_set = set(original_placeholders)
        translated_set = set(translated_placeholders)
        
        if original_set != translated_set:
            missing = original_set - translated_set
            extra = translated_set - original_set
            
            if missing:
                logger.error(f"Missing placeholders: {missing}")
            if extra:
                logger.error(f"Extra placeholders: {extra}")
                
            return False
            
        # Check order is preserved (important for context)
        if original_placeholders != translated_placeholders:
            logger.warning("Placeholder order changed")
            
        return True
        
    def apply_glossary_fixes(self, text: str) -> str:
        """Apply glossary-based corrections to translation"""
        result = text
        
        # Apply known medication mappings
        for mx_drug, us_drug in self.medications.items():
            # Case-insensitive replacement
            pattern = re.compile(re.escape(mx_drug), re.IGNORECASE)
            result = pattern.sub(us_drug, result)
            
        return result
        
    def translate(self,
                 text: str,
                 mode: TranslationMode = TranslationMode.MEDICAL,
                 context: Optional[MedicalContext] = None,
                 temperature: float = 0.3,
                 max_tokens: int = 2048) -> str:
        """
        Translate medical text using ALIA-40b
        
        Args:
            text: Spanish medical text to translate
            mode: Translation mode
            context: Medical context for enhanced translation
            temperature: LLM temperature (0-1)
            max_tokens: Maximum output tokens
            
        Returns:
            Translated English text with PHI preserved
        """
        if not text or not text.strip():
            return text
            
        # Use cache if enabled
        if self.cache_enabled:
            cache_key = hashlib.md5(
                f"{text}:{mode.value}:{temperature}".encode()
            ).hexdigest()
            
            if cache_key in self.cache:
                self.cache_hits += 1
                logger.debug(f"Cache hit ({self.cache_hits} total)")
                return self.cache[cache_key]
                
        # Extract PHI placeholders
        original_text, placeholders = self.extract_placeholders(text)
        
        # Use default context if not provided
        if context is None:
            context = MedicalContext()
            
        try:
            # Create appropriate prompt based on mode
            if mode == TranslationMode.DIRECT:
                prompt = f"Translate from Spanish to English: {text}"
            else:
                prompt = self.create_medical_prompt(text, context)
                
            # Prepare API request
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stop": None,
                "stream": False
            }
            
            # Make API call with retry logic
            for attempt in range(self.max_retries):
                try:
                    response = requests.post(
                        f"{self.vllm_url}/v1/chat/completions",
                        json=payload,
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        self.api_calls += 1
                        break
                    else:
                        logger.warning(f"API returned {response.status_code}")
                        if attempt < self.max_retries - 1:
                            time.sleep(2 ** attempt)  # Exponential backoff
                            
                except requests.exceptions.Timeout:
                    logger.warning(f"Request timeout on attempt {attempt + 1}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                    else:
                        raise
                        
            # Extract translation
            result = response.json()
            translated = result['choices'][0]['message']['content'].strip()
            
            # Validate PHI preservation
            if placeholders:
                if not self.validate_placeholders(placeholders, translated):
                    logger.error("PHI validation failed, returning original")
                    return text
                    
            # Apply glossary fixes if medical mode
            if mode in [TranslationMode.MEDICAL, TranslationMode.CLINICAL]:
                translated = self.apply_glossary_fixes(translated)
                
            # Cache the result
            if self.cache_enabled:
                self.cache[cache_key] = translated
                
            return translated
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text  # Return original on error
            
    def translate_batch(self,
                       texts: List[str],
                       mode: TranslationMode = TranslationMode.MEDICAL,
                       batch_size: int = 4) -> List[str]:
        """
        Translate multiple texts efficiently
        
        Args:
            texts: List of Spanish texts
            mode: Translation mode
            batch_size: Number of texts per batch
            
        Returns:
            List of translated texts
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            
            # Process batch
            for text in batch:
                translated = self.translate(text, mode)
                results.append(translated)
                
            # Small delay between batches
            if i + batch_size < len(texts):
                time.sleep(0.5)
                
        return results
        
    def translate_document(self,
                          document: str,
                          document_type: str = "clinical_note") -> str:
        """
        Translate entire document with appropriate context
        
        Args:
            document: Full document text
            document_type: Type of medical document
            
        Returns:
            Translated document
        """
        # Determine translation mode based on document type
        mode_mapping = {
            'clinical_note': TranslationMode.CLINICAL,
            'prescription': TranslationMode.MEDICAL,
            'lab_report': TranslationMode.MEDICAL,
            'discharge_summary': TranslationMode.CLINICAL,
            'referral': TranslationMode.ADMINISTRATIVE,
            'insurance_form': TranslationMode.ADMINISTRATIVE,
        }
        
        mode = mode_mapping.get(document_type, TranslationMode.MEDICAL)
        
        # Create context
        context = MedicalContext(
            document_type=document_type,
            institution='IMSS' if 'IMSS' in document else 'general',
            expand_abbreviations=True
        )
        
        # Split into paragraphs for better processing
        paragraphs = document.split('\n\n')
        translated_paragraphs = []
        
        for para in paragraphs:
            if para.strip():
                translated = self.translate(para, mode, context)
                translated_paragraphs.append(translated)
            else:
                translated_paragraphs.append('')
                
        return '\n\n'.join(translated_paragraphs)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get translation statistics"""
        total_requests = self.api_calls + self.cache_hits
        
        return {
            'api_calls': self.api_calls,
            'cache_hits': self.cache_hits,
            'cache_size': len(self.cache) if self.cache else 0,
            'cache_hit_rate': self.cache_hits / total_requests if total_requests > 0 else 0,
            'total_translations': total_requests
        }
        

def create_test_cases():
    """Create test cases for ALIA medical translation"""
    return [
        {
            'name': 'Basic medical with PHI',
            'input': 'El paciente __PHI_NAME_001__ presenta HTA controlada con Losartán 50mg c/12h.',
            'expected_keywords': ['patient', 'hypertension', 'controlled', 'Losartan', '50mg']
        },
        {
            'name': 'Mexican medications',
            'input': 'Prescripción: Metamizol 500mg, Paracetamol 500mg, Clonixinato de lisina 125mg',
            'expected_keywords': ['dipyrone', 'acetaminophen', 'lysine clonixinate']
        },
        {
            'name': 'IMSS terminology',
            'input': 'Derechohabiente acude a consulta externa en la unidad médica',
            'expected_keywords': ['beneficiary', 'outpatient', 'medical unit']
        },
        {
            'name': 'Medical abbreviations',
            'input': 'Dx: DM2, HTA, EPOC. Tx: Control metabólico',
            'expected_keywords': ['Type 2 Diabetes', 'Hypertension', 'COPD', 'Treatment']
        },
        {
            'name': 'Vital signs',
            'input': 'TA: 130/80 mmHg, FC: 72 lpm, T: 36.5°C, SatO2: 98%',
            'expected_keywords': ['130/80', 'mmHg', '72', '36.5°C', '98%']
        }
    ]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ALIA-40b Medical Translator")
    parser.add_argument('--test', action='store_true', help='Run test cases')
    parser.add_argument('--text', type=str, help='Text to translate')
    parser.add_argument('--mode', type=str, default='medical',
                       choices=['direct', 'medical', 'clinical', 'administrative'])
    parser.add_argument('--server', type=str, default='http://localhost:8504',
                       help='vLLM server URL')
    parser.add_argument('--glossary', type=str, help='Path to glossary CSV')
    
    args = parser.parse_args()
    
    # Initialize translator
    translator = ALIAMedicalTranslator(
        vllm_url=args.server,
        glossary_path=args.glossary
    )
    
    if args.test:
        print("Running ALIA medical translation tests...\n")
        
        test_cases = create_test_cases()
        for test in test_cases:
            print(f"Test: {test['name']}")
            print(f"Input: {test['input']}")
            
            translated = translator.translate(
                test['input'],
                mode=TranslationMode.MEDICAL
            )
            
            print(f"Output: {translated}")
            
            # Check for expected keywords
            found_keywords = [kw for kw in test['expected_keywords'] 
                            if kw.lower() in translated.lower()]
            
            if len(found_keywords) == len(test['expected_keywords']):
                print("✅ All expected keywords found")
            else:
                missing = set(test['expected_keywords']) - set(found_keywords)
                print(f"⚠️  Missing keywords: {missing}")
                
            print()
            
        # Show statistics
        stats = translator.get_stats()
        print(f"\nStatistics: {stats}")
        
    elif args.text:
        # Translate provided text
        mode = TranslationMode[args.mode.upper()]
        
        print(f"Mode: {mode.value}")
        print(f"Original:\n{args.text}\n")
        
        translated = translator.translate(args.text, mode)
        
        print(f"Translated:\n{translated}\n")
        
        # Check PHI preservation
        original_phi = translator.phi_pattern.findall(args.text)
        translated_phi = translator.phi_pattern.findall(translated)
        
        if original_phi:
            if original_phi == translated_phi:
                print("✅ PHI placeholders preserved")
            else:
                print("❌ PHI placeholders modified!")
                
    else:
        # Default test
        test_text = """
        Paciente __PHI_NAME_001__ de __PHI_AGE_001__ años.
        
        Diagnóstico: HTA, DM2 controlada.
        
        Medicamentos:
        - Metformina 850mg c/12h
        - Losartán 50mg c/24h  
        - Metamizol 500mg PRN dolor
        
        Próxima cita: Consulta externa en 2 meses.
        """
        
        print("Default test translation:")
        print(f"Original:\n{test_text}\n")
        
        translated = translator.translate(test_text)
        print(f"Translated:\n{translated}")
        
        stats = translator.get_stats()
        print(f"\nStats: {stats}")