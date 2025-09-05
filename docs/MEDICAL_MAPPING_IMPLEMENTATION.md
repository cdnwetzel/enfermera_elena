# Medical Mapping Implementation Guide
## Hybrid Ontology + Neural Approach for Mexican Clinical Text

### Version 1.0 | Date: 2025-09-05

---

## Executive Summary

Rather than simple dictionary lookup, we implement a **two-lever system**:
1. **Ontology Anchoring** (UMLS/SNOMED CT Mexico) for rigorous medical accuracy
2. **Neural Helpers** (BETO/RoBERTuito) for handling real-world messiness

This hybrid approach ensures both medical correctness AND robustness to typos, abbreviations, and regional variants.

## Architecture Overview

```
Mexican Clinical Text
        ↓
┌──────────────────────────────────┐
│  1. Entity Recognition (Neural)   │ ← RoBERTuito/Spanish-BioBERT
│  "HTA" → "hipertensión arterial"  │
└──────────────────────────────────┘
        ↓
┌──────────────────────────────────┐
│  2. Concept Mapping (Ontology)    │ ← UMLS/SNOMED CT Mexico
│  "hipertensión arterial" → C0020538│
└──────────────────────────────────┘
        ↓
┌──────────────────────────────────┐
│  3. Canonical English (Lookup)    │ ← CUI → English mapping
│  C0020538 → "hypertension"        │
└──────────────────────────────────┘
        ↓
┌──────────────────────────────────┐
│  4. Glossary-Forced Translation   │ ← MT with terminology constraints
│  Preserve medical terms exactly   │
└──────────────────────────────────┘
```

## Component 1: Ontology Integration

### UMLS Setup (Free with Registration)

```python
# 1. Register at https://uts.nlm.nih.gov/uts/
# 2. Download UMLS Metathesaurus
# 3. Extract Spanish subset

from umls_api import UMLSClient

class UMLSMedicalMapper:
    """Map Spanish terms to CUIs and English labels"""
    
    def __init__(self, api_key: str):
        self.client = UMLSClient(api_key)
        self.cache = {}  # CUI → translations cache
        
    def spanish_to_cui(self, term: str) -> str:
        """Map Spanish term to Concept Unique Identifier"""
        # Search UMLS for Spanish term
        results = self.client.search(
            string=term,
            inputType="sourceUi",
            searchType="exact",
            sources=["SCTSPA", "MSHSPA"],  # Spanish sources
        )
        
        if results:
            return results[0]["ui"]  # CUI
        return None
    
    def cui_to_english(self, cui: str) -> str:
        """Get preferred English term for CUI"""
        if cui in self.cache:
            return self.cache[cui]
            
        concept = self.client.getConcept(cui)
        english_name = concept.getPreferredName(language="ENG")
        self.cache[cui] = english_name
        return english_name
    
    def map_term(self, spanish_term: str) -> tuple[str, str, float]:
        """Complete mapping: Spanish → CUI → English"""
        cui = self.spanish_to_cui(spanish_term)
        if cui:
            english = self.cui_to_english(cui)
            return cui, english, 1.0  # High confidence
        return None, None, 0.0
```

### SNOMED CT Mexico Edition

```python
import pandas as pd

class SNOMEDMexicoMapper:
    """Mexican-specific medical terminology"""
    
    def __init__(self, concept_file: str, description_file: str):
        # Load SNOMED CT Mexico files (requires license)
        self.concepts = pd.read_csv(concept_file, sep='\t')
        self.descriptions = pd.read_csv(description_file, sep='\t')
        
        # Build Spanish → English mapping
        self.build_bilingual_map()
    
    def build_bilingual_map(self):
        """Create Spanish → English term mappings"""
        self.term_map = {}
        
        # Group descriptions by concept
        for concept_id in self.concepts['id'].unique():
            spanish_terms = self.descriptions[
                (self.descriptions['conceptId'] == concept_id) &
                (self.descriptions['languageCode'] == 'es-MX')
            ]['term'].tolist()
            
            english_terms = self.descriptions[
                (self.descriptions['conceptId'] == concept_id) &
                (self.descriptions['languageCode'] == 'en')
            ]['term'].tolist()
            
            # Map all Spanish variants to preferred English
            for sp_term in spanish_terms:
                if english_terms:
                    self.term_map[sp_term.lower()] = english_terms[0]
    
    def translate(self, spanish_term: str) -> str:
        """Get English equivalent from SNOMED"""
        return self.term_map.get(spanish_term.lower())
```

### Drug Mapping with ATC + COFEPRIS

```python
class MexicanDrugMapper:
    """Map Mexican brand names to generic + ATC codes"""
    
    def __init__(self):
        # Load COFEPRIS drug database
        self.cofepris_db = self.load_cofepris()
        # Load WHO ATC classification
        self.atc_db = self.load_atc()
        
    def load_cofepris(self) -> dict:
        """Load Mexican drug registry"""
        # Download from: https://www.gob.mx/cofepris
        drugs = {}
        # Format: Brand → Generic + ATC
        drugs['tempra'] = {'generic': 'paracetamol', 'atc': 'N02BE01'}
        drugs['winadeine f'] = {'generic': 'paracetamol+codeine', 'atc': 'N02AJ06'}
        # ... load full database
        return drugs
    
    def map_drug(self, brand_name: str) -> dict:
        """Map Mexican brand to international generic"""
        brand_lower = brand_name.lower()
        if brand_lower in self.cofepris_db:
            drug_info = self.cofepris_db[brand_lower]
            # Add English generic name from ATC
            atc_code = drug_info['atc']
            english_generic = self.atc_db.get(atc_code, {}).get('english_name')
            return {
                'mexican_brand': brand_name,
                'generic_spanish': drug_info['generic'],
                'generic_english': english_generic,
                'atc_code': atc_code
            }
        return None
```

## Component 2: Neural Model Integration

### Spanish Biomedical Entity Recognition

```python
from transformers import AutoTokenizer, AutoModelForTokenClassification
import torch

class SpanishMedicalNER:
    """Neural entity recognition for Spanish clinical text"""
    
    def __init__(self):
        # Load PlanTL's Spanish biomedical model
        model_name = "PlanTL-GOB-ES/roberta-base-biomedical-clinical-es"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(model_name)
        self.model.eval()
    
    def extract_entities(self, text: str) -> list:
        """Extract medical entities from Spanish text"""
        # Tokenize
        inputs = self.tokenizer(
            text, 
            return_tensors="pt",
            truncation=True,
            max_length=512
        )
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.argmax(outputs.logits, dim=-1)
        
        # Decode entities
        tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        labels = [self.model.config.id2label[p.item()] for p in predictions[0]]
        
        # Group into entities
        entities = []
        current_entity = []
        current_label = None
        
        for token, label in zip(tokens, labels):
            if label.startswith("B-"):  # Beginning of entity
                if current_entity:
                    entities.append((" ".join(current_entity), current_label))
                current_entity = [token.replace("▁", "")]
                current_label = label[2:]
            elif label.startswith("I-"):  # Inside entity
                current_entity.append(token.replace("▁", ""))
            else:  # Outside entity
                if current_entity:
                    entities.append((" ".join(current_entity), current_label))
                    current_entity = []
                    current_label = None
        
        return entities
```

### Fuzzy Matching with BETO Embeddings

```python
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class BETOSimilarityMatcher:
    """Use BETO embeddings for fuzzy medical term matching"""
    
    def __init__(self):
        # Load BETO (Spanish BERT)
        model_name = "dccuchile/bert-base-spanish-wwm-cased"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        
        # Pre-compute embeddings for known terms
        self.term_embeddings = {}
        self.load_medical_vocabulary()
    
    def load_medical_vocabulary(self):
        """Pre-compute embeddings for medical terms"""
        medical_terms = [
            "hipertensión arterial",
            "diabetes mellitus",
            "infarto agudo de miocardio",
            # ... load from UMLS/SNOMED
        ]
        
        for term in medical_terms:
            self.term_embeddings[term] = self.get_embedding(term)
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Get BETO embedding for text"""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use [CLS] token embedding
            embedding = outputs.last_hidden_state[0][0].numpy()
        return embedding
    
    def find_similar_term(self, query: str, threshold: float = 0.85) -> str:
        """Find most similar medical term using embeddings"""
        query_embedding = self.get_embedding(query)
        
        best_match = None
        best_score = 0
        
        for term, term_embedding in self.term_embeddings.items():
            similarity = cosine_similarity(
                query_embedding.reshape(1, -1),
                term_embedding.reshape(1, -1)
            )[0][0]
            
            if similarity > best_score and similarity > threshold:
                best_score = similarity
                best_match = term
        
        return best_match, best_score
```

### Abbreviation Expansion

```python
class MedicalAbbreviationExpander:
    """Expand Mexican medical abbreviations using context"""
    
    def __init__(self):
        # Common Mexican medical abbreviations
        self.abbreviations = {
            'HTA': 'hipertensión arterial',
            'DM': 'diabetes mellitus',
            'DM2': 'diabetes mellitus tipo 2',
            'IAM': 'infarto agudo del miocardio',
            'EVC': 'evento vascular cerebral',
            'EPOC': 'enfermedad pulmonar obstructiva crónica',
            'IRC': 'insuficiencia renal crónica',
            'ICC': 'insuficiencia cardíaca congestiva',
            'CA': 'cáncer',
            'Tx': 'tratamiento',
            'Dx': 'diagnóstico',
            'Px': 'pronóstico',
            'Qx': 'quirúrgico',
            'PO': 'postoperatorio',
            'VSC': 'vida sexual conservada',
            'PAEG': 'producto adecuado para edad gestacional'
        }
        
        # Context-aware model for ambiguous abbreviations
        self.context_model = self.load_context_model()
    
    def expand_in_text(self, text: str) -> str:
        """Expand all abbreviations in text"""
        expanded = text
        for abbr, full_form in self.abbreviations.items():
            # Use word boundaries to avoid partial matches
            pattern = rf'\b{abbr}\b'
            expanded = re.sub(pattern, f'{abbr} ({full_form})', expanded)
        return expanded
    
    def context_aware_expansion(self, abbr: str, context: str) -> str:
        """Use context to disambiguate abbreviations"""
        # Example: "CA" could be "cáncer" or "California"
        if abbr == "CA":
            if any(word in context.lower() for word in ['metástasis', 'tumor', 'oncología']):
                return 'cáncer'
            elif any(word in context.lower() for word in ['estado', 'usa', 'dirección']):
                return 'California'
        
        return self.abbreviations.get(abbr, abbr)
```

## Integrated Pipeline

### Complete Medical Mapping System

```python
class MexicanMedicalMappingPipeline:
    """Orchestrate all components for medical term mapping"""
    
    def __init__(self, umls_key: str, snomed_path: str):
        # Ontology components
        self.umls_mapper = UMLSMedicalMapper(umls_key)
        self.snomed_mapper = SNOMEDMexicoMapper(snomed_path)
        self.drug_mapper = MexicanDrugMapper()
        
        # Neural components
        self.ner_model = SpanishMedicalNER()
        self.similarity_matcher = BETOSimilarityMatcher()
        self.abbr_expander = MedicalAbbreviationExpander()
        
        # Translation glossary
        self.glossary = {}
    
    def process_document(self, text: str) -> dict:
        """Complete medical mapping pipeline"""
        
        # Step 1: Expand abbreviations
        expanded_text = self.abbr_expander.expand_in_text(text)
        
        # Step 2: Extract medical entities (neural)
        entities = self.ner_model.extract_entities(expanded_text)
        
        # Step 3: Map each entity to standardized concepts
        mapped_entities = []
        for entity_text, entity_type in entities:
            
            # Try exact ontology match first
            cui, english_term, confidence = self.umls_mapper.map_term(entity_text)
            
            # If no exact match, try fuzzy matching
            if not cui:
                similar_term, similarity = self.similarity_matcher.find_similar_term(entity_text)
                if similar_term:
                    cui, english_term, _ = self.umls_mapper.map_term(similar_term)
                    confidence = similarity
            
            # Special handling for drugs
            if entity_type == "MEDICATION":
                drug_info = self.drug_mapper.map_drug(entity_text)
                if drug_info:
                    english_term = drug_info['generic_english']
            
            mapped_entities.append({
                'spanish': entity_text,
                'english': english_term,
                'cui': cui,
                'type': entity_type,
                'confidence': confidence
            })
            
            # Add to glossary for forced translation
            if english_term:
                self.glossary[entity_text] = english_term
        
        return {
            'processed_text': expanded_text,
            'entities': mapped_entities,
            'glossary': self.glossary
        }
    
    def prepare_for_translation(self, text: str) -> str:
        """Prepare text with medical term anchoring"""
        # Process document to build glossary
        result = self.process_document(text)
        
        # Replace medical terms with placeholders
        prepared_text = result['processed_text']
        for i, entity in enumerate(result['entities']):
            if entity['english']:
                # Use placeholder that preserves meaning
                placeholder = f"[MEDICAL_{i}:{entity['english']}]"
                prepared_text = prepared_text.replace(
                    entity['spanish'], 
                    placeholder
                )
        
        return prepared_text, result['glossary']
```

## Implementation Workflow

### Phase 1: Setup Ontologies (Week 1)

```bash
# 1. Register for UMLS
# https://uts.nlm.nih.gov/uts/

# 2. Download UMLS Metathesaurus
# Select Spanish sources: SCTSPA, MSHSPA, MDRSPA

# 3. Request SNOMED CT Mexico
# Through Mexican health authority or SNOMED International

# 4. Download COFEPRIS drug database
# https://www.gob.mx/cofepris/acciones-y-programas/registros-sanitarios

# 5. Get WHO ATC classification
# https://www.whocc.no/atc_ddd_index/
```

### Phase 2: Setup Neural Models (Week 1)

```python
# Install transformers
pip install transformers torch scikit-learn

# Download models
from transformers import AutoModel, AutoTokenizer

models = [
    "PlanTL-GOB-ES/roberta-base-biomedical-clinical-es",  # Spanish medical NER
    "dccuchile/bert-base-spanish-wwm-cased",              # BETO for embeddings
    "BSC-TeMU/roberta-base-biomedical-es",                # Alternative medical model
]

for model_name in models:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    # Save locally for offline use
    tokenizer.save_pretrained(f"./models/{model_name.split('/')[-1]}")
    model.save_pretrained(f"./models/{model_name.split('/')[-1]}")
```

### Phase 3: Integration with Scaffold (Week 2)

```python
# Modify scaffold's pipeline.py

def run_pipeline(pdf_in: str, pdf_out: str, cfg: AppConfig):
    # ... existing OCR code ...
    
    # NEW: Medical mapping stage
    medical_mapper = MexicanMedicalMappingPipeline(
        umls_key=cfg.umls_api_key,
        snomed_path=cfg.snomed_path
    )
    
    # Process extracted text
    prepared_text, glossary = medical_mapper.prepare_for_translation(text)
    
    # Continue with de-id
    deid_text = deid_engine.deidentify(prepared_text)
    
    # Translate with glossary forcing
    translated = translate_with_glossary(deid_text, glossary)
    
    # ... rest of pipeline ...
```

## Performance Optimizations

### Caching Strategy

```python
import pickle
from functools import lru_cache

class CachedMedicalMapper:
    """Cache expensive lookups"""
    
    def __init__(self):
        self.load_or_build_cache()
    
    def load_or_build_cache(self):
        try:
            with open('medical_cache.pkl', 'rb') as f:
                self.cache = pickle.load(f)
        except:
            self.cache = {}
            self.build_cache()
    
    def build_cache(self):
        """Pre-compute common medical terms"""
        common_terms = load_common_mexican_medical_terms()
        for term in common_terms:
            self.cache[term] = self.map_term(term)
        self.save_cache()
    
    @lru_cache(maxsize=10000)
    def map_term(self, term: str) -> dict:
        """LRU cache for recent lookups"""
        if term in self.cache:
            return self.cache[term]
        # Compute and cache
        result = self.compute_mapping(term)
        self.cache[term] = result
        return result
```

### Batch Processing

```python
def batch_process_entities(entities: list, batch_size: int = 32):
    """Process entities in batches for GPU efficiency"""
    results = []
    for i in range(0, len(entities), batch_size):
        batch = entities[i:i+batch_size]
        # Process batch on GPU
        batch_embeddings = model.encode(batch)
        batch_results = process_embeddings(batch_embeddings)
        results.extend(batch_results)
    return results
```

## Quality Assurance

### Medical Term Validation

```python
def validate_medical_mapping(spanish: str, english: str, cui: str) -> bool:
    """Ensure mapping quality"""
    checks = []
    
    # Check 1: CUI exists and is active
    checks.append(umls_client.is_active_concept(cui))
    
    # Check 2: English term matches CUI
    checks.append(umls_client.get_english_name(cui) == english)
    
    # Check 3: Semantic type is medical
    semantic_types = umls_client.get_semantic_types(cui)
    medical_types = ['Disease or Syndrome', 'Pharmacologic Substance', 'Body Part']
    checks.append(any(st in medical_types for st in semantic_types))
    
    return all(checks)
```

## Conclusion

This hybrid approach gives us:
1. **Accuracy** from ontologies (UMLS/SNOMED)
2. **Flexibility** from neural models (BETO/RoBERTuito)
3. **Robustness** to handle real Mexican medical documents

The two-lever system ensures we can handle both standardized medical concepts AND the messy reality of hospital records (abbreviations, typos, regional variants).

---

*Document Status: Implementation guide complete*
*Key Technologies: UMLS, SNOMED CT Mexico, BETO, RoBERTuito*
*Next Step: Register for UMLS and download models*