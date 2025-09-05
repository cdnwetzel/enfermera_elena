# PHI De-identification Strategy
## HIPAA-Compliant Translation Pipeline

### Version 1.0 | Date: 2025-09-05

---

## Executive Summary

Translation services (even HIPAA-eligible ones from AWS/Google) should NOT receive raw PHI. The safest approach is to de-identify BEFORE translation, then re-identify after. This document outlines our de-identification strategy for HIPAA compliance.

## The HIPAA Challenge

### Two Approaches to Cloud Translation

#### Option 1: BAA with Cloud Provider (Risky)
```yaml
AWS/Google with BAA:
  - Status: "HIPAA-eligible" not "HIPAA-compliant"
  - Risk: You're still sending PHI to third party
  - Liability: Shared with provider
  - Audit: Must track all PHI transmissions
  - Cost: Higher tier pricing
```

#### Option 2: De-identification First (Recommended) ✅
```yaml
De-identify → Translate → Re-identify:
  - Status: No PHI leaves your control
  - Risk: Minimal - only anonymous text translated
  - Liability: None for translation service
  - Audit: Simpler - no PHI transmitted
  - Cost: Standard pricing tiers
```

## De-identification Pipeline

### Architecture
```python
class HIPAACompliantTranslation:
    """
    De-identify → Translate → Re-identify Pipeline
    """
    
    def translate_with_privacy(self, document):
        # Step 1: Detect and extract PHI
        phi_entities, tokens = self.detect_phi(document)
        
        # Step 2: Replace PHI with tokens
        de_identified = self.tokenize_phi(document, phi_entities)
        # "Juan García, nacido 15/03/1980" → "[NAME_001], nacido [DATE_001]"
        
        # Step 3: Translate de-identified text (safe for any service)
        translated = self.translate(de_identified)  # Can use ANY service
        # "[NAME_001], born [DATE_001]"
        
        # Step 4: Re-insert PHI
        final = self.re_identify(translated, tokens)
        # "Juan García, born 03/15/1980"
        
        return final
```

## PHI Detection Methods

### Method 1: Rule-Based (Fast, Deterministic)
```python
class RuleBasedPHIDetector:
    """
    Regex patterns for Mexican documents
    """
    
    patterns = {
        # Mexican specific
        'CURP': r'[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d',
        'RFC': r'[A-Z]{4}\d{6}[A-Z0-9]{3}',
        'NSS': r'\d{11}',  # IMSS number
        
        # Universal PHI
        'DATE': r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        'PHONE': r'[\+]?[\d\s\(\)\-]{10,}',
        'EMAIL': r'[\w\.-]+@[\w\.-]+\.\w+',
        
        # Mexican names (more complex)
        'NAME': r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+',
        
        # Medical Record Numbers
        'MRN': r'(expediente|folio|registro)[\s:#]*[\d\-]+',
        
        # Addresses (Mexican format)
        'ADDRESS': r'(Calle|Av\.|Blvd\.)[^,\n]{10,50}(Col\.|Colonia)[^,\n]{5,30}'
    }
    
    def detect(self, text):
        entities = []
        for phi_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, text):
                entities.append({
                    'type': phi_type,
                    'text': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
        return entities
```

### Method 2: ML-Based (More Accurate)
```python
class MLBasedPHIDetector:
    """
    Using AWS Comprehend Medical or Google Healthcare NLP
    """
    
    def detect_with_comprehend_medical(self, text):
        # AWS Comprehend Medical (HIPAA-eligible for detection only)
        response = comprehend_medical.detect_phi(
            Text=text,
            LanguageCode='es'  # Spanish support limited
        )
        
        # Returns entities with confidence scores
        return response['Entities']
    
    def detect_with_presidio(self, text):
        # Microsoft Presidio (open source, self-hosted)
        from presidio_analyzer import AnalyzerEngine
        
        analyzer = AnalyzerEngine()
        results = analyzer.analyze(
            text=text,
            language='es',
            entities=["PERSON", "PHONE_NUMBER", "DATE_TIME", "MEDICAL_LICENSE"]
        )
        return results
```

### Method 3: Hybrid Approach (Recommended) ✅
```python
class HybridPHIDetector:
    """
    Combine rule-based for Mexican-specific + ML for general
    """
    
    def detect(self, text):
        # Mexican-specific patterns (CURP, RFC, NSS)
        mexican_phi = self.rule_based_mexican(text)
        
        # General PHI detection with ML
        general_phi = self.ml_based_detection(text)
        
        # Combine and deduplicate
        all_phi = self.merge_detections(mexican_phi, general_phi)
        
        # Manual validation for low confidence
        if self.requires_review(all_phi):
            all_phi = self.flag_for_human_review(all_phi)
        
        return all_phi
```

## Tokenization Strategy

### Safe Tokenization
```python
class PHITokenizer:
    """
    Replace PHI with safe, reversible tokens
    """
    
    def tokenize(self, text, phi_entities):
        # Sort by position (reverse to maintain indices)
        sorted_entities = sorted(phi_entities, key=lambda x: x['start'], reverse=True)
        
        tokenized = text
        token_map = {}
        
        for entity in sorted_entities:
            # Generate unique token
            token = f"[{entity['type']}_{uuid.uuid4().hex[:8]}]"
            
            # Store mapping
            token_map[token] = {
                'original': entity['text'],
                'type': entity['type'],
                'format': self.detect_format(entity['text'])
            }
            
            # Replace in text
            tokenized = (
                tokenized[:entity['start']] + 
                token + 
                tokenized[entity['end']:]
            )
        
        return tokenized, token_map
    
    def format_preserving_token(self, phi_value, phi_type):
        """
        Maintain format for better translation context
        """
        if phi_type == 'DATE':
            return "[DATE_XX/XX/XXXX]"  # Preserve date format
        elif phi_type == 'PHONE':
            return "[PHONE_XXX-XXX-XXXX]"  # Preserve phone format
        elif phi_type == 'NAME':
            return "[FIRSTNAME] [LASTNAME]"  # Preserve name structure
        else:
            return f"[{phi_type}]"
```

## Re-identification Process

### Secure Re-identification
```python
class PHIReidentifier:
    """
    Safely restore PHI after translation
    """
    
    def re_identify(self, translated_text, token_map):
        final_text = translated_text
        
        # Handle date format conversion (DD/MM/YYYY → MM/DD/YYYY)
        for token, data in token_map.items():
            if token in final_text:
                if data['type'] == 'DATE':
                    # Convert Mexican to US date format
                    original_value = self.convert_date_format(data['original'])
                else:
                    original_value = data['original']
                
                final_text = final_text.replace(token, original_value)
        
        # Validate all tokens were replaced
        remaining_tokens = re.findall(r'\[\w+_\w{8}\]', final_text)
        if remaining_tokens:
            raise ValueError(f"Unreplaced tokens found: {remaining_tokens}")
        
        return final_text
    
    def convert_date_format(self, mexican_date):
        """Convert DD/MM/YYYY to MM/DD/YYYY"""
        try:
            parsed = datetime.strptime(mexican_date, '%d/%m/%Y')
            return parsed.strftime('%m/%d/%Y')
        except:
            return mexican_date  # Return as-is if parsing fails
```

## Implementation Options

### Option A: External Service (Simple)
```yaml
Architecture:
  1. Your Server: De-identification
  2. AWS/Google Translate: Translation (no BAA needed!)
  3. Your Server: Re-identification

Pros:
  - No BAA required
  - Use any translation service
  - Lower costs
  - Simple compliance

Cons:
  - Tokens might affect translation quality
  - Need robust de-identification
```

### Option B: Internal Service (Secure)
```yaml
Architecture:
  1. Your Server: De-identification
  2. Your GPU: Translation (self-hosted models)
  3. Your Server: Re-identification

Pros:
  - No data leaves your infrastructure
  - Complete control
  - No compliance concerns

Cons:
  - Higher infrastructure costs
  - Maintain models yourself
```

### Option C: Hybrid (Recommended) ✅
```yaml
Architecture:
  1. Your Server: De-identification
  2. Decision Router:
     - High confidence PHI removal → External service
     - Low confidence → Internal processing
  3. Your Server: Re-identification

Pros:
  - Balance of security and performance
  - Cost-effective
  - Flexible routing

Cons:
  - More complex logic
```

## Compliance Validation

### Audit Requirements
```python
class PHIAuditLog:
    """
    Track all PHI handling for compliance
    """
    
    def log_de_identification(self, document_id, phi_found):
        audit_entry = {
            'timestamp': datetime.utcnow(),
            'document_id': document_id,
            'phi_detected': len(phi_found),
            'phi_types': list(set([p['type'] for p in phi_found])),
            'de_id_method': 'hybrid',
            'success': True
        }
        
        # Never log actual PHI values!
        self.write_to_audit_log(audit_entry)
    
    def verify_no_phi_transmitted(self, text_sent_to_translator):
        """
        Final check before external transmission
        """
        quick_patterns = [
            r'\d{3}-\d{2}-\d{4}',  # SSN
            r'[A-Z]{4}\d{6}',  # CURP prefix
            r'\d{11}',  # NSS
        ]
        
        for pattern in quick_patterns:
            if re.search(pattern, text_sent_to_translator):
                raise ValueError("PHI detected in text to be transmitted!")
        
        return True
```

## Special Considerations for Mexican Documents

### Mexican-Specific PHI
```python
MEXICAN_PHI = {
    'CURP': {
        'pattern': r'[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d',
        'description': 'Unique Population Registry Code',
        'sensitivity': 'HIGH'
    },
    'RFC': {
        'pattern': r'[A-Z]{4}\d{6}[A-Z0-9]{3}',
        'description': 'Federal Taxpayer Registry',
        'sensitivity': 'HIGH'
    },
    'NSS': {
        'pattern': r'\d{11}',
        'description': 'Social Security Number (IMSS)',
        'sensitivity': 'HIGH'
    },
    'INE': {
        'pattern': r'IDMEX\d{13}',
        'description': 'Voter ID number',
        'sensitivity': 'MEDIUM'
    },
    'Folio': {
        'pattern': r'[Ff]olio[\s:]*[\d\-]+',
        'description': 'Medical record number',
        'sensitivity': 'HIGH'
    }
}
```

### IMSS Document Structure
```python
def handle_imss_format(document):
    """
    IMSS documents have predictable PHI locations
    """
    sections = {
        'header': {
            'contains_phi': True,
            'fields': ['NSS', 'name', 'CURP', 'birthdate']
        },
        'clinical_notes': {
            'contains_phi': False,  # Usually safe
            'fields': []
        },
        'prescriptions': {
            'contains_phi': False,
            'fields': []
        },
        'footer': {
            'contains_phi': True,
            'fields': ['doctor_cedula', 'signature']
        }
    }
    
    # Can optimize by only de-identifying specific sections
    return sections
```

## Testing & Validation

### De-identification Validation
```python
class DeIdentificationValidator:
    """
    Ensure complete PHI removal
    """
    
    def validate_complete_removal(self, original, de_identified):
        # Test with known PHI patterns
        test_patterns = {
            'CURP': 'BACJ800315HDFRRN09',
            'Phone': '52 55 1234 5678',
            'Email': 'juan.garcia@email.com',
            'Date': '15/03/1980'
        }
        
        for phi_type, value in test_patterns.items():
            if value in de_identified:
                raise AssertionError(f"{phi_type} not removed: {value}")
        
        return True
    
    def validate_re_identification(self, original, final):
        """
        Ensure PHI correctly restored
        """
        # All original PHI should be in final document
        # But translated text should be different
        pass
```

## Recommended Architecture

```python
class SafeTranslationPipeline:
    """
    Complete HIPAA-compliant translation
    """
    
    def __init__(self):
        self.de_identifier = HybridPHIDetector()
        self.tokenizer = PHITokenizer()
        self.translator = self.select_translator()
        self.re_identifier = PHIReidentifier()
        self.auditor = PHIAuditLog()
    
    def select_translator(self):
        """
        Choose based on compliance requirements
        """
        if self.organization_requires_baa:
            return AWSTranslateWithBAA()  # More expensive
        else:
            return StandardTranslationAPI()  # After de-identification
    
    def translate_document(self, document):
        # 1. Detect PHI
        phi_entities = self.de_identifier.detect(document)
        self.auditor.log_de_identification(document.id, phi_entities)
        
        # 2. Remove PHI
        safe_text, token_map = self.tokenizer.tokenize(document.text, phi_entities)
        
        # 3. Verify no PHI remains
        self.verify_no_phi(safe_text)
        
        # 4. Translate (safe for any service)
        translated = self.translator.translate(safe_text)
        
        # 5. Restore PHI
        final = self.re_identifier.re_identify(translated, token_map)
        
        # 6. Audit completion
        self.auditor.log_completion(document.id)
        
        return final
```

## Cost-Benefit Analysis

| Approach | Monthly Cost | Compliance Risk | Implementation Time |
|----------|-------------|-----------------|-------------------|
| AWS with BAA | $3,000 | Medium | 1 month |
| Full de-identification | $1,000 | Low | 2 months |
| Hybrid approach | $1,500 | Low | 1.5 months |
| Self-hosted only | $5,000 | Lowest | 3 months |

## Recommendations

### For Enfermera Elena:

1. **Use De-identification Pipeline** ✅
   - Safer legally
   - Cheaper (no BAA pricing)
   - More flexible (any translation service)

2. **Mexican PHI Patterns** ✅
   - Build specific detectors for CURP, RFC, NSS
   - These don't exist in standard tools

3. **Hybrid Detection** ✅
   - Rules for Mexican identifiers
   - ML for names and addresses

4. **Format-Preserving Tokens** ✅
   - Maintains context for better translation
   - "[DATE]" vs "[FECHA]" helps translation

5. **Audit Everything** ✅
   - Log what PHI was found/removed
   - Never log actual PHI values
   - Track all transformations

## Compliance Checklist

- [ ] PHI detection includes Mexican identifiers (CURP, RFC, NSS)
- [ ] De-identification validated on sample documents
- [ ] No raw PHI sent to external services
- [ ] Token mapping stored securely
- [ ] Re-identification process tested
- [ ] Audit logs capture all operations
- [ ] Date format conversion (DD/MM → MM/DD)
- [ ] Manual review process for low confidence
- [ ] Compliance officer sign-off

---

*Document Status: De-identification strategy defined*  
*Compliance Review: Required before implementation*  
*Next Step: Test with sample IMSS documents*