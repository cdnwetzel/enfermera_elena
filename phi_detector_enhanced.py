#!/usr/bin/env python3
"""
Enhanced HIPAA-Compliant PHI Detection for Spanish Medical Records
Fixes overlapping patterns and improves accuracy
"""

import re
from typing import Dict, List, Tuple, Set, Optional
from datetime import datetime
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class PHIType(Enum):
    """HIPAA PHI identifier types"""
    NAME = "name"
    DATE = "date"
    PHONE = "phone"
    FAX = "fax"
    EMAIL = "email"
    SSN = "ssn"
    MRN = "medical_record_number"
    HEALTH_PLAN = "health_plan_number"
    ACCOUNT = "account_number"
    LICENSE = "license_number"
    VEHICLE = "vehicle_identifier"
    DEVICE = "device_identifier"
    URL = "web_url"
    IP = "ip_address"
    BIOMETRIC = "biometric_identifier"
    PHOTO = "photo_image"
    GEOGRAPHIC = "geographic_location"
    AGE_OVER_89 = "age_over_89"
    # Mexican specific
    CURP = "curp"
    RFC = "rfc"
    NSS = "nss_imss"
    INE = "ine_ife"

@dataclass
class PHIMatch:
    """Represents a PHI match in text"""
    phi_type: PHIType
    value: str
    start: int
    end: int
    confidence: float
    context: str = ""

class SpanishMedicalPHIDetector:
    """
    Enhanced PHI detector that handles overlapping patterns
    and Spanish medical document specifics
    """
    
    def __init__(self):
        self.patterns = self._build_priority_patterns()
        self.audit_log = []
        
    def _build_priority_patterns(self) -> List[Tuple[PHIType, re.Pattern, float]]:
        """
        Build patterns with priority ordering to handle overlaps
        Returns: List of (PHIType, pattern, confidence_score)
        """
        patterns = []
        
        # HIGH PRIORITY - Most specific patterns first
        
        # CURP (very specific format - 18 chars)
        patterns.append((
            PHIType.CURP,
            re.compile(r'\bCURP[:\s]*([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b', re.IGNORECASE),
            1.0
        ))
        
        # RFC (Mexican tax ID - specific format)
        patterns.append((
            PHIType.RFC,
            re.compile(r'\bRFC[:\s]*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})\b', re.IGNORECASE),
            1.0
        ))
        
        # NSS/IMSS (11 digits after keyword)
        patterns.append((
            PHIType.NSS,
            re.compile(r'\b(?:NSS|IMSS|SEGURO\s+SOCIAL)[:\s#]*(\d{11})\b', re.IGNORECASE),
            0.95
        ))
        
        # Medical Record Number (with keywords)
        patterns.append((
            PHIType.MRN,
            re.compile(
                r'\b(?:NHC|HC|HISTORIA\s+CLÍNICA|EXPEDIENTE|'
                r'FOLIO\s+MÉDICO|FICHA\s+MÉDICA)'
                r'[:\s#\-]*([A-Z0-9]{2,}[\-]?[A-Z0-9]+)\b',
                re.IGNORECASE
            ),
            0.9
        ))
        
        # Health Insurance Policy
        patterns.append((
            PHIType.HEALTH_PLAN,
            re.compile(
                r'\b(?:PÓLIZA|POLIZA|AFILIACIÓN|AFILIACION|'
                r'CERTIFICADO\s+DE\s+SEGURO|CONTRATO\s+DE\s+SEGURO)'
                r'[:\s#\-]*([A-Z0-9\-]{5,})\b',
                re.IGNORECASE
            ),
            0.85
        ))
        
        # Names with context (after keywords)
        patterns.append((
            PHIType.NAME,
            re.compile(
                r'\b(?:PACIENTE|NOMBRE\s+DEL?\s+PACIENTE|TITULAR|'
                r'BENEFICIARIO|ASEGURADO|NOMBRE\s+COMPLETO)'
                r'[:\s]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,4})\b'
            ),
            0.95
        ))
        
        # Doctor names
        patterns.append((
            PHIType.NAME,
            re.compile(
                r'\b(?:DR\.?|DRA\.?|MÉDICO|DOCTOR|DOCTORA|'
                r'MÉDICO\s+TRATANTE|ATENDIÓ)'
                r'[:\s]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\b'
            ),
            0.9
        ))
        
        # Mexican phone formats
        patterns.append((
            PHIType.PHONE,
            re.compile(
                r'\b(?:TEL\.?|TELÉFONO|CEL\.?|CELULAR|MÓVIL|CONTACTO)'
                r'[:\s]*(?:\+52\s*)?'
                r'(\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4})\b',
                re.IGNORECASE
            ),
            0.95
        ))
        
        # Email addresses
        patterns.append((
            PHIType.EMAIL,
            re.compile(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'),
            1.0
        ))
        
        # Mexican dates (DD/MM/YYYY or DD-MM-YYYY)
        patterns.append((
            PHIType.DATE,
            re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-](?:\d{4}|\d{2}))\b'),
            0.8
        ))
        
        # Written dates in Spanish
        patterns.append((
            PHIType.DATE,
            re.compile(
                r'\b(\d{1,2}\s+(?:DE\s+)?'
                r'(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|'
                r'AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)'
                r'\s+(?:DE\s+)?\d{4})\b',
                re.IGNORECASE
            ),
            0.95
        ))
        
        # Mexican addresses
        patterns.append((
            PHIType.GEOGRAPHIC,
            re.compile(
                r'(?:CALLE|AV\.?|AVENIDA|BLVD\.?|BOULEVARD|'
                r'CARRETERA|CAMINO|CALZADA)\s+'
                r'([^,\n]{5,50})'  # Street name
                r'(?:.*?C\.?P\.?\s*\d{5})?',  # Optional ZIP
                re.IGNORECASE
            ),
            0.7
        ))
        
        # Mexican ZIP codes
        patterns.append((
            PHIType.GEOGRAPHIC,
            re.compile(r'\bC\.?P\.?\s*(\d{5})\b', re.IGNORECASE),
            0.9
        ))
        
        # Age over 89
        patterns.append((
            PHIType.AGE_OVER_89,
            re.compile(r'\b(?:EDAD|AÑOS)[:\s]*((?:9\d|[1-9]\d{2}))\s*(?:AÑOS)?\b', re.IGNORECASE),
            0.95
        ))
        
        # INE/IFE voter ID
        patterns.append((
            PHIType.INE,
            re.compile(r'\b(?:INE|IFE|ELECTOR|CREDENCIAL)[:\s#]*(\d{13,18})\b', re.IGNORECASE),
            0.85
        ))
        
        # Professional license (Cédula)
        patterns.append((
            PHIType.LICENSE,
            re.compile(
                r'\b(?:CÉDULA\s+PROFESIONAL|CED\.?\s+PROF\.?|'
                r'LICENCIA|MATRÍCULA)[:\s#]*(\d{5,10})\b',
                re.IGNORECASE
            ),
            0.8
        ))
        
        # URLs
        patterns.append((
            PHIType.URL,
            re.compile(r'(https?://[^\s<>"{}|\\^`\[\]]+)'),
            1.0
        ))
        
        # IP addresses
        patterns.append((
            PHIType.IP,
            re.compile(r'\b((?:\d{1,3}\.){3}\d{1,3})\b'),
            0.9
        ))
        
        return patterns
    
    def detect_phi(self, text: str) -> List[PHIMatch]:
        """
        Detect all PHI in text, handling overlaps intelligently
        Returns: List of PHIMatch objects, sorted by position
        """
        all_matches = []
        
        # Find all matches
        for phi_type, pattern, confidence in self.patterns:
            for match in pattern.finditer(text):
                value = match.group(1) if match.groups() else match.group(0)
                
                # Get context around match (20 chars before and after)
                context_start = max(0, match.start() - 20)
                context_end = min(len(text), match.end() + 20)
                context = text[context_start:context_end]
                
                all_matches.append(PHIMatch(
                    phi_type=phi_type,
                    value=value,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence,
                    context=context
                ))
        
        # Remove overlapping matches, keeping higher confidence ones
        filtered_matches = self._filter_overlaps(all_matches)
        
        # Sort by position
        filtered_matches.sort(key=lambda x: x.start)
        
        # Log detection
        self._log_detection(text, filtered_matches)
        
        return filtered_matches
    
    def _filter_overlaps(self, matches: List[PHIMatch]) -> List[PHIMatch]:
        """Remove overlapping matches, keeping higher confidence ones"""
        if not matches:
            return []
        
        # Sort by confidence (descending) then by start position
        matches.sort(key=lambda x: (-x.confidence, x.start))
        
        filtered = []
        used_positions = set()
        
        for match in matches:
            # Check if this match overlaps with any already selected
            positions = set(range(match.start, match.end))
            if not positions & used_positions:
                filtered.append(match)
                used_positions.update(positions)
        
        return filtered
    
    def sanitize_text(self, text: str) -> Tuple[str, Dict[str, PHIMatch]]:
        """
        Remove all PHI from text
        Returns: (sanitized_text, phi_map)
        """
        matches = self.detect_phi(text)
        phi_map = {}
        sanitized = text
        
        # Process in reverse order to maintain indices
        for match in reversed(matches):
            placeholder = f"[{match.phi_type.value.upper()}_{len(phi_map)}]"
            phi_map[placeholder] = match
            sanitized = sanitized[:match.start] + placeholder + sanitized[match.end:]
        
        return sanitized, phi_map
    
    def restore_phi(self, sanitized_text: str, phi_map: Dict[str, PHIMatch]) -> str:
        """Restore PHI to sanitized text"""
        restored = sanitized_text
        
        for placeholder, match in phi_map.items():
            restored = restored.replace(placeholder, match.value)
        
        return restored
    
    def _log_detection(self, text: str, matches: List[PHIMatch]):
        """Log PHI detection for audit trail"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'text_hash': hashlib.sha256(text.encode()).hexdigest()[:16],
            'phi_types_found': list(set(m.phi_type.value for m in matches)),
            'phi_count': len(matches),
            'high_confidence_count': len([m for m in matches if m.confidence >= 0.9])
        }
        self.audit_log.append(log_entry)
    
    def generate_report(self, matches: List[PHIMatch]) -> str:
        """Generate a summary report of PHI found"""
        if not matches:
            return "No PHI detected"
        
        report = []
        report.append("PHI Detection Summary")
        report.append("=" * 50)
        
        # Group by type
        by_type = {}
        for match in matches:
            if match.phi_type not in by_type:
                by_type[match.phi_type] = []
            by_type[match.phi_type].append(match)
        
        for phi_type, type_matches in by_type.items():
            report.append(f"\n{phi_type.value.replace('_', ' ').title()}:")
            for match in type_matches[:3]:  # Show max 3 examples
                masked = match.value[:3] + "*" * (len(match.value) - 3)
                report.append(f"  • {masked} (confidence: {match.confidence:.0%})")
            if len(type_matches) > 3:
                report.append(f"  ... and {len(type_matches) - 3} more")
        
        report.append(f"\nTotal PHI items: {len(matches)}")
        high_conf = len([m for m in matches if m.confidence >= 0.9])
        report.append(f"High confidence: {high_conf}/{len(matches)}")
        
        return "\n".join(report)


def test_enhanced_detector():
    """Test the enhanced PHI detector"""
    
    test_text = """
    HOSPITAL GENERAL SAN MIGUEL
    EXPEDIENTE MÉDICO
    
    PACIENTE: María González Hernández
    FECHA NAC: 15/03/1945
    EDAD: 79 años
    CURP: GOHM450315MGTRNR08
    NSS: 12345678901
    NHC: HC-2025-001234
    
    DOMICILIO: Av. Insurgentes 123, Col. Centro, C.P. 37700
    TEL: 415-123-4567
    EMAIL: maria.g@email.com
    
    PÓLIZA: POL-ABC123456
    
    DR. JUAN PÉREZ LÓPEZ
    CED. PROF. 1234567
    
    INGRESO: 12/03/2025
    """
    
    print("Testing Enhanced PHI Detector")
    print("=" * 70)
    
    detector = SpanishMedicalPHIDetector()
    
    # Detect PHI
    matches = detector.detect_phi(test_text)
    
    # Generate report
    print(detector.generate_report(matches))
    
    # Test sanitization
    print("\n" + "=" * 70)
    print("Sanitization Test:")
    sanitized, phi_map = detector.sanitize_text(test_text)
    
    # Show sample
    lines = sanitized.split('\n')
    for i, line in enumerate(lines[4:10]):  # Show lines 4-9
        print(f"  {line}")
    
    # Test restoration
    restored = detector.restore_phi(sanitized, phi_map)
    
    if restored == test_text:
        print("\n✅ Perfect restoration achieved!")
    else:
        print("\n❌ Restoration failed")
    
    return detector


if __name__ == "__main__":
    test_enhanced_detector()