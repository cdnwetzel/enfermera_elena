# Interim Translation Strategy (3-Day UMLS Wait Period)
## Immediate Implementation Options While Awaiting UMLS License

### Executive Summary
We have two viable paths to start translating medical records immediately while maintaining HIPAA compliance and preparing for UMLS integration on Day 3.

---

## Path A: Fully On-Premise (Zero External APIs) ✅ RECOMMENDED

### Overview
- **Privacy**: 100% on-premise, zero PHI exposure risk
- **Compliance**: Full HIPAA compliance without BAA requirements
- **Integration**: Seamless UMLS upgrade when license arrives

### Technology Stack

#### 1. LibreTranslate (Docker)
```bash
# Quick deployment
docker pull libretranslate/libretranslate
docker run -ti --rm -p 5000:5000 libretranslate/libretranslate \
  --load-only es,en \
  --disable-files-translation
```
- Uses Argos/Marian models under the hood
- REST API compatible with our scaffold
- ~2GB per language pair

#### 2. OPUS-MT Models (Alternative)
```python
from transformers import MarianMTModel, MarianTokenizer

model_name = "Helsinki-NLP/opus-mt-es-en"
tokenizer = MarianTokenizer.from_pretrained(model_name)
model = MarianMTModel.from_pretrained(model_name)
```
- Direct HuggingFace integration
- Lighter weight than LibreTranslate
- Better for batch processing

#### 3. Spanish Biomedical NER
```python
from transformers import pipeline

# For medical entity recognition and abbreviation expansion
ner = pipeline(
    "ner",
    model="PlanTL-GOB-ES/roberta-base-biomedical-clinical-es",
    aggregation_strategy="simple"
)
```

### Implementation Timeline

**Day 0-1: Core Translation**
- Deploy LibreTranslate via Docker
- Integrate with scaffold's mt/ module
- Implement PHI placeholder protection
- Test with sample documents

**Day 2: Medical Enhancement**
- Add Spanish biomedical NER
- Create abbreviation expander (HTA→Hipertensión, DM2→Diabetes Mellitus Tipo 2)
- Build seed glossary (1-3k terms)
- Implement term enforcement

**Day 3: UMLS Integration**
- Swap seed glossary for UMLS-generated glossary
- Add CUI anchoring
- Enhance with SNOMED CT mappings

---

## Path B: De-ID → OpenAI API → Re-ID

### Overview
- **Quality**: Superior translation quality and medical reasoning
- **Speed**: Fastest implementation (hours not days)
- **Risk**: Requires bulletproof de-identification

### Compliance Requirements

#### Critical: BAA Status
```
WITHOUT BAA: Only de-identified text (Safe Harbor + placeholders)
WITH BAA: Can process PHI with proper controls
```

#### OpenAI Enterprise Features
- Zero data retention (ZDR)
- No training on API data
- SOC 2 Type II certified
- HIPAA-eligible with BAA

### Implementation Safeguards

```python
class OpenAISecureAdapter:
    def __init__(self):
        self.phi_pattern = r'__PHI_[A-Z]+_\d+__'
        
    def validate_no_phi(self, text: str) -> bool:
        """Ensure text is fully de-identified"""
        # Check for common PHI patterns
        patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d',  # CURP
            r'\b\d{11}\b',  # NSS
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                raise ValueError("PHI detected in text!")
        return True
        
    def translate(self, text: str) -> str:
        # Validate de-identification
        self.validate_no_phi(text)
        
        # Preserve placeholders
        placeholders = re.findall(self.phi_pattern, text)
        
        # API call with medical context
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": "Translate Mexican Spanish medical text to English. "
                          "Preserve all __PHI_*__ placeholders exactly. "
                          "Use US medical terminology."
            }]
        )
        
        # Verify placeholder integrity
        self.verify_placeholders(text, response)
        return response
```

---

## Recommended 3-Day Implementation Plan

### Day 0: Foundation (4-6 hours)
```bash
# Morning: Deploy LibreTranslate
docker-compose up -d libretranslate

# Afternoon: Integrate with scaffold
python src/mt/libretranslate_adapter.py --test

# Evening: Verify PHI protection
pytest tests/test_phi_preservation.py
```

### Day 1: Medical Enhancement (6-8 hours)
```bash
# Download Spanish medical models
python scripts/download_medical_models.py

# Create seed glossary
python scripts/generate_seed_glossary.py \
  --sources "imss,cofepris,common" \
  --output data/glossaries/seed_glossary.csv

# Test medical term handling
python tests/test_medical_terms.py
```

### Day 2: Quality & Testing (4-6 hours)
```bash
# Process test documents
python pipeline.py \
  --input samples/imss_sample.pdf \
  --output output/translated.pdf \
  --config config/interim.yaml

# Generate quality metrics
python scripts/evaluate_translation.py

# Optional: Test OpenAI path (if compliant)
python src/mt/openai_adapter.py --test --dry-run
```

### Day 3: UMLS Integration (When Licensed)
```bash
# Download UMLS data
./scripts/download_umls.sh

# Generate production glossary
python scripts/prepare_umls_data.py

# Swap glossaries
mv data/glossaries/seed_glossary.csv data/glossaries/seed_glossary.backup
cp data/umls/glossary_es_en.csv data/glossaries/production_glossary.csv

# Restart with UMLS support
python pipeline.py --config config/production.yaml
```

---

## Seed Glossary Sources (Available Now)

### 1. Public Medical Lexicons
- **MedlinePlus Spanish**: Medical terms and consumer health
- **WHO ICD-10 Spanish**: Disease classifications
- **RxNorm Spanish mappings**: Medication names

### 2. Mexican-Specific Terms
```csv
es_term,en_term,category,notes
derechohabiente,beneficiary,admin,IMSS term
consulta externa,outpatient visit,service,Common in IMSS
urgencias,emergency room,service,ER department
expediente clínico,clinical record,admin,Medical record
receta médica,prescription,document,Medical prescription
metamizol,dipyrone,drug,Common in Mexico
paracetamol,acetaminophen,drug,Same active ingredient
clonixinato de lisina,lysine clonixinate,drug,Mexican NSAID
```

### 3. Abbreviation Expansions
```csv
abbrev,expansion_es,expansion_en
HTA,Hipertensión Arterial,Hypertension
DM2,Diabetes Mellitus Tipo 2,Type 2 Diabetes
IAM,Infarto Agudo al Miocardio,Acute Myocardial Infarction
EVC,Evento Vascular Cerebral,Stroke
EPOC,Enfermedad Pulmonar Obstructiva Crónica,COPD
```

---

## Adapter Configuration

### config/interim.yaml
```yaml
translation:
  # Choose: libretranslate, opus-mt, openai
  backend: libretranslate
  
  libretranslate:
    host: localhost
    port: 5000
    api_key: optional
    timeout: 30
    
  opus_mt:
    model: Helsinki-NLP/opus-mt-es-en
    device: cuda  # or cpu
    batch_size: 32
    
  openai:
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
    temperature: 0.3
    validate_no_phi: true
    
glossary:
  path: data/glossaries/seed_glossary.csv
  enforce_terms: true
  never_translate:
    - "__PHI_*__"
    - "CURP"
    - "RFC"
    - "NSS"
    
medical_ner:
  enabled: true
  model: PlanTL-GOB-ES/roberta-base-biomedical-clinical-es
  expand_abbreviations: true
  abbreviations_db: data/abbreviations.csv
```

---

## Quality Metrics (Expected)

| Metric | LibreTranslate | OPUS-MT | OpenAI | UMLS-Enhanced |
|--------|---------------|---------|---------|---------------|
| General accuracy | 85% | 87% | 94% | 89% |
| Medical terms | 75% | 78% | 88% | 95% |
| Mexican terms | 65% | 67% | 82% | 93% |
| Speed (pages/min) | 15 | 20 | 5 | 18 |
| PHI Safety | 100% | 100% | 99%* | 100% |
| Cost | $0 | $0 | ~$0.10/page | $0 |

*Requires proper de-identification

---

## Risk Mitigation

### For Path A (On-Premise)
- **Risk**: Lower initial quality
- **Mitigation**: Use medical NER + seed glossary
- **Upgrade**: UMLS integration on Day 3

### For Path B (OpenAI)
- **Risk**: PHI exposure
- **Mitigation**: Strict validation + placeholder preservation
- **Requirement**: BAA for production use

### For Both Paths
- **Risk**: Mexican term confusion
- **Mitigation**: Seed glossary with IMSS/COFEPRIS terms
- **Validation**: Mexican physician review

---

## Immediate Next Steps

1. **Choose Path A or B** based on compliance requirements
2. **Deploy chosen backend** (LibreTranslate recommended)
3. **Create seed glossary** from available sources
4. **Test with real IMSS samples** (de-identified)
5. **Prepare for UMLS integration** on Day 3

---

## Commands to Start Now

```bash
# Path A: Deploy LibreTranslate
cd enfermera_elena
docker pull libretranslate/libretranslate
docker run -d -p 5000:5000 libretranslate/libretranslate --load-only es,en

# Test translation
curl -X POST http://localhost:5000/translate \
  -H "Content-Type: application/json" \
  -d '{"q": "El paciente presenta hipertensión arterial", "source": "es", "target": "en"}'

# Create seed glossary
python scripts/generate_seed_glossary.py

# Run interim pipeline
python cli.py translate \
  --input samples/test.pdf \
  --output output/translated.pdf \
  --backend libretranslate
```

---

*Last Updated: 2025-09-05*
*Status: Ready for immediate implementation*
*UMLS Integration: Day 3*