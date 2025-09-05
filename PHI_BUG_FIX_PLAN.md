# PHI Detection & Restoration Bug Fix Plan

## Root Cause Analysis

### 1. Sanitization Bug (Address Not Removed)
**Issue**: "CAMINO A ALCOCER NO. 12 Col..." not being detected
**Cause**: Regex pattern expects street name immediately after "CAMINO" but gets "CAMINO A"
**Current Pattern**: `(?:CAMINO)\s+([^,\n]{5,50})`
**Problem**: Doesn't account for prepositions like "A", "DE", "DEL"

### 2. Restoration Bug (Text Corruption)
**Issue**: "First diff at position 333: 'C' vs '3'"
**Cause**: Index corruption during multi-pass replacement
**Problems**:
- Overlapping matches not properly handled
- Placeholder length differs from original text
- Multiple replacement passes corrupt indices

## Solution Architecture

### Phase 1: Fix Restoration Algorithm (CRITICAL)
```python
# New single-pass algorithm
def sanitize_and_restore(text):
    1. Detect all PHI with exact positions
    2. Resolve overlaps keeping highest confidence
    3. Sort by position (no reversal needed)
    4. Build new text in single pass:
       - Track current position
       - Copy unchanged segments
       - Insert placeholders
       - Store mapping with original text
    5. Restore using stored original segments
```

### Phase 2: Fix Address Detection
```python
# Enhanced address pattern
address_pattern = re.compile(
    r'(?:CALLE|AV\.?|AVENIDA|CAMINO|CARRETERA|CALZADA)'
    r'(?:\s+(?:A|DE|DEL|LA|LAS|LOS))?' # Optional prepositions
    r'\s+([^,\n]{3,50})'  # Address content
    r'(?:.*?(?:COL\.?|COLONIA)[^,\n]+)?'  # Optional colony
    r'(?:.*?C\.?P\.?\s*\d{5})?'  # Optional ZIP
)
```

### Phase 3: Context-Aware Detection
```python
# Distinguish facility vs patient addresses
def classify_address(address, context):
    # Hospital addresses (keep):
    - In document header
    - Contains "HOSPITAL", "CLÍNICA", "CENTRO MÉDICO"
    - Before patient information section
    
    # Patient addresses (remove):
    - After "PACIENTE:", "DOMICILIO:", "DIRECCIÓN:"
    - In patient information section
    - Associated with personal data
```

## Test Strategy

### 1. Unit Test Suite
```python
test_cases = {
    "mexican_address": "CAMINO A ALCOCER NO. 12 Col. CENTRO",
    "patient_name": "Juan Carlos Hernández García",
    "curp": "HEGJ450315HGTRRN09",
    "nss": "12345678901",
    "dates": ["12/03/2025", "15 de marzo de 2025"],
    "phone": "+52 415 123 4567",
    "email": "paciente@ejemplo.com"
}
```

### 2. Integration Tests
- Test with redacted 8-page document
- Verify no data corruption
- Ensure all PHI types detected
- Validate perfect restoration

### 3. Validation Metrics
- Sanitization: 0 PHI remaining (except placeholders)
- Restoration: 100% byte-perfect match
- Performance: <1 second for 8 pages
- No false positives on facility info

## Implementation Steps

### Day 1: Core Fixes
1. ✅ Rewrite sanitization with single-pass algorithm
2. ✅ Fix address regex patterns
3. ✅ Add comprehensive unit tests
4. ✅ Validate with 8-page sample

### Day 2: Enhancements
1. Add context-aware detection
2. Implement facility vs patient classification
3. Create test document with all PHI types
4. Performance optimization

### Day 3: Production Readiness
1. Full integration testing
2. Audit log validation
3. Documentation update
4. Final validation before 87-page test

## Success Criteria

### Must Have (Before Production)
- ✅ Zero data corruption in restoration
- ✅ All address patterns detected
- ✅ 100% unit test pass rate
- ✅ Audit log complete and accurate

### Nice to Have
- Context-aware facility detection
- Performance <0.5s for 8 pages
- Confidence scoring refinement
- Multi-language support

## Risk Mitigation

### High Risk Items
1. **Data Corruption**: Test restoration on every change
2. **PHI Leakage**: Validate all patterns with test data
3. **Performance**: Profile if >1s for 8 pages

### Contingency Plans
- Keep original PHI detector as backup
- Manual review for first 87-page document
- Incremental rollout with monitoring

## Code Quality Checklist
- [ ] All functions have docstrings
- [ ] Unit tests for each regex pattern
- [ ] Integration tests for full pipeline
- [ ] Performance benchmarks documented
- [ ] Audit logging tested
- [ ] Error handling comprehensive
- [ ] Code review completed

## Timeline
- **Today**: Fix critical bugs (restoration + address)
- **Tomorrow**: Add tests and validation
- **Day 3**: Production readiness
- **Day 4**: Process 87-page document (if all tests pass)

---
*Critical: Do not process 87-page document until restoration bug is fixed*