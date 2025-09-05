# Enfermera Elena - Usage Guide

## Quick Start

### Single File Processing
```bash
# Activate virtual environment
source venv/bin/activate

# Process a single medical record
python3 process_medical_records.py medical_records/original/your_file.pdf
```

### Batch Processing

#### Sequential Mode (Default)
Processes each document completely before moving to the next:
```bash
# Process all PDFs in a directory
python3 process_medical_records.py medical_records/original/*.pdf

# Or specify directory
python3 process_medical_records.py medical_records/original/
```

#### Batch Mode
Processes in phases (extract all → translate all → analyze all):
```bash
python3 process_medical_records.py medical_records/original/*.pdf --mode batch
```

### Verbose Output
See detailed progress:
```bash
python3 process_medical_records.py medical_records/original/*.pdf --verbose
```

## Directory Structure

```
medical_records/
├── original/     # Place PDF files here
├── extracted/    # Text extraction output
├── translated/   # Translation output
└── quality/      # Quality analysis reports
```

## Processing Pipeline

1. **Extract**: PDF → Text using `pdftotext`
2. **Translate**: Spanish → English using UMLS glossary
3. **Analyze**: Generate quality scores and review documents

## Command Options

```bash
python3 process_medical_records.py [OPTIONS] INPUT_FILES

Arguments:
  INPUT_FILES    One or more PDF files or directories

Options:
  --mode         Processing mode: 'sequential' or 'batch'
  --verbose, -v  Show detailed progress
  --help, -h     Show help message
```

## Examples

### Process Single Document
```bash
python3 process_medical_records.py medical_records/original/mr_12_03_25_MACSMA_redacted.pdf
```
Output:
- `medical_records/extracted/mr_12_03_25_MACSMA_redacted_extracted.txt`
- `medical_records/translated/mr_12_03_25_MACSMA_redacted_translated.txt`
- `medical_records/quality/mr_12_03_25_MACSMA_redacted_quality.json`

### Process Multiple Documents
```bash
# Process all PDFs in original folder
python3 process_medical_records.py medical_records/original/

# Process specific files
python3 process_medical_records.py file1.pdf file2.pdf file3.pdf

# Mix files and directories
python3 process_medical_records.py file1.pdf /path/to/pdfs/
```

### Batch Processing Modes

**Sequential (Default)**: Complete each file before starting next
```bash
python3 process_medical_records.py medical_records/original/*.pdf
```
Flow: File1(extract→translate→analyze) → File2(extract→translate→analyze) → ...

**Batch**: Process all files in phases
```bash
python3 process_medical_records.py medical_records/original/*.pdf --mode batch
```
Flow: All(extract) → All(translate) → All(analyze)

## Quality Scores

Each processed document gets a quality score (0-100%):
- **≥80%**: High confidence, minimal review needed
- **50-79%**: Medium confidence, selective review recommended
- **<50%**: Low confidence, thorough review required

Review files in `medical_records/quality/`:
- `*_quality.json`: Machine-readable quality metrics
- `batch_summary.json`: Overall batch processing results

## Individual Script Usage

### Extract Only
```bash
pdftotext -layout medical_records/original/file.pdf medical_records/extracted/file_extracted.txt
```

### Translate Only
```bash
python3 translate_medical_record.py
```

### Quality Analysis Only
```bash
python3 translation_quality_analyzer.py
```

## Troubleshooting

### Missing Dependencies
If pip is not available:
```bash
# Ask administrator to install
sudo dnf install python3-pip

# Then install dependencies
pip install -r requirements.txt
```

### PDF Extraction Issues
Ensure `pdftotext` is installed:
```bash
# Check if installed
which pdftotext

# If missing, install poppler-utils
sudo dnf install poppler-utils
```

### Low Quality Scores
Common causes:
- Medical terms not in glossary (4.8% coverage currently)
- Mixed Spanish-English in output
- Partial translations (e.g., "OXIGENO POR Day")

## Performance

- **UMLS Glossary**: 375,448 Spanish→English terms
- **Processing Speed**: ~30 seconds per 8-page document
- **Quality Analysis**: ~2 seconds per document

## Tips

1. **Organize PDFs**: Keep related documents in subdirectories
2. **Review Low Scores**: Check files with <70% confidence manually
3. **Use Verbose Mode**: For debugging or monitoring progress
4. **Batch Large Sets**: Use `--mode batch` for 10+ files

---
*For setup instructions, see SETUP_AND_RUN.md*
*For development details, see CURRENT_STATE_CHECKPOINT.md*