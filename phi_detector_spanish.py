#!/usr/bin/env python3
"""
HIPAA-Compliant PHI Detection for Spanish Medical Records
Handles all 18 HIPAA identifiers in both Spanish and English contexts
"""

import re
from typing import Dict, List, Tuple, Set
from datetime import datetime
import hashlib
import json
from pathlib import Path

class SpanishMedicalPHIDetector:
    """
    Detects all 18 HIPAA PHI identifiers in Spanish medical documents
    """
    
    def __init__(self):
        # Spanish medical record acronyms and terms
        self.spanish_medical_terms = {
            # Medical Record Numbers
            'NHC': 'Número de Historia Clínica',
            'NSS': 'Número de Seguridad Social',
            'CURP': 'Clave Única de Registro de Población',
            'RFC': 'Registro Federal de Contribuyentes',
            'IMSS': 'Instituto Mexicano del Seguro Social',
            'ISSSTE': 'Instituto de Seguridad Social',
            'NE': 'Número de Expediente',
            'FOLIO': 'Número de Folio',
            'PÓLIZA': 'Número de Póliza',
            'AFILIACIÓN': 'Número de Afiliación',
            
            # Personal identifiers
            'INE': 'Instituto Nacional Electoral',
            'IFE': 'Instituto Federal Electoral (old)',
            'PASAPORTE': 'Passport Number',
            'LICENCIA': 'License Number',
            
            # Date-related
            'FDN': 'Fecha de Nacimiento',
            'F.NAC': 'Fecha de Nacimiento',
            'FECHA NAC': 'Fecha de Nacimiento',
            'INGRESO': 'Fecha de Ingreso',
            'EGRESO': 'Fecha de Egreso',
            'ALTA': 'Fecha de Alta',
            'DEFUNCIÓN': 'Fecha de Defunción',
        }
        
        self._build_patterns()
        self.phi_found = []
        self.audit_log = []
    
    def _build_patterns(self):
        """Build regex patterns for all 18 HIPAA identifiers"""
        
        self.patterns = {
            # 1. Names (Spanish names often have 2 surnames)
            'name_spanish': re.compile(
                r'\b(?:NOMBRE|PACIENTE|TITULAR|BENEFICIARIO|ASEGURADO|MÉDICO|DR\.?|DRA\.?)[:\s]*'
                r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,4})\b',
                re.IGNORECASE
            ),
            'name_general': re.compile(
                r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s+'  # First name
                r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s+'     # Paternal surname
                r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b'      # Maternal surname (common in Mexico)
            ),
            
            # 2. Geographic subdivisions (Mexican format)
            'address_mexico': re.compile(
                r'(?:CALLE|AV\.?|AVENIDA|BLVD|BOULEVARD|CARRETERA|CAMINO)\s+'
                r'[^,\n]+(?:,\s*)?'
                r'(?:COL\.?|COLONIA|FRACC\.?|FRACCIONAMIENTO)\s+[^,\n]+(?:,\s*)?'
                r'(?:C\.?P\.?\s*\d{5})?(?:,\s*)?'
                r'(?:DEL\.?|MUNICIPIO|CIUDAD)\s+[^,\n]+',
                re.IGNORECASE
            ),
            'zip_mexico': re.compile(r'\bC\.?P\.?\s*(\d{5})\b'),
            
            # 3. Dates (Mexican format DD/MM/YYYY or DD-MM-YYYY)
            'date_mexican': re.compile(
                r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4}|\d{2})\b'
            ),
            'date_text': re.compile(
                r'\b(\d{1,2})\s+(?:DE\s+)?'
                r'(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)'
                r'\s+(?:DE\s+)?(\d{4})\b',
                re.IGNORECASE
            ),
            
            # 4. Phone numbers (Mexican format)
            'phone_mexico': re.compile(
                r'\b(?:TEL\.?|TELÉFONO|CEL\.?|CELULAR|MÓVIL)[:\s]*'
                r'(?:\+52\s*)?'
                r'(?:\d{2,3}[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b',
                re.IGNORECASE
            ),
            'phone_general': re.compile(
                r'\b(?:\+52\s*)?(?:\d{2,3}[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b'
            ),
            
            # 5. Fax numbers
            'fax': re.compile(
                r'\bFAX[:\s]*(?:\+52\s*)?(?:\d{2,3}[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b',
                re.IGNORECASE
            ),
            
            # 6. Email addresses
            'email': re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
            
            # 7. Social Security Numbers (Mexican NSS is 11 digits)
            'nss_mexico': re.compile(
                r'\b(?:NSS|IMSS|SEGURO\s+SOCIAL)[:\s#]*(\d{11})\b',
                re.IGNORECASE
            ),
            
            # 8. Medical Record Numbers (various Mexican formats)
            'medical_record': re.compile(
                r'\b(?:NHC|HC|HISTORIA\s+CLÍNICA|EXPEDIENTE|NE|FOLIO|FICHA)'
                r'[:\s#]*([A-Z0-9\-]+)\b',
                re.IGNORECASE
            ),
            
            # 9. Health Plan Numbers
            'insurance_number': re.compile(
                r'\b(?:PÓLIZA|POLIZA|AFILIACIÓN|AFILIACION|CONTRATO|CERTIFICADO)'
                r'[:\s#]*([A-Z0-9\-]+)\b',
                re.IGNORECASE
            ),
            
            # 10. Account numbers
            'account': re.compile(
                r'\b(?:CUENTA|CTA\.?|REFERENCIA|REF\.?)[:\s#]*([A-Z0-9\-]+)\b',
                re.IGNORECASE
            ),
            
            # 11. License numbers (Mexican)
            'license': re.compile(
                r'\b(?:LICENCIA|LIC\.?|CÉDULA|CED\.?|MATRÍCULA)[:\s#]*([A-Z0-9\-]+)\b',
                re.IGNORECASE
            ),
            
            # 12. Vehicle identifiers
            'vehicle': re.compile(
                r'\b(?:PLACA|PLACAS|VIN|SERIE)[:\s#]*([A-Z0-9\-]+)\b',
                re.IGNORECASE
            ),
            
            # 13. Device identifiers
            'device': re.compile(
                r'\b(?:SERIE|MODELO|LOTE|ID\s+DISPOSITIVO)[:\s#]*([A-Z0-9\-]+)\b',
                re.IGNORECASE
            ),
            
            # 14. URLs
            'url': re.compile(
                r'https?://[^\s<>"{}|\\^`\[\]]+'
            ),
            
            # 15. IP addresses
            'ip': re.compile(
                r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            ),
            
            # 16. Biometric identifiers (rarely in text)
            'biometric': re.compile(
                r'\b(?:HUELLA|RETINA|IRIS|ADN|DNA|BIOMÉTRICO)[:\s]*[A-Z0-9]+\b',
                re.IGNORECASE
            ),
            
            # 17. Photos (references to)
            'photo_ref': re.compile(
                r'\b(?:FOTO|FOTOGRAFÍA|IMAGEN|IMG)[:\s]*[^\s]+\.(jpg|jpeg|png|gif|bmp)\b',
                re.IGNORECASE
            ),
            
            # 18. CURP (Mexican unique population registry - 18 chars)
            'curp': re.compile(
                r'\b(?:CURP)[:\s]*([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b',
                re.IGNORECASE
            ),
            
            # RFC (Mexican tax ID)
            'rfc': re.compile(
                r'\b(?:RFC)[:\s]*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})\b',
                re.IGNORECASE
            ),
            
            # INE/IFE (Mexican voter ID)
            'ine': re.compile(
                r'\b(?:INE|IFE|ELECTOR)[:\s]*(\d{13,18})\b',
                re.IGNORECASE
            ),
            
            # Age over 89 (HIPAA requirement)
            'age_over_89': re.compile(
                r'\b(?:EDAD|AÑOS)[:\s]*([9-9]\d|1\d{2})\s*(?:AÑOS)?\b',
                re.IGNORECASE
            ),
        }
    
    def detect_phi(self, text: str) -> Dict[str, List[Tuple[str, int, int]]]:
        """
        Detect all PHI in the text
        Returns dict with PHI type as key and list of (value, start, end) tuples
        """
        phi_found = {}
        
        for phi_type, pattern in self.patterns.items():
            matches = []
            for match in pattern.finditer(text):
                # Get the full match or first group if available
                value = match.group(1) if match.groups() else match.group(0)
                matches.append((value, match.start(), match.end()))
            
            if matches:
                phi_found[phi_type] = matches
        
        # Log the detection
        self._log_detection(text, phi_found)
        
        return phi_found
    
    def _log_detection(self, text: str, phi_found: Dict):
        """Log PHI detection for audit trail"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'text_hash': hashlib.sha256(text.encode()).hexdigest()[:16],
            'phi_types_found': list(phi_found.keys()),
            'phi_count': sum(len(v) for v in phi_found.values())
        }
        self.audit_log.append(log_entry)
    
    def sanitize_text(self, text: str) -> Tuple[str, Dict]:
        """
        Remove all PHI from text and return sanitized version with PHI map
        """
        phi_found = self.detect_phi(text)
        phi_map = {}
        sanitized = text
        
        # Sort by position (reverse) to maintain indices while replacing
        all_phi = []
        for phi_type, matches in phi_found.items():
            for value, start, end in matches:
                all_phi.append((start, end, phi_type, value))
        
        all_phi.sort(reverse=True)
        
        # Replace PHI with placeholders
        for start, end, phi_type, value in all_phi:
            placeholder = f"[{phi_type.upper()}_{len(phi_map)}]"
            phi_map[placeholder] = {
                'type': phi_type,
                'value': value,
                'start': start,
                'end': end
            }
            sanitized = sanitized[:start] + placeholder + sanitized[end:]
        
        return sanitized, phi_map
    
    def restore_phi(self, sanitized_text: str, phi_map: Dict) -> str:
        """
        Restore PHI to sanitized text
        """
        restored = sanitized_text
        
        # Sort by placeholder appearance in text
        for placeholder, info in phi_map.items():
            restored = restored.replace(placeholder, info['value'])
        
        return restored
    
    def validate_sanitization(self, original: str, sanitized: str, restored: str) -> bool:
        """
        Validate that sanitization and restoration work correctly
        """
        # Check no PHI remains in sanitized version
        phi_in_sanitized = self.detect_phi(sanitized)
        
        # Only consider it PHI if it's not a placeholder
        real_phi = {}
        for phi_type, matches in phi_in_sanitized.items():
            real_matches = []
            for value, start, end in matches:
                if not re.match(r'\[[\w_]+_\d+\]', value):
                    real_matches.append((value, start, end))
            if real_matches:
                real_phi[phi_type] = real_matches
        
        if real_phi:
            print(f"⚠️ Warning: PHI still found in sanitized text: {list(real_phi.keys())}")
            return False
        
        # Check restoration is perfect
        if original != restored:
            print("⚠️ Warning: Restoration does not match original")
            # Find differences for debugging
            for i, (c1, c2) in enumerate(zip(original, restored)):
                if c1 != c2:
                    print(f"  First difference at position {i}: '{c1}' vs '{c2}'")
                    print(f"  Context: ...{original[max(0,i-20):i+20]}...")
                    break
            return False
        
        return True
    
    def get_audit_log(self) -> List[Dict]:
        """Return audit log for compliance"""
        return self.audit_log
    
    def save_audit_log(self, filepath: str):
        """Save audit log to file"""
        with open(filepath, 'w') as f:
            json.dump(self.audit_log, f, indent=2, ensure_ascii=False)


def test_spanish_phi_detection():
    """Test PHI detection with Spanish medical text"""
    
    # Sample Spanish medical text with various PHI
    test_text = """
    HOSPITAL GENERAL DE SAN MIGUEL DE ALLENDE
    HISTORIA CLÍNICA
    
    NOMBRE DEL PACIENTE: Juan Carlos Hernández García
    FECHA DE NACIMIENTO: 15/03/1945
    EDAD: 79 años
    CURP: HEGJ450315HGTRRN09
    NSS IMSS: 12345678901
    NHC: HC-2025-001234
    
    DIRECCIÓN: Calle Hidalgo #123, Col. Centro, C.P. 37700, San Miguel de Allende, Gto.
    TELÉFONO: 415-123-4567
    CELULAR: +52 415 987 6543
    EMAIL: paciente.juan@ejemplo.com
    
    PÓLIZA DE SEGURO: POL-123456789
    NÚMERO DE AFILIACIÓN: AF-987654
    
    MÉDICO TRATANTE: Dra. María López Martínez
    CÉDULA PROFESIONAL: 12345678
    
    FECHA DE INGRESO: 12/03/2025
    FECHA DE EGRESO: 15/03/2025
    
    DIAGNÓSTICO: Neumonía bacteriana
    
    MEDICAMENTOS:
    - PARACETAMOL 500mg cada 8 horas
    - CLEXANE 60mg cada 24 horas
    """
    
    print("="*70)
    print("Testing Spanish Medical PHI Detection")
    print("="*70)
    
    detector = SpanishMedicalPHIDetector()
    
    # Detect PHI
    phi_found = detector.detect_phi(test_text)
    
    print("\n📋 PHI Detection Results:")
    print("-"*50)
    for phi_type, matches in phi_found.items():
        print(f"\n{phi_type}:")
        for value, start, end in matches[:3]:  # Show first 3 of each type
            print(f"  • {value}")
    
    # Test sanitization
    print("\n🔒 Testing Sanitization:")
    print("-"*50)
    sanitized, phi_map = detector.sanitize_text(test_text)
    
    # Show a sample of sanitized text
    sample_start = test_text.index("NOMBRE DEL PACIENTE")
    sample_end = test_text.index("EMAIL:") + 50
    print("Original:")
    print(test_text[sample_start:sample_end])
    print("\nSanitized:")
    print(sanitized[sample_start:sample_end])
    
    # Test restoration
    print("\n🔓 Testing Restoration:")
    print("-"*50)
    restored = detector.restore_phi(sanitized, phi_map)
    
    # Validate
    is_valid = detector.validate_sanitization(test_text, sanitized, restored)
    
    if is_valid:
        print("✅ Sanitization and restoration successful!")
    else:
        print("❌ Validation failed!")
    
    # Show audit log
    print("\n📝 Audit Log:")
    print("-"*50)
    for entry in detector.get_audit_log():
        print(f"  Timestamp: {entry['timestamp']}")
        print(f"  PHI types found: {', '.join(entry['phi_types_found'])}")
        print(f"  Total PHI items: {entry['phi_count']}")
    
    return detector

if __name__ == "__main__":
    test_spanish_phi_detection()