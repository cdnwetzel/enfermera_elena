#!/usr/bin/env python3
"""
Seed Glossary Generator for Enfermera Elena
Creates initial medical glossary while waiting for UMLS license
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SeedGlossaryGenerator:
    """Generate seed medical glossary from multiple sources"""
    
    def __init__(self, output_path: str = "../data/glossaries/seed_glossary.csv"):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.glossary = {}
        
    def add_imss_terms(self):
        """Add IMSS/ISSSTE-specific terminology"""
        imss_terms = {
            # Administrative terms
            'derechohabiente': 'beneficiary/insured person',
            'afiliación': 'enrollment',
            'vigencia': 'coverage validity',
            'consultorio': 'consultation room',
            'unidad médica': 'medical unit',
            'delegación': 'delegation/regional office',
            'número de seguridad social': 'social security number',
            'carnet': 'insurance card',
            'pase de especialidad': 'specialty referral',
            'contrarreferencia': 'counter-referral',
            
            # Service types
            'consulta externa': 'outpatient consultation',
            'urgencias': 'emergency room',
            'urgencias calificadas': 'qualified emergencies',
            'hospitalización': 'hospitalization',
            'quirófano': 'operating room',
            'tococirugía': 'obstetrics surgery',
            'unidad de cuidados intensivos': 'intensive care unit',
            'medicina preventiva': 'preventive medicine',
            'medicina del trabajo': 'occupational medicine',
            'medicina familiar': 'family medicine',
            
            # Clinical documents
            'expediente clínico': 'clinical record',
            'historia clínica': 'medical history',
            'nota médica': 'medical note',
            'nota de evolución': 'progress note',
            'nota de ingreso': 'admission note',
            'nota de egreso': 'discharge note',
            'hoja de enfermería': 'nursing notes',
            'receta médica': 'medical prescription',
            'resumen clínico': 'clinical summary',
            'certificado médico': 'medical certificate',
            'certificado de incapacidad': 'disability certificate',
            'formato único': 'standard form',
            
            # Programs and benefits
            'cuadro básico': 'essential medicines list/formulary',
            'seguro popular': 'popular insurance (discontinued)',
            'insabi': 'INSABI (health institute)',
            'prevenimss': 'PrevenIMSS (prevention program)',
            'chequeo médico': 'medical checkup',
            'cartilla de salud': 'health card',
            
            # Personnel
            'médico familiar': 'family physician',
            'médico especialista': 'specialist physician',
            'médico tratante': 'attending physician',
            'enfermera': 'nurse',
            'trabajadora social': 'social worker',
            'camillero': 'orderly/stretcher bearer',
        }
        
        self.glossary.update(imss_terms)
        logger.info(f"Added {len(imss_terms)} IMSS/ISSSTE terms")
        
    def add_mexican_medications(self):
        """Add Mexican medication names and their US equivalents"""
        medications = {
            # Pain/Fever
            'metamizol': 'dipyrone/metamizole',
            'metamizol sódico': 'metamizole sodium',
            'neo-melubrina': 'dipyrone (brand)',
            'paracetamol': 'acetaminophen',
            'tempra': 'acetaminophen (brand)',
            'ácido acetilsalicílico': 'aspirin',
            'aspirina': 'aspirin',
            
            # NSAIDs
            'diclofenaco': 'diclofenac',
            'voltaren': 'diclofenac (brand)',
            'ketorolaco': 'ketorolac',
            'naproxeno': 'naproxen',
            'ibuprofeno': 'ibuprofen',
            'clonixinato de lisina': 'lysine clonixinate',
            'dolac': 'lysine clonixinate (brand)',
            'meloxicam': 'meloxicam',
            'piroxicam': 'piroxicam',
            'indometacina': 'indomethacin',
            
            # Antibiotics
            'amoxicilina': 'amoxicillin',
            'ampicilina': 'ampicillin',
            'penicilina': 'penicillin',
            'penicilina benzatínica': 'benzathine penicillin',
            'cefalexina': 'cephalexin',
            'ceftriaxona': 'ceftriaxone',
            'ciprofloxacino': 'ciprofloxacin',
            'levofloxacino': 'levofloxacin',
            'azitromicina': 'azithromycin',
            'claritromicina': 'clarithromycin',
            'metronidazol': 'metronidazole',
            'trimetoprim': 'trimethoprim',
            'sulfametoxazol': 'sulfamethoxazole',
            'nitrofurantoína': 'nitrofurantoin',
            
            # Cardiovascular
            'captopril': 'captopril',
            'enalapril': 'enalapril',
            'losartán': 'losartan',
            'telmisartán': 'telmisartan',
            'amlodipino': 'amlodipine',
            'nifedipino': 'nifedipine',
            'metoprolol': 'metoprolol',
            'propranolol': 'propranolol',
            'atenolol': 'atenolol',
            'hidroclorotiazida': 'hydrochlorothiazide',
            'furosemida': 'furosemide',
            'espironolactona': 'spironolactone',
            'digoxina': 'digoxin',
            
            # Diabetes
            'metformina': 'metformin',
            'glibenclamida': 'glyburide/glibenclamide',
            'insulina': 'insulin',
            'insulina glargina': 'insulin glargine',
            'insulina lispro': 'insulin lispro',
            'sitagliptina': 'sitagliptin',
            
            # GI
            'omeprazol': 'omeprazole',
            'ranitidina': 'ranitidine',
            'sucralfato': 'sucralfate',
            'butilhioscina': 'hyoscine butylbromide',
            'buscapina': 'hyoscine butylbromide (brand)',
            'metoclopramida': 'metoclopramide',
            'loperamida': 'loperamide',
            'senosidos': 'sennosides',
            
            # Respiratory
            'salbutamol': 'albuterol/salbutamol',
            'bromuro de ipratropio': 'ipratropium bromide',
            'budesonida': 'budesonide',
            'montelukast': 'montelukast',
            'ambroxol': 'ambroxol',
            'dextrometorfano': 'dextromethorphan',
            'loratadina': 'loratadine',
            'clorfeniramina': 'chlorpheniramine',
            
            # Psychiatric
            'alprazolam': 'alprazolam',
            'clonazepam': 'clonazepam',
            'diazepam': 'diazepam',
            'fluoxetina': 'fluoxetine',
            'sertralina': 'sertraline',
            'paroxetina': 'paroxetine',
            'amitriptilina': 'amitriptyline',
            'haloperidol': 'haloperidol',
            'risperidona': 'risperidone',
            
            # Other
            'ácido fólico': 'folic acid',
            'sulfato ferroso': 'ferrous sulfate',
            'complejo b': 'B complex vitamins',
            'vitamina c': 'vitamin C',
            'calcio': 'calcium',
            'levotiroxina': 'levothyroxine',
            'prednisona': 'prednisone',
            'dexametasona': 'dexamethasone',
            'hidrocortisona': 'hydrocortisone',
        }
        
        self.glossary.update(medications)
        logger.info(f"Added {len(medications)} medication terms")
        
    def add_medical_abbreviations(self):
        """Add common Mexican medical abbreviations"""
        abbreviations = {
            # Conditions
            'hta': 'hypertension',
            'has': 'systemic arterial hypertension',
            'dm': 'diabetes mellitus',
            'dm2': 'type 2 diabetes mellitus',
            'dm1': 'type 1 diabetes mellitus',
            'iam': 'acute myocardial infarction',
            'icc': 'congestive heart failure',
            'evc': 'stroke/cerebrovascular event',
            'acv': 'cerebrovascular accident',
            'epoc': 'COPD',
            'asma': 'asthma',
            'irc': 'chronic renal insufficiency',
            'ira': 'acute renal insufficiency',
            'ivu': 'urinary tract infection',
            'eda': 'acute diarrheal disease',
            'ira vías respiratorias': 'acute respiratory infection',
            'tb': 'tuberculosis',
            'vih': 'HIV',
            'sida': 'AIDS',
            'ca': 'cancer',
            'fx': 'fracture',
            'tcr': 'traumatic brain injury',
            
            # Diagnostics
            'rx': 'x-ray',
            'tac': 'CT scan',
            'rm': 'MRI',
            'eco': 'ultrasound',
            'ecg': 'electrocardiogram',
            'ekg': 'electrocardiogram',
            'eeg': 'electroencephalogram',
            'bh': 'blood count',
            'qs': 'blood chemistry',
            'ego': 'urinalysis',
            'pfh': 'liver function tests',
            'pfr': 'renal function tests',
            'tpt': 'prothrombin time',
            'ttp': 'partial thromboplastin time',
            'vsg': 'erythrocyte sedimentation rate',
            'pcr': 'c-reactive protein',
            
            # Vitals/Measurements
            'ta': 'blood pressure',
            'pa': 'arterial pressure',
            'fc': 'heart rate',
            'fr': 'respiratory rate',
            'temp': 'temperature',
            't°': 'temperature',
            'spo2': 'oxygen saturation',
            'sato2': 'oxygen saturation',
            'peso': 'weight',
            'talla': 'height',
            'imc': 'BMI',
            'per. abd': 'abdominal perimeter',
            
            # Procedures/Treatments
            'cx': 'surgery',
            'qx': 'surgery',
            'tx': 'treatment',
            'dx': 'diagnosis',
            'px': 'prognosis',
            'bx': 'biopsy',
            'lape': 'exploratory laparotomy',
            'cole': 'cholecystectomy',
            'ape': 'appendectomy',
            'hta': 'total abdominal hysterectomy',
            'cesárea': 'cesarean section',
            'legrado': 'curettage',
            'ameu': 'manual vacuum aspiration',
            
            # Routes/Frequencies
            'vo': 'oral route',
            'iv': 'intravenous',
            'im': 'intramuscular',
            'sc': 'subcutaneous',
            'sl': 'sublingual',
            'prn': 'as needed',
            'qd': 'once daily',
            'bid': 'twice daily',
            'tid': 'three times daily',
            'qid': 'four times daily',
            'c/8h': 'every 8 hours',
            'c/12h': 'every 12 hours',
            'c/24h': 'every 24 hours',
            
            # Units
            'mg': 'milligrams',
            'g': 'grams',
            'kg': 'kilograms',
            'ml': 'milliliters',
            'l': 'liters',
            'ui': 'international units',
            'mmhg': 'millimeters of mercury',
            'lpm': 'liters per minute',
            'rpm': 'breaths per minute',
            'lxm': 'beats per minute',
            'mg/dl': 'milligrams per deciliter',
            'mmol/l': 'millimoles per liter',
        }
        
        self.glossary.update(abbreviations)
        logger.info(f"Added {len(abbreviations)} abbreviation expansions")
        
    def add_anatomy_terms(self):
        """Add anatomical terms"""
        anatomy = {
            # General
            'cabeza': 'head',
            'cuello': 'neck',
            'tórax': 'thorax/chest',
            'abdomen': 'abdomen',
            'pelvis': 'pelvis',
            'extremidades': 'extremities',
            'miembros superiores': 'upper limbs',
            'miembros inferiores': 'lower limbs',
            
            # Organs
            'cerebro': 'brain',
            'corazón': 'heart',
            'pulmones': 'lungs',
            'hígado': 'liver',
            'riñones': 'kidneys',
            'páncreas': 'pancreas',
            'bazo': 'spleen',
            'vesícula biliar': 'gallbladder',
            'vejiga': 'bladder',
            'útero': 'uterus',
            'ovarios': 'ovaries',
            'próstata': 'prostate',
            'tiroides': 'thyroid',
            
            # Systems
            'sistema nervioso': 'nervous system',
            'sistema cardiovascular': 'cardiovascular system',
            'sistema respiratorio': 'respiratory system',
            'sistema digestivo': 'digestive system',
            'sistema urinario': 'urinary system',
            'sistema reproductor': 'reproductive system',
            'sistema endocrino': 'endocrine system',
            'sistema inmunológico': 'immune system',
            'sistema musculoesquelético': 'musculoskeletal system',
        }
        
        self.glossary.update(anatomy)
        logger.info(f"Added {len(anatomy)} anatomy terms")
        
    def add_symptoms_signs(self):
        """Add symptoms and clinical signs"""
        symptoms = {
            # General
            'dolor': 'pain',
            'cefalea': 'headache',
            'mareo': 'dizziness',
            'vértigo': 'vertigo',
            'náusea': 'nausea',
            'vómito': 'vomiting',
            'fiebre': 'fever',
            'escalofríos': 'chills',
            'sudoración': 'sweating',
            'fatiga': 'fatigue',
            'debilidad': 'weakness',
            'malestar general': 'general malaise',
            'pérdida de peso': 'weight loss',
            'aumento de peso': 'weight gain',
            
            # Respiratory
            'tos': 'cough',
            'expectoración': 'expectoration/sputum',
            'hemoptisis': 'hemoptysis',
            'disnea': 'dyspnea/shortness of breath',
            'dolor torácico': 'chest pain',
            'sibilancias': 'wheezing',
            'estridor': 'stridor',
            
            # Cardiovascular
            'palpitaciones': 'palpitations',
            'dolor precordial': 'precordial pain',
            'edema': 'edema',
            'cianosis': 'cyanosis',
            'palidez': 'pallor',
            'lipotimia': 'fainting',
            'síncope': 'syncope',
            
            # GI
            'dolor abdominal': 'abdominal pain',
            'diarrea': 'diarrhea',
            'estreñimiento': 'constipation',
            'melena': 'melena',
            'hematoquecia': 'hematochezia',
            'hematemesis': 'hematemesis',
            'pirosis': 'heartburn',
            'disfagia': 'dysphagia',
            'distensión abdominal': 'abdominal distension',
            
            # Neurological
            'convulsiones': 'seizures',
            'parestesias': 'paresthesias',
            'parálisis': 'paralysis',
            'paresia': 'paresis',
            'afasia': 'aphasia',
            'disartria': 'dysarthria',
            'alteración del estado de conciencia': 'altered mental status',
            'pérdida de conciencia': 'loss of consciousness',
            
            # Skin
            'exantema': 'rash',
            'prurito': 'pruritus/itching',
            'ictericia': 'jaundice',
            'petequias': 'petechiae',
            'equimosis': 'ecchymosis',
            'eritema': 'erythema',
        }
        
        self.glossary.update(symptoms)
        logger.info(f"Added {len(symptoms)} symptom/sign terms")
        
    def add_procedures_diagnostics(self):
        """Add procedure and diagnostic terms"""
        procedures = {
            # Surgical
            'cirugía': 'surgery',
            'operación': 'operation',
            'intervención quirúrgica': 'surgical intervention',
            'anestesia general': 'general anesthesia',
            'anestesia local': 'local anesthesia',
            'anestesia regional': 'regional anesthesia',
            'sutura': 'suture',
            'drenaje': 'drainage',
            'debridación': 'debridement',
            'resección': 'resection',
            'anastomosis': 'anastomosis',
            'trasplante': 'transplant',
            
            # Diagnostic procedures
            'exploración física': 'physical examination',
            'auscultación': 'auscultation',
            'palpación': 'palpation',
            'percusión': 'percussion',
            'inspección': 'inspection',
            'punción lumbar': 'lumbar puncture',
            'paracentesis': 'paracentesis',
            'toracocentesis': 'thoracentesis',
            'artrocentesis': 'arthrocentesis',
            'endoscopia': 'endoscopy',
            'colonoscopia': 'colonoscopy',
            'broncoscopia': 'bronchoscopy',
            'cistoscopia': 'cystoscopy',
            
            # Imaging
            'radiografía': 'radiography/x-ray',
            'tomografía': 'tomography/CT scan',
            'resonancia magnética': 'magnetic resonance imaging',
            'ultrasonido': 'ultrasound',
            'ecografía': 'ultrasound/sonography',
            'mamografía': 'mammography',
            'angiografía': 'angiography',
            'gammagrafía': 'scintigraphy',
            
            # Lab tests
            'biometría hemática': 'complete blood count',
            'química sanguínea': 'blood chemistry',
            'examen general de orina': 'urinalysis',
            'cultivo': 'culture',
            'antibiograma': 'antibiogram',
            'prueba de embarazo': 'pregnancy test',
            'glucosa': 'glucose',
            'hemoglobina glucosilada': 'glycated hemoglobin',
            'perfil lipídico': 'lipid panel',
            'perfil tiroideo': 'thyroid panel',
        }
        
        self.glossary.update(procedures)
        logger.info(f"Added {len(procedures)} procedure/diagnostic terms")
        
    def add_common_phrases(self):
        """Add common medical phrases"""
        phrases = {
            # Assessment phrases
            'sin datos de': 'no evidence of',
            'con datos de': 'with evidence of',
            'a descartar': 'to rule out',
            'en estudio': 'under investigation',
            'por protocolo': 'per protocol',
            'a valorar': 'to be evaluated',
            'en control': 'under control',
            'en tratamiento': 'under treatment',
            
            # Clinical status
            'estable': 'stable',
            'grave': 'serious/severe',
            'crítico': 'critical',
            'reservado': 'guarded',
            'mejoría': 'improvement',
            'sin mejoría': 'no improvement',
            'deterioro': 'deterioration',
            'alta': 'discharge',
            'defunción': 'death',
            
            # Instructions
            'en ayunas': 'fasting',
            'con alimentos': 'with food',
            'antes de comidas': 'before meals',
            'después de comidas': 'after meals',
            'al acostarse': 'at bedtime',
            'por la mañana': 'in the morning',
            'por la noche': 'at night',
            'según necesidad': 'as needed',
            'hasta nueva orden': 'until further notice',
        }
        
        self.glossary.update(phrases)
        logger.info(f"Added {len(phrases)} common phrases")
        
    def save_glossary(self):
        """Save glossary to CSV file"""
        with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['es_term', 'en_term', 'category', 'source'])
            
            for es_term, en_term in sorted(self.glossary.items()):
                # Determine category
                if any(x in es_term for x in ['mg', 'ml', 'metformina', 'paracetamol']):
                    category = 'medication'
                elif any(x in es_term for x in ['dolor', 'fiebre', 'tos', 'náusea']):
                    category = 'symptom'
                elif any(x in es_term for x in ['cirugía', 'radiografía', 'cultivo']):
                    category = 'procedure'
                elif any(x in es_term for x in ['derechohabiente', 'consulta', 'expediente']):
                    category = 'administrative'
                elif len(es_term) <= 5:
                    category = 'abbreviation'
                else:
                    category = 'general'
                    
                writer.writerow([es_term, en_term, category, 'seed'])
                
        logger.info(f"Saved {len(self.glossary)} terms to {self.output_path}")
        
    def generate_full_glossary(self):
        """Generate complete seed glossary"""
        logger.info("Generating seed glossary...")
        
        self.add_imss_terms()
        self.add_mexican_medications()
        self.add_medical_abbreviations()
        self.add_anatomy_terms()
        self.add_symptoms_signs()
        self.add_procedures_diagnostics()
        self.add_common_phrases()
        
        self.save_glossary()
        
        # Print statistics
        categories = {}
        for es_term in self.glossary:
            if any(x in es_term for x in ['mg', 'ml', 'metformina', 'paracetamol']):
                cat = 'medication'
            elif any(x in es_term for x in ['dolor', 'fiebre', 'tos', 'náusea']):
                cat = 'symptom'
            elif any(x in es_term for x in ['cirugía', 'radiografía', 'cultivo']):
                cat = 'procedure'
            elif any(x in es_term for x in ['derechohabiente', 'consulta', 'expediente']):
                cat = 'administrative'
            elif len(es_term) <= 5:
                cat = 'abbreviation'
            else:
                cat = 'general'
                
            categories[cat] = categories.get(cat, 0) + 1
            
        print("\nGlossary Statistics:")
        print(f"Total terms: {len(self.glossary)}")
        print("\nBreakdown by category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")
            

def main():
    parser = argparse.ArgumentParser(description="Generate seed medical glossary")
    parser.add_argument(
        '--output',
        default='../data/glossaries/seed_glossary.csv',
        help='Output path for glossary CSV'
    )
    parser.add_argument(
        '--sources',
        default='all',
        help='Sources to include (all, imss, medications, abbreviations, etc.)'
    )
    
    args = parser.parse_args()
    
    generator = SeedGlossaryGenerator(args.output)
    
    if args.sources == 'all':
        generator.generate_full_glossary()
    else:
        sources = args.sources.split(',')
        if 'imss' in sources:
            generator.add_imss_terms()
        if 'medications' in sources:
            generator.add_mexican_medications()
        if 'abbreviations' in sources:
            generator.add_medical_abbreviations()
        if 'anatomy' in sources:
            generator.add_anatomy_terms()
        if 'symptoms' in sources:
            generator.add_symptoms_signs()
        if 'procedures' in sources:
            generator.add_procedures_diagnostics()
        if 'phrases' in sources:
            generator.add_common_phrases()
            
        generator.save_glossary()
        
    print(f"\n✅ Seed glossary generated: {generator.output_path}")
    print("This glossary will be replaced with UMLS data when license is approved")


if __name__ == "__main__":
    main()