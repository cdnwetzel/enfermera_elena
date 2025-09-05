# OCR Strategy for Mixed Mexican Medical PDFs
## Handling Multi-Source 87-Page Documents

### Version 1.0 | Date: 2025-09-05

---

## Document Analysis: 87-Page Mexican Medical Record

### Document Composition
Based on your sample, Mexican medical records are complex multi-source documents:

```yaml
Document Types in Single PDF:
  1. Native Digital PDFs (15-20%):
     - Direct from hospital systems
     - Searchable text
     - Clean formatting
     
  2. Printed → Scanned PDFs (40-50%):
     - Computer-printed documents
     - Later scanned to PDF
     - OCR needed but high accuracy
     
  3. Forms with Printed Text (20-30%):
     - Pre-printed forms (IMSS/ISSSTE templates)
     - Computer printing added on form
     - Mixed quality
     
  4. Handwritten on Forms (10-15%): [SKIP]
     - Manual writing on printed forms
     - Doctor notes, signatures
     - Not processing initially
     
  5. Stamps & Signatures (5-10%): [SKIP]
     - Official seals
     - Authorization stamps
     - Not needed for translation
```

## OCR Processing Pipeline

### Phase 1: PDF Analysis & Segmentation

```python
class MexicalMedicalPDFProcessor:
    """
    Intelligent PDF processor that handles mixed content types
    """
    
    def analyze_pdf(self, pdf_path):
        """
        Determine processing strategy per page
        """
        pdf_analysis = {
            'total_pages': 87,
            'pages_with_text': [],      # Native digital text
            'pages_need_ocr': [],        # Scanned pages
            'pages_with_forms': [],      # IMSS/ISSSTE forms
            'pages_skip': []             # Handwritten/stamps only
        }
        
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            # Check if page has extractable text
            text = page.get_text()
            
            if len(text.strip()) > 50:
                # Native digital PDF with text
                pdf_analysis['pages_with_text'].append(page_num)
            else:
                # Needs OCR
                if self.is_printed_text(page):
                    pdf_analysis['pages_need_ocr'].append(page_num)
                elif self.is_form_with_printed(page):
                    pdf_analysis['pages_with_forms'].append(page_num)
                else:
                    # Handwritten or stamps only - skip
                    pdf_analysis['pages_skip'].append(page_num)
        
        return pdf_analysis
    
    def is_printed_text(self, page):
        """
        Detect if page contains printed (not handwritten) text
        """
        # Convert to image
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Use edge detection to identify printed text characteristics
        # Printed text has uniform edges vs handwriting
        edges = cv2.Canny(np.array(img), 50, 150)
        
        # Calculate uniformity metrics
        horizontal_lines = self.detect_horizontal_lines(edges)
        vertical_alignment = self.detect_vertical_alignment(edges)
        
        return horizontal_lines > 0.7 and vertical_alignment > 0.6
```

### Phase 2: Selective OCR Processing

```python
class SelectiveOCR:
    """
    Apply OCR only to printed text, skip handwriting
    """
    
    def __init__(self):
        # Multiple OCR engines for best results
        self.engines = {
            'primary': 'AWS Textract',      # Best for forms
            'secondary': 'Tesseract',       # Backup
            'forms': 'Azure Form Recognizer' # IMSS forms
        }
    
    def process_page(self, page_image, page_type):
        """
        Process based on page type
        """
        if page_type == 'native_text':
            # Already have text, just extract
            return self.extract_native_text(page_image)
            
        elif page_type == 'printed_scan':
            # High-quality OCR for printed text
            return self.ocr_printed_text(page_image)
            
        elif page_type == 'form_printed':
            # Form-aware OCR
            return self.ocr_form_printed(page_image)
            
        else:  # handwritten, stamps
            return None  # Skip
    
    def ocr_printed_text(self, image):
        """
        OCR for computer-printed text only
        """
        # Pre-processing for printed text
        processed = self.preprocess_printed(image)
        
        # Use AWS Textract for printed documents
        response = textract.detect_document_text(
            Document={'Bytes': processed}
        )
        
        # Filter out low-confidence results (likely handwriting)
        text_blocks = []
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                if block['Confidence'] > 85:  # High confidence = printed
                    text_blocks.append(block['Text'])
        
        return '\n'.join(text_blocks)
    
    def preprocess_printed(self, image):
        """
        Optimize image for printed text OCR
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Denoise (printed text doesn't need heavy denoising)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # Adaptive thresholding for printed text
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Deskew if needed (printed docs often scanned crooked)
        deskewed = self.deskew(binary)
        
        return deskewed
```

### Phase 3: IMSS/ISSSTE Form Recognition

```python
class MexicanMedicalFormProcessor:
    """
    Special handling for Mexican healthcare forms
    """
    
    def __init__(self):
        self.form_templates = {
            'IMSS-01': 'Historia Clínica',
            'IMSS-02': 'Nota de Evolución',
            'IMSS-03': 'Receta Médica',
            'ISSSTE-01': 'Expediente Clínico',
            'SP-01': 'Seguro Popular - Consulta'
        }
    
    def identify_form(self, image):
        """
        Identify which IMSS/ISSSTE form template
        """
        # Look for form identifiers (usually top-right)
        header_region = image[0:200, -400:]  # Top-right corner
        
        # OCR just the header
        header_text = pytesseract.image_to_string(
            header_region,
            lang='spa'
        )
        
        # Match against known forms
        for form_id, form_name in self.form_templates.items():
            if form_id in header_text or form_name in header_text:
                return form_id
        
        return 'UNKNOWN'
    
    def extract_form_fields(self, image, form_id):
        """
        Extract only printed text from form fields
        """
        if form_id == 'IMSS-03':  # Prescription form
            fields = {
                'patient_name': (100, 200, 500, 250),  # x1,y1,x2,y2
                'nss': (100, 250, 300, 300),
                'diagnosis': (100, 400, 700, 500),
                'medications': (100, 550, 700, 800),
                'date': (500, 200, 650, 250)
            }
        # ... other form templates
        
        extracted_data = {}
        for field_name, coords in fields.items():
            x1, y1, x2, y2 = coords
            field_image = image[y1:y2, x1:x2]
            
            # OCR only if printed text detected
            if self.has_printed_text(field_image):
                text = self.ocr_field(field_image)
                extracted_data[field_name] = text
        
        return extracted_data
```

### Phase 4: Quality Control & Validation

```python
class OCRQualityControl:
    """
    Ensure we're only processing printed text
    """
    
    def validate_ocr_output(self, text, confidence_scores):
        """
        Filter out likely handwriting/noise
        """
        validated_lines = []
        
        for line, confidence in zip(text.split('\n'), confidence_scores):
            # Printed text characteristics
            if self.is_likely_printed(line, confidence):
                validated_lines.append(line)
        
        return '\n'.join(validated_lines)
    
    def is_likely_printed(self, text, confidence):
        """
        Heuristics to identify printed vs handwritten
        """
        indicators = {
            'high_confidence': confidence > 85,
            'consistent_case': not text.isupper() or not text.islower(),
            'no_cursive_patterns': not self.has_cursive_patterns(text),
            'standard_formatting': bool(re.match(r'[\w\s,.\-:;()]+', text)),
            'medical_terms': self.contains_medical_terms(text)
        }
        
        # Printed if most indicators are true
        return sum(indicators.values()) >= 3
```

## Implementation Strategy for 87-Page Document

### Processing Flow

```python
def process_mexican_medical_pdf(pdf_path):
    """
    Complete pipeline for 87-page medical record
    """
    
    # Step 1: Analyze PDF structure
    processor = MexicalMedicalPDFProcessor()
    analysis = processor.analyze_pdf(pdf_path)
    
    print(f"Processing {analysis['total_pages']} pages:")
    print(f"  - Native text: {len(analysis['pages_with_text'])} pages")
    print(f"  - Need OCR: {len(analysis['pages_need_ocr'])} pages")
    print(f"  - Forms: {len(analysis['pages_with_forms'])} pages")
    print(f"  - Skipping: {len(analysis['pages_skip'])} pages")
    
    # Step 2: Extract text from each page type
    extracted_text = []
    
    for page_num in range(analysis['total_pages']):
        if page_num in analysis['pages_with_text']:
            # Direct text extraction
            text = extract_native_text(pdf_path, page_num)
            
        elif page_num in analysis['pages_need_ocr']:
            # OCR for printed text only
            text = ocr_printed_only(pdf_path, page_num)
            
        elif page_num in analysis['pages_with_forms']:
            # Form-specific OCR
            text = process_medical_form(pdf_path, page_num)
            
        else:
            # Skip handwritten/stamps
            text = None
        
        if text:
            extracted_text.append({
                'page': page_num + 1,
                'text': text,
                'type': get_page_type(analysis, page_num)
            })
    
    # Step 3: Combine and structure
    document = structure_medical_document(extracted_text)
    
    return document
```

### Expected Output Structure

```json
{
  "document_info": {
    "total_pages": 87,
    "processed_pages": 72,
    "skipped_pages": 15,
    "extraction_method": "mixed"
  },
  "sections": [
    {
      "type": "patient_info",
      "source": "IMSS form",
      "data": {
        "name": "[REDACTED]",
        "nss": "[REDACTED]",
        "curp": "[REDACTED]"
      }
    },
    {
      "type": "clinical_history",
      "source": "printed_text",
      "text": "Paciente con antecedentes de diabetes mellitus tipo 2..."
    },
    {
      "type": "prescriptions",
      "source": "form_ocr",
      "medications": [
        "Metformina 850mg c/12hrs",
        "Glibenclamida 5mg c/24hrs"
      ]
    }
  ],
  "quality_metrics": {
    "avg_confidence": 92.3,
    "form_recognition_rate": 0.95,
    "printed_text_coverage": 0.85
  }
}
```

## Technology Stack for OCR

### Recommended Tools

```yaml
Primary OCR:
  AWS Textract:
    - Best for: Forms, tables, printed text
    - Cost: $1.50 per 1000 pages
    - Accuracy: 95%+ on printed text
    - Skip: Handwriting detection available

Secondary OCR:
  Tesseract 5.x:
    - Best for: Backup, simple printed text
    - Cost: Free
    - Accuracy: 90% on clean printed text
    - Configuration: Spanish language pack

Form Processing:
  Azure Form Recognizer:
    - Best for: IMSS/ISSSTE forms
    - Cost: $1.50 per 1000 pages
    - Custom models: Can train on IMSS templates

PDF Handling:
  PyMuPDF (fitz):
    - Text extraction from native PDFs
    - Page rendering for OCR
    - Metadata extraction

Image Processing:
  OpenCV:
    - Preprocessing for OCR
    - Printed vs handwritten detection
    - Deskewing and denoising
```

### Performance Optimizations

```python
class BatchOCRProcessor:
    """
    Optimize for 87-page documents
    """
    
    def __init__(self):
        self.batch_size = 10  # Process 10 pages at once
        self.use_gpu = True
        self.cache_templates = True
    
    def process_batch(self, pdf_path):
        """
        Batch processing for efficiency
        """
        # Split 87 pages into batches
        batches = self.create_batches(pdf_path, self.batch_size)
        
        # Parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for batch in batches:
                future = executor.submit(self.process_batch_pages, batch)
                futures.append(future)
            
            # Collect results
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())
        
        return results
```

## Cost Analysis for 87-Page Documents

```yaml
Per Document (87 pages):
  AWS Textract:
    - Cost: $0.13 (87 pages × $1.50/1000)
    - Processing time: ~45 seconds
    
  Azure Form Recognizer:
    - Cost: $0.13 (for form pages only)
    - Processing time: ~30 seconds
    
  Total per document: ~$0.26
  
Monthly Volume (1000 documents):
  - OCR costs: $260
  - Translation costs: $150 (after text extraction)
  - Total: $410/month

Annual projection:
  - 12,000 documents: $4,920
  - Vs manual transcription: $120,000
  - Savings: 96%
```

## Quality Metrics

### Success Criteria
```yaml
Printed Text Extraction:
  - Accuracy: >95% for computer-printed text
  - Coverage: >85% of printed content extracted
  - False positives: <5% handwriting mistaken for print

Form Recognition:
  - IMSS form identification: >95%
  - Field extraction accuracy: >90%
  - Medication name accuracy: >98%

Performance:
  - 87-page document: <2 minutes total
  - Cost per page: <$0.003
  - Parallel processing: 4-10 pages simultaneously
```

## Implementation Phases

### Phase 1: Basic OCR (Week 1)
- Set up AWS Textract
- Implement PDF splitter
- Extract native digital text
- Basic printed text OCR

### Phase 2: Intelligent Processing (Week 2)
- Implement printed vs handwritten detection
- Add confidence filtering
- Skip handwritten sections
- Optimize preprocessing

### Phase 3: Form Recognition (Week 3)
- IMSS/ISSSTE template matching
- Field-level extraction
- Medication list parsing
- Date/number formatting

### Phase 4: Production Pipeline (Week 4)
- Batch processing
- Error handling
- Quality validation
- Performance optimization

## Sample Code for 87-Page Document

```python
# Complete processing example
if __name__ == "__main__":
    # Your 87-page medical record
    pdf_file = "/path/to/mexican_medical_record.pdf"
    
    # Initialize processor
    processor = MexicalMedicalPDFProcessor()
    
    # Process document
    print("Starting OCR for 87-page document...")
    result = processor.process_pdf(
        pdf_file,
        skip_handwriting=True,
        skip_stamps=True,
        extract_forms=True,
        languages=['spa', 'eng']
    )
    
    # Summary
    print(f"\nProcessing complete:")
    print(f"  Pages processed: {result['processed_pages']}/87")
    print(f"  Text extracted: {len(result['text'])} characters")
    print(f"  Forms identified: {result['forms_found']}")
    print(f"  Medications found: {len(result['medications'])}")
    print(f"  Processing time: {result['time_seconds']} seconds")
    print(f"  Estimated cost: ${result['cost_estimate']:.2f}")
    
    # Save for translation
    with open('extracted_text.json', 'w') as f:
        json.dump(result, f, indent=2)
```

---

*Document Status: OCR Strategy Defined*  
*Next Step: Test with actual IMSS documents*  
*Focus: Printed text only, skip handwriting/stamps*