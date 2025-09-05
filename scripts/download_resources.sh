#!/bin/bash
# Download Medical Resources for Enfermera Elena
# Run this after UMLS license is approved

set -e

echo "================================================"
echo "Enfermera Elena - Medical Resources Downloader"
echo "================================================"

# Create data directories
echo "Creating data directories..."
mkdir -p ../data/{umls,cofepris,imss,models,glossaries}

# Check if UMLS API key is set
if [ -z "$UMLS_API_KEY" ]; then
    echo "⚠️  UMLS_API_KEY environment variable not set"
    echo "   Set it after receiving your UMLS license:"
    echo "   export UMLS_API_KEY='your-api-key-here'"
    echo ""
fi

# Download COFEPRIS drug database (publicly available)
echo ""
echo "📥 Downloading COFEPRIS drug database..."
if [ ! -f "../data/cofepris/medicamentos.csv" ]; then
    # Note: Update this URL with the actual COFEPRIS data URL
    echo "   Visit: https://www.gob.mx/cofepris/documentos/datos-abiertos-cofepris"
    echo "   Download the medications CSV to: ../data/cofepris/medicamentos.csv"
else
    echo "   ✅ COFEPRIS data already downloaded"
fi

# Download IMSS Cuadro Básico
echo ""
echo "📥 Downloading IMSS Cuadro Básico..."
if [ ! -f "../data/imss/cuadro_basico.pdf" ]; then
    echo "   Visit: http://www.imss.gob.mx/profesionales-salud/cuadro-basico"
    echo "   Download the PDF to: ../data/imss/cuadro_basico.pdf"
else
    echo "   ✅ IMSS Cuadro Básico already downloaded"
fi

# Create Python virtual environment for model downloads
echo ""
echo "🐍 Setting up Python environment..."
if [ ! -d "../venv" ]; then
    python3 -m venv ../venv
    source ../venv/bin/activate
    pip install --upgrade pip
    pip install transformers torch datasets
else
    source ../venv/bin/activate
    echo "   ✅ Virtual environment already exists"
fi

# Download Spanish medical models from HuggingFace
echo ""
echo "🤖 Downloading Spanish medical models..."

cat << 'EOF' > download_models.py
#!/usr/bin/env python3
import os
from pathlib import Path
from transformers import AutoTokenizer, AutoModel

models_dir = Path("../data/models")
models_dir.mkdir(parents=True, exist_ok=True)

models_to_download = [
    ("dccuchile/bert-base-spanish-wwm-cased", "BETO"),
    ("PlanTL-GOB-ES/roberta-base-biomedical-clinical-es", "RoBERTa-biomedical-clinical"),
    ("PlanTL-GOB-ES/bsc-bio-ehr-spanish", "BSC-bio-ehr"),
    ("mrm8488/bert-base-spanish-wwm-cased-finetuned-ner", "BERT-NER-Spanish")
]

for model_name, friendly_name in models_to_download:
    save_path = models_dir / friendly_name
    
    if save_path.exists():
        print(f"   ✅ {friendly_name} already downloaded")
    else:
        print(f"   📥 Downloading {friendly_name}...")
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModel.from_pretrained(model_name)
            
            tokenizer.save_pretrained(save_path)
            model.save_pretrained(save_path)
            
            print(f"   ✅ {friendly_name} downloaded to {save_path}")
        except Exception as e:
            print(f"   ❌ Failed to download {friendly_name}: {e}")

print("\nModel download complete!")
EOF

python download_models.py
rm download_models.py

# Create sample configuration files
echo ""
echo "📝 Creating sample configuration files..."

# Create API keys template
cat << 'EOF' > ../config/.env.template
# Enfermera Elena Configuration Template
# Copy to .env and fill in your actual values

# UMLS API Configuration
UMLS_API_KEY=your-umls-api-key-here

# Translation API (choose one)
# Google Cloud Translation
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# AWS Translate
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Database Configuration
DB_HOST=localhost
DB_NAME=enfermera_elena
DB_USER=psadmin
DB_PASSWORD=

# Application Settings
ENV=development
DEBUG=true
LOG_LEVEL=INFO
USE_GPU=false
EOF

echo "   ✅ Configuration template created at ../config/.env.template"

# Create README for data directory
cat << 'EOF' > ../data/README.md
# Enfermera Elena - Data Directory

## Structure
```
data/
├── umls/          # UMLS Metathesaurus files (after license approval)
├── cofepris/      # Mexican drug database
├── imss/          # IMSS terminology and guidelines
├── models/        # Pre-trained neural models
└── glossaries/    # Generated translation glossaries
```

## Setup Instructions

### 1. UMLS Data (Requires License)
After your UMLS license is approved (3 business days):
1. Download UMLS Metathesaurus from https://www.nlm.nih.gov/research/umls/
2. Extract MRCONSO.RRF, MRREL.RRF, MRSTY.RRF to `umls/` folder
3. Run: `python ../scripts/prepare_umls_data.py`

### 2. COFEPRIS Data (Public)
1. Visit https://www.gob.mx/cofepris/documentos/datos-abiertos-cofepris
2. Download medications CSV to `cofepris/medicamentos.csv`

### 3. IMSS Resources (Public)
1. Visit http://www.imss.gob.mx/profesionales-salud/cuadro-basico
2. Download Cuadro Básico PDF to `imss/cuadro_basico.pdf`

### 4. Neural Models (Automated)
Models are automatically downloaded by the setup script to `models/`

## Data Sources Status

| Source | License Required | Status | Action |
|--------|-----------------|--------|---------|
| UMLS | Yes (3 days) | ⏳ Pending | Wait for approval |
| COFEPRIS | No | 📥 Ready | Manual download |
| IMSS | No | 📥 Ready | Manual download |
| HuggingFace | No | ✅ Downloaded | Automated |

## Notes
- Keep sensitive data (especially UMLS) secure and don't commit to git
- Add `data/` to `.gitignore` except for README and samples
- Ensure sufficient disk space (~10GB for full UMLS)
EOF

echo "   ✅ Data README created"

# Summary
echo ""
echo "================================================"
echo "✅ Resource download script completed!"
echo "================================================"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. ⏳ Wait for UMLS license approval (3 business days)"
echo "   Then download UMLS Metathesaurus and extract to data/umls/"
echo ""
echo "2. 📥 Download COFEPRIS data manually:"
echo "   https://www.gob.mx/cofepris/documentos/datos-abiertos-cofepris"
echo ""
echo "3. 📥 Download IMSS Cuadro Básico:"
echo "   http://www.imss.gob.mx/profesionales-salud/cuadro-basico"
echo ""
echo "4. 🔧 Configure environment:"
echo "   cp ../config/.env.template ../config/.env"
echo "   Edit .env with your API keys"
echo ""
echo "5. 🚀 After UMLS approval, run:"
echo "   python ../scripts/prepare_umls_data.py"
echo ""
echo "================================================"