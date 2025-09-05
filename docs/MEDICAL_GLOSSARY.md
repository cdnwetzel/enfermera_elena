# Medical Glossary & Terminology Framework
## Enfermera Elena - Spanish-English Medical Translation Reference

### Version 1.0 | Date: 2025-09-05

---

## Overview

This document defines the medical terminology mapping framework for accurate Mexican Spanish-to-English translation of healthcare documents from Mexican institutions (IMSS, ISSSTE, Seguro Popular). It focuses on Mexican pharmaceutical names, IMSS-specific terminology, and Mexican folk medicine concepts.

## Core Medical Terminology Categories

### 1. Anatomical Terms (Términos Anatómicos)

#### Common Anatomical Terms
| Spanish | English | ICD-10 Region | Notes |
|---------|---------|---------------|--------|
| corazón | heart | I00-I99 | |
| hígado | liver | K70-K77 | |
| riñón | kidney | N00-N29 | |
| pulmón/pulmones | lung/lungs | J00-J99 | |
| cerebro | brain | G00-G99 | |
| estómago | stomach | K20-K31 | |
| páncreas | pancreas | K85-K87 | |
| bazo | spleen | D73 | |
| vesícula biliar | gallbladder | K80-K87 | |
| vejiga | bladder | N30-N39 | |

#### Mexican-Specific Anatomical Terms
| Mexican Term | Standard Spanish | English | IMSS Usage |
|-------------|-----------------|---------|------------|
| panza | abdomen | belly/abdomen | Common |
| empeine | dorso del pie | instep | Regional |
| mollera | fontanela | fontanelle | Pediatric |
| espinazo | columna vertebral | spine | Folk usage |

### 2. Medical Conditions (Condiciones Médicas)

#### Chronic Conditions
| Spanish | English | ICD-10 | Severity Flag |
|---------|---------|--------|---------------|
| diabetes mellitus | diabetes mellitus | E10-E14 | HIGH |
| hipertensión arterial | hypertension | I10-I16 | HIGH |
| asma | asthma | J45 | MEDIUM |
| insuficiencia cardíaca | heart failure | I50 | CRITICAL |
| enfermedad renal crónica | chronic kidney disease | N18 | HIGH |
| cáncer | cancer | C00-C97 | CRITICAL |
| epilepsia | epilepsy | G40 | HIGH |
| cirrosis hepática | liver cirrhosis | K74 | HIGH |

#### Acute Conditions
| Spanish | English | ICD-10 | Emergency |
|---------|---------|--------|-----------|
| infarto agudo de miocardio | acute myocardial infarction | I21 | YES |
| accidente cerebrovascular | stroke | I60-I69 | YES |
| apendicitis aguda | acute appendicitis | K35 | YES |
| neumonía | pneumonia | J12-J18 | POSSIBLE |
| fractura | fracture | S00-T88 | POSSIBLE |

### 3. Medications (Medicamentos)

#### Mexican Brand Names → US Generic Mapping
| Mexican Brand | Generic Name | US Equivalent | IMSS Formulary |
|--------------|--------------|---------------|----------------|
| Tempra | paracetamol | acetaminophen/Tylenol | Yes |
| Motrin | ibuprofeno | ibuprofen | Yes |
| Amoxil | amoxicilina | amoxicillin | Yes |
| Glucophage | metformina | metformin | Yes |
| Coumadin | warfarina | warfarin | Yes |
| Lantus | insulina glargina | insulin glargine | Yes |
| Losec | omeprazol | omeprazole/Prilosec | Yes |
| Lipitor | atorvastatina | atorvastatin | Yes |
| Eutirox | levotiroxina | levothyroxine/Synthroid | Yes |
| Winadeine | paracetamol/codeína | acetaminophen/codeine | Yes |
| Voltaren | diclofenaco | diclofenac | Yes |
| Buscapina | butilhioscina | hyoscine butylbromide | Yes |

#### Dosage Terms
| Spanish | English | Example |
|---------|---------|---------|
| miligramos (mg) | milligrams (mg) | 500 mg |
| gramos (g) | grams (g) | 1 g |
| mililitros (ml) | milliliters (mL) | 5 mL |
| gotas | drops | 10 drops |
| comprimidos | tablets | 2 tablets |
| cápsulas | capsules | 1 capsule |
| cada X horas | every X hours | every 8 hours |
| dos veces al día | twice daily | BID |
| tres veces al día | three times daily | TID |

### 4. Medical Procedures (Procedimientos Médicos)

#### Diagnostic Procedures
| Spanish | English | CPT Category |
|---------|---------|-------------|
| radiografía | X-ray | 70000-79999 |
| tomografía computarizada | CT scan | 70450-70498 |
| resonancia magnética | MRI | 70551-70559 |
| electrocardiograma | electrocardiogram (ECG/EKG) | 93000-93010 |
| análisis de sangre | blood test | 80047-80076 |
| ultrasonido/ecografía | ultrasound | 76700-76999 |
| endoscopia | endoscopy | 43200-43273 |
| colonoscopia | colonoscopy | 45378-45398 |

#### Surgical Procedures
| Spanish | English | Urgency |
|---------|---------|---------|
| apendicectomía | appendectomy | Often urgent |
| colecistectomía | cholecystectomy | Variable |
| cesárea | cesarean section | Variable |
| bypass coronario | coronary bypass | Scheduled |
| transplante | transplant | Critical |
| amputación | amputation | Variable |

### 5. Laboratory Values (Valores de Laboratorio)

#### Blood Tests
| Spanish | English | Normal Range | Units |
|---------|---------|--------------|-------|
| glucosa en sangre | blood glucose | 70-100 | mg/dL |
| hemoglobina | hemoglobin | 12-16 (F), 14-18 (M) | g/dL |
| leucocitos | white blood cells | 4,500-11,000 | cells/μL |
| plaquetas | platelets | 150,000-450,000 | /μL |
| creatinina | creatinine | 0.6-1.2 | mg/dL |
| colesterol total | total cholesterol | <200 | mg/dL |
| presión arterial | blood pressure | 120/80 | mmHg |

#### Critical Values (Must Flag)
| Test | Critical Low | Critical High | Spanish Term |
|------|-------------|---------------|--------------|
| Glucose | <50 mg/dL | >400 mg/dL | glucosa |
| Potassium | <2.5 mEq/L | >6.5 mEq/L | potasio |
| Sodium | <120 mEq/L | >160 mEq/L | sodio |
| Hemoglobin | <7 g/dL | >20 g/dL | hemoglobina |
| Platelet | <20,000/μL | >1,000,000/μL | plaquetas |

## Medical Abbreviations

### Common Spanish Medical Abbreviations
| Spanish Abbr. | Full Spanish | English Equiv. | Full English |
|--------------|--------------|----------------|--------------|
| TA | tensión arterial | BP | blood pressure |
| FC | frecuencia cardíaca | HR | heart rate |
| FR | frecuencia respiratoria | RR | respiratory rate |
| T° | temperatura | Temp | temperature |
| PA | presión arterial | BP | blood pressure |
| IAM | infarto agudo de miocardio | AMI | acute myocardial infarction |
| ACV | accidente cerebrovascular | CVA/Stroke | cerebrovascular accident |
| DM | diabetes mellitus | DM | diabetes mellitus |
| HTA | hipertensión arterial | HTN | hypertension |
| EPOC | enfermedad pulmonar obstructiva crónica | COPD | chronic obstructive pulmonary disease |
| UCI | unidad de cuidados intensivos | ICU | intensive care unit |
| IV | intravenoso | IV | intravenous |
| IM | intramuscular | IM | intramuscular |
| VO | vía oral | PO | per os (by mouth) |

### Prescription Abbreviations
| Latin/Spanish | English | Meaning | Frequency |
|--------------|---------|---------|-----------|
| c/8h | q8h | every 8 hours | Common |
| c/12h | q12h | every 12 hours | Common |
| SOS | PRN | as needed | Common |
| ayunas | NPO | nothing by mouth | Common |
| antes de comer | AC | before meals | Common |
| después de comer | PC | after meals | Common |

## Mexican Medical Terminology

### Mexican Folk Medicine Terms
| Mexican Term | Description | Clinical Correlation | IMSS Recognition |
|-------------|------------|---------------------|-----------------|
| Empacho | Blocked digestion from food | Gastritis, constipation | Documented |
| Susto | Fright illness/soul loss | Anxiety, PTSD | Documented |
| Mal de ojo | Evil eye syndrome | Fever, irritability in children | Acknowledged |
| Caída de mollera | Sunken fontanelle | Dehydration in infants | Medical emergency |
| Aire | Bad air entering body | Muscle pain, paralysis | Folk belief |
| Bilis | Bile/anger illness | Gastric upset | Folk belief |
| Latido | Pulsing in stomach | Hunger, gastritis | Regional |

### IMSS-Specific Terminology
| IMSS Term | English Translation | US Equivalent |
|-----------|-------------------|---------------|
| Derechohabiente | Beneficiary | Insured patient |
| Consulta externa | Outpatient consultation | Outpatient visit |
| Urgencias calificadas | Qualified emergency | True emergency |
| Incapacidad | Disability certificate | Sick leave |
| Carnet de citas | Appointment booklet | Appointment card |
| Pase de especialidad | Specialty referral | Referral authorization |
| Cuadro básico | Basic formulary | Formulary list |

### Mexican Healthcare Institutions
| Spanish Acronym | Full Name | English Translation |
|----------------|-----------|-------------------|
| IMSS | Instituto Mexicano del Seguro Social | Mexican Social Security Institute |
| ISSSTE | Instituto de Seguridad y Servicios Sociales | State Workers' Security Institute |
| COFEPRIS | Comisión Federal para la Protección contra Riesgos Sanitarios | Federal Commission for Protection against Health Risks |
| SSA | Secretaría de Salud | Ministry of Health |
| CONAMED | Comisión Nacional de Arbitraje Médico | National Medical Arbitration Commission |

## Critical Safety Terms

### Must Never Mistranslate
| Spanish | English | Risk if Mistranslated |
|---------|---------|---------------------|
| alergia/alérgico | allergy/allergic | Anaphylaxis risk |
| embarazada | pregnant | Medication contraindications |
| dosis | dose/dosage | Overdose/underdose |
| una vez/dos veces | once/twice | Medication errors |
| miligramos/gramos | milligrams/grams | 1000x dosage error |
| derecho/izquierdo | right/left | Wrong site surgery |
| sí/no | yes/no | Consent issues |

### Emergency Phrases
| Spanish | English | Context |
|---------|---------|---------|
| ¡Emergencia! | Emergency! | Immediate attention |
| No puedo respirar | I can't breathe | Respiratory emergency |
| Dolor en el pecho | Chest pain | Cardiac emergency |
| Alérgico a... | Allergic to... | Allergy alert |
| Estoy sangrando | I'm bleeding | Hemorrhage |
| Me voy a desmayar | I'm going to faint | Syncope warning |

## Validation Rules

### High-Risk Term Validation
```python
HIGH_RISK_TERMS = {
    'medications': {
        'warfarin': {'verify_dosage': True, 'max_dose_mg': 10},
        'insulin': {'verify_units': True, 'verify_type': True},
        'digoxin': {'verify_dosage': True, 'max_dose_mg': 0.25},
        'morphine': {'verify_route': True, 'controlled': True}
    },
    'allergies': {
        'penicillin': {'severity_check': True},
        'latex': {'equipment_alert': True},
        'contrast': {'imaging_alert': True}
    },
    'conditions': {
        'pregnant': {'medication_check': True},
        'dialysis': {'renal_dosing': True},
        'immunocompromised': {'special_precautions': True}
    }
}
```

### Dosage Validation Patterns
```python
DOSAGE_PATTERNS = {
    'spanish': r'(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|unidades?)',
    'english': r'(\d+(?:\.\d+)?)\s*(mg|g|mL|mcg|units?)',
    'frequency_spanish': r'cada\s+(\d+)\s+horas?|(\d+)\s+veces?\s+al\s+día',
    'frequency_english': r'every\s+(\d+)\s+hours?|(\d+)\s+times?\s+(?:a|per)\s+day'
}
```

## Quality Assurance Checklist

### Pre-Translation Checks
- [ ] Identify document type (prescription, lab, clinical note)
- [ ] Detect regional dialect markers
- [ ] Flag high-risk medications
- [ ] Identify critical values
- [ ] Check for abbreviations

### Translation Validation
- [ ] Medication names correctly translated
- [ ] Dosages preserved exactly
- [ ] Units converted appropriately
- [ ] Anatomical terms accurate
- [ ] Temporal relationships maintained

### Post-Translation Review
- [ ] Critical terms highlighted for review
- [ ] Confidence scores assessed
- [ ] Cultural concepts explained
- [ ] Allergies prominently displayed
- [ ] Emergency information prioritized

## Glossary Maintenance

### Update Frequency
- Core medical terms: Quarterly
- Medication database: Monthly
- Regional variations: As discovered
- Abbreviations: Bi-annually
- Critical safety terms: Immediate

### Sources for Updates
1. **Medical Databases**
   - UMLS (Unified Medical Language System)
   - WHO ICD-10/11
   - RxNorm
   - SNOMED CT

2. **Professional Organizations**
   - Real Academia Nacional de Medicina (Spain)
   - Academia Nacional de Medicina (Mexico)
   - Pan American Health Organization

3. **Clinical Feedback**
   - User-reported corrections
   - Medical expert reviews
   - Hospital terminology committees

### Version Control
```yaml
Glossary Version: 1.0.0
Last Updated: 2025-09-05
Review Cycle: Quarterly
Approval Required: Medical Director
Change Log: /docs/glossary_changelog.md
```

## API Integration

### Terminology Lookup Endpoint
```python
@app.get("/api/v1/terminology/lookup")
async def lookup_term(
    term: str,
    source_language: str = "es",
    target_language: str = "en",
    include_alternates: bool = True,
    regional_variant: Optional[str] = None
):
    """
    Look up medical term translation
    
    Returns:
    {
        "source_term": "hipertensión",
        "primary_translation": "hypertension",
        "alternates": ["high blood pressure"],
        "icd10_code": "I10",
        "category": "condition",
        "severity": "high",
        "regional_notes": {},
        "confidence": 0.99
    }
    """
```

### Batch Terminology Validation
```python
@app.post("/api/v1/terminology/validate")
async def validate_terms(
    document_id: str,
    terms: List[MedicalTerm]
):
    """
    Validate medical terms in translated document
    
    Returns flagged terms requiring review
    """
```

## Training Data Structure

### Parallel Corpus Format
```json
{
    "pair_id": "med_001234",
    "source": {
        "language": "es",
        "text": "Paciente con diabetes mellitus tipo 2",
        "regional_variant": "mexico"
    },
    "target": {
        "language": "en",
        "text": "Patient with type 2 diabetes mellitus"
    },
    "metadata": {
        "document_type": "clinical_note",
        "specialty": "endocrinology",
        "validated_by": "MD_reviewer_id",
        "confidence": 1.0
    }
}
```

---

*Document Status: Initial framework established*  
*Medical Review: Pending*  
*Next Update: After medical expert consultation*