#!/usr/bin/env python3
"""
Medical Record Translator for Enfermera Elena
Translates the hospital billing and medical record
"""

import csv
import re
import os
from pathlib import Path
from typing import Dict


def load_glossary(path: str = "data/glossaries/glossary_comprehensive.csv") -> Dict[str, str]:
    """Load enhanced UMLS glossary"""
    glossary = {}
    
    # Try comprehensive glossary first, fall back to production if not found
    if not Path(path).exists():
        path = "data/glossaries/glossary_es_en_production.csv"
        print(f"Using fallback glossary: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            es_term = row['es_term'].lower()
            en_term = row['en_term']
            glossary[es_term] = en_term
            
    print(f"Loaded {len(glossary)} medical terms")
    return glossary


def translate_medical_document(text: str, glossary: Dict[str, str]) -> str:
    """Translate medical document text"""
    
    # Key translations for this document
    translations = {
        # Document headers
        'detallado de cargos de hospitalización': 'Detailed Hospitalization Charges',
        'cargos de hospitalizacion por sección': 'Hospitalization Charges by Section',
        'centro hospitalario': 'Hospital Center',
        
        # Column headers
        'fecha': 'Date',
        'descripción': 'Description',
        'cant.': 'Qty.',
        'uni.': 'Unit',
        'p.unitario': 'Unit Price',
        'importe': 'Amount',
        'descto.': 'Discount',
        'subtotal': 'Subtotal',
        'iva': 'VAT',
        'neto': 'Net',
        
        # Medical departments
        'imagenologia': 'IMAGING',
        'inhaloterapia': 'RESPIRATORY THERAPY',
        'laboratorio': 'LABORATORY',
        'farmacia': 'PHARMACY',
        'urgencias': 'EMERGENCY',
        'hospitalizacion': 'HOSPITALIZATION',
        'cuidados intensivos': 'INTENSIVE CARE',
        'cirugia': 'SURGERY',
        'anestesia': 'ANESTHESIA',
        'enfermeria': 'NURSING',
        
        # Medical procedures
        'tomografia torax simple': 'Simple Chest CT Scan',
        'tomografia': 'CT Scan',
        'radiografia portatil': 'Portable X-Ray',
        'radiografia': 'X-Ray',
        'interpretacion de estudios': 'Study Interpretation',
        'servicio imagenologia de urgencia': 'Emergency Imaging Service',
        'administracion de medicamentos': 'Medication Administration',
        'por via inhalada': 'via Inhalation',
        'por sesion': 'per Session',
        
        # Lab tests
        'biometria hematica completa': 'Complete Blood Count',
        'quimica sanguinea': 'Blood Chemistry',
        'electrolitos sericos': 'Serum Electrolytes',
        'pruebas de funcion hepatica': 'Liver Function Tests',
        'pruebas de funcion renal': 'Kidney Function Tests',
        'gasometria arterial': 'Arterial Blood Gas',
        'cultivo': 'Culture',
        'antibiograma': 'Antibiogram',
        'glucosa': 'Glucose',
        'creatinina': 'Creatinine',
        'urea': 'Urea',
        'sodio': 'Sodium',
        'potasio': 'Potassium',
        'cloro': 'Chloride',
        
        # Medications
        'antibiotico': 'Antibiotic',
        'analgesico': 'Analgesic',
        'antipiretico': 'Antipyretic',
        'solucion': 'Solution',
        'tableta': 'Tablet',
        'ampula': 'Ampule',
        'frasco': 'Vial',
        
        # Common terms
        'servicio': 'Service',
        'materiales': 'Materials',
        'desechables': 'Disposables',
        'consumibles': 'Consumables',
        'incluye': 'Includes',
        'no incluye': 'Does Not Include',
        'proyeccion': 'Projection',
        'simple': 'Simple',
        'completo': 'Complete',
        'parcial': 'Partial',
        'total': 'Total',
        
        # Units
        'serv.': 'SERV.',
        'pza': 'PC',
        'es': 'EA',
        'ml': 'ML',
        'mg': 'MG',
        'gr': 'G',
        'tab': 'TAB',
        'amp': 'AMP',
        
        # Financial terms
        'cargo': 'Charge',
        'cargos': 'Charges',
        'honorarios': 'Professional Fees',
        'material': 'Material',
        'medicamento': 'Medication',
        'procedimiento': 'Procedure',
        'estudio': 'Study',
        'consulta': 'Consultation',
        'urgencia': 'Emergency',
        
        # Dates/Times
        'hora': 'Hour',
        'dia': 'Day',
        'turno': 'Shift',
        'matutino': 'Morning',
        'vespertino': 'Evening',
        'nocturno': 'Night',
    }
    
    # Translate line by line
    lines = text.split('\n')
    translated_lines = []
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            translated_lines.append(line)
            continue
            
        # Preserve formatting (spaces, alignment)
        translated = line
        
        # Apply translations (case-insensitive)
        for spanish, english in translations.items():
            # Use word boundaries for better matching
            pattern = re.compile(re.escape(spanish), re.IGNORECASE)
            translated = pattern.sub(english, translated)
            
        # Translate using glossary for medical terms
        line_lower = translated.lower()
        for es_term, en_term in glossary.items():
            if es_term in line_lower and len(es_term) > 3:  # Skip very short terms
                pattern = re.compile(r'\b' + re.escape(es_term) + r'\b', re.IGNORECASE)
                if pattern.search(translated):
                    translated = pattern.sub(en_term, translated)
                    break  # One replacement per line to avoid over-translation
                    
        # Basic word translations for remaining Spanish
        basic_words = {
            ' de ': ' of ',
            ' del ': ' of the ',
            ' la ': ' the ',
            ' el ': ' the ',
            ' los ': ' the ',
            ' las ': ' the ',
            ' por ': ' by ',
            ' para ': ' for ',
            ' con ': ' with ',
            ' sin ': ' without ',
            ' y ': ' and ',
            ' o ': ' or ',
            ' ni ': ' nor ',
            ' no ': ' not ',
        }
        
        for sp, en in basic_words.items():
            translated = translated.replace(sp, en)
            
        translated_lines.append(translated)
        
    return '\n'.join(translated_lines)


def main():
    """Main translation function"""
    
    print("=" * 70)
    print("Enfermera Elena - Medical Record Translation")
    print("Translating Hospital Billing Document")
    print("=" * 70)
    
    # Load glossary
    print("\n📚 Loading UMLS glossary...")
    glossary = load_glossary()
    
    # Read extracted text
    input_file = "medical_records/extracted/mr_12_03_25_MACSMA_extracted.txt"
    print(f"\n📄 Reading: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        original_text = f.read()
        
    print(f"   Found {len(original_text)} characters, {len(original_text.split())} words")
    
    # Translate
    print("\n🔄 Translating document...")
    translated = translate_medical_document(original_text, glossary)
    
    # Save translation
    output_file = "medical_records/translated/mr_12_03_25_MACSMA_translated.txt"
    Path("medical_records/translated").mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(translated)
        
    print(f"\n✅ Translation saved to: {output_file}")
    
    # Show sample
    print("\n📝 Sample of translation:")
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
    
    print("\n✅ Translation complete!")
    print(f"\nView the full translation: cat {output_file}")


if __name__ == "__main__":
    main()