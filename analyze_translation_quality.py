#!/usr/bin/env python3
"""
Analyze OpenAI translation quality for medical records
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

def analyze_translation(original_file: str, translated_file: str):
    """Analyze translation quality"""
    
    print("=" * 70)
    print("Medical Translation Quality Analysis")
    print("=" * 70)
    
    # Read files
    with open(original_file, 'r', encoding='utf-8') as f:
        original = f.read()
    
    with open(translated_file, 'r', encoding='utf-8') as f:
        translated = f.read()
    
    # Key medical terms to verify
    medical_terms = {
        'DETALLADO DE CARGOS': 'DETAILED.*CHARGES',
        'HOSPITALIZACIÓN': 'HOSPITALIZATION',
        'IMAGENOLOGÍA': 'IMAGING',
        'LABORATORIO': 'LABORATORY',
        'MEDICAMENTOS': 'MEDICATIONS|MEDICATION',
        'BIOMETRIA HEMATICA': 'COMPLETE BLOOD COUNT|BLOOD COUNT',
        'TOMOGRAFIA': 'CT SCAN|TOMOGRAPHY',
        'RAYOS X': 'X-RAY',
        'TERAPIA INHALATORIA': 'INHALATION THERAPY',
        'ADMINISTRACION DE MEDICAMENTOS': 'MEDICATION ADMINISTRATION',
        'VIA INHALADA': 'INHALED ROUTE|INHALATION',
        'GLUCOMETRIA': 'GLUCOMETER|GLUCOSE',
        'DIETA DEL PACIENTE': 'PATIENT DIET',
        'HONORARIOS': 'FEES|PROFESSIONAL FEES',
        'CIRUGIA': 'SURGERY|SURGICAL',
        'ANESTESIA': 'ANESTHESIA',
        'URGENCIAS': 'EMERGENCY',
        'TIEMPO DE COAGULACION': 'COAGULATION TIME',
        'REACCIONES FEBRILES': 'FEBRILE REACTIONS',
        'EXAMEN GENERAL DE ORINA': 'GENERAL URINE TEST|URINALYSIS',
        'ELECTROLITOS': 'ELECTROLYTES',
        'QUÍMICA SANGUÍNEA': 'BLOOD CHEMISTRY|METABOLIC PANEL',
        'TROPONINA': 'TROPONIN',
        'DÍMERO D': 'D-DIMER'
    }
    
    # Drug names to verify
    drugs = {
        'CLEXANE': 'CLEXANE|ENOXAPARIN',
        'PARACETAMOL': 'PARACETAMOL|ACETAMINOPHEN',
        'METAMIZOL': 'METAMIZOL|DIPYRONE',
        'OMEPRAZOL': 'OMEPRAZOLE',
        'BUTILHIOSCINA': 'BUTYLSCOPOLAMINE|HYOSCINE',
        'ONDANSETRON': 'ONDANSETRON',
        'KETOROLACO': 'KETOROLAC',
        'FUROSEMIDA': 'FUROSEMIDE',
        'MIDAZOLAM': 'MIDAZOLAM',
        'PROPOFOL': 'PROPOFOL',
        'FENTANILO': 'FENTANYL',
        'LIDOCAINA': 'LIDOCAINE'
    }
    
    # Check translation of key terms
    print("\n📊 Medical Term Translation Analysis:")
    print("-" * 50)
    
    correct = 0
    total = 0
    
    for spanish, english_pattern in medical_terms.items():
        if spanish.lower() in original.lower():
            total += 1
            if re.search(english_pattern, translated, re.IGNORECASE):
                correct += 1
                print(f"✓ {spanish} → Found correct translation")
            else:
                print(f"✗ {spanish} → Translation not found or incorrect")
    
    print(f"\nMedical terms accuracy: {correct}/{total} ({100*correct/total:.1f}%)")
    
    # Check drug name translations
    print("\n💊 Drug Name Translation Analysis:")
    print("-" * 50)
    
    drug_correct = 0
    drug_total = 0
    
    for spanish, english_pattern in drugs.items():
        if spanish.upper() in original.upper():
            drug_total += 1
            if re.search(english_pattern, translated, re.IGNORECASE):
                drug_correct += 1
                print(f"✓ {spanish} → Found correct translation")
            else:
                print(f"✗ {spanish} → Translation not found")
    
    if drug_total > 0:
        print(f"\nDrug names accuracy: {drug_correct}/{drug_total} ({100*drug_correct/drug_total:.1f}%)")
    
    # Check numerical preservation
    print("\n🔢 Numerical Data Preservation:")
    print("-" * 50)
    
    # Extract all prices from original
    prices_original = re.findall(r'\$[\d,]+\.?\d*', original)
    prices_translated = re.findall(r'\$[\d,]+\.?\d*', translated)
    
    print(f"Prices in original: {len(prices_original)}")
    print(f"Prices in translation: {len(prices_translated)}")
    
    # Check dates
    dates_original = re.findall(r'\d{2}/\d{2}/\d{4}', original)
    dates_translated = re.findall(r'\d{2}/\d{2}/\d{4}', translated)
    
    print(f"Dates in original: {len(dates_original)}")
    print(f"Dates in translation: {len(dates_translated)}")
    
    # Check quantities
    quantities_original = re.findall(r'\s+\d+\s+(?:PZA|AMP|TAB|CAP|ML|MG|SERV)', original)
    quantities_translated = re.findall(r'\s+\d+\s+(?:UNITS?|AMP|TAB|CAP|ML|MG|SERV|EA)', translated, re.IGNORECASE)
    
    print(f"Quantities in original: {len(quantities_original)}")
    print(f"Quantities in translation: {len(quantities_translated)}")
    
    # Structure preservation
    print("\n📋 Document Structure:")
    print("-" * 50)
    
    original_lines = original.split('\n')
    translated_lines = translated.split('\n')
    
    print(f"Original lines: {len(original_lines)}")
    print(f"Translated lines: {len(translated_lines)}")
    
    # Check section headers
    sections = ['IMAGENOLOGÍA', 'LABORATORIO', 'HOSPITALIZACIÓN', 'MEDICAMENTOS', 'HONORARIOS']
    sections_found = 0
    for section in sections:
        if section in original.upper():
            english = section.replace('IMAGENOLOGÍA', 'IMAGING').replace('LABORATORIO', 'LABORATORY')
            english = english.replace('HOSPITALIZACIÓN', 'HOSPITALIZATION').replace('MEDICAMENTOS', 'MEDICATIONS')
            english = english.replace('HONORARIOS', 'FEES')
            if english in translated.upper():
                sections_found += 1
    
    print(f"Section headers preserved: {sections_found}/{len([s for s in sections if s in original.upper()])}")
    
    # Overall assessment
    print("\n=" * 70)
    print("OVERALL QUALITY ASSESSMENT")
    print("=" * 70)
    
    total_checks = total + drug_total
    total_correct = correct + drug_correct
    
    if total_checks > 0:
        accuracy = 100 * total_correct / total_checks
        print(f"\n✅ Translation Accuracy: {accuracy:.1f}%")
        
        if accuracy >= 90:
            print("🎯 TARGET ACHIEVED: 90%+ accuracy for medical/insurance use")
        elif accuracy >= 80:
            print("⚠️ Good quality but below 90% target")
        else:
            print("❌ Quality below acceptable threshold for medical use")
    
    # Sample comparison
    print("\n📝 Sample Translation Comparison:")
    print("-" * 70)
    
    # Find a representative section
    if 'BIOMETRIA HEMATICA' in original:
        # Find the line with this term
        for i, line in enumerate(original_lines):
            if 'BIOMETRIA HEMATICA' in line:
                print(f"Original:  {line.strip()}")
                if i < len(translated_lines):
                    for j in range(max(0, i-2), min(len(translated_lines), i+3)):
                        if 'BLOOD COUNT' in translated_lines[j].upper():
                            print(f"Translated: {translated_lines[j].strip()}")
                            break
                break
    
    return accuracy if total_checks > 0 else 0

if __name__ == "__main__":
    original = "medical_records/extracted/mr_12_03_25_MACSMA_redacted_extracted.txt"
    translated = "medical_records/translated/mr_12_03_25_MACSMA_redacted_translated.txt"
    
    if Path(original).exists() and Path(translated).exists():
        accuracy = analyze_translation(original, translated)
    else:
        print("Files not found!")