#!/bin/bash
# Ready-to-run translation script for Enfermera Elena
# Now with 375,000+ UMLS medical terms!

echo "========================================="
echo "Enfermera Elena - Medical PDF Translation"
echo "With UMLS Full Release (375,000+ terms)"
echo "========================================="

# Configuration
PDF_INPUT="${1:-}"
OUTPUT_DIR="./output"
GLOSSARY="data/glossaries/glossary_es_en_production.csv"

# Check if PDF provided
if [ -z "$PDF_INPUT" ]; then
    echo "Usage: ./run_translation.sh <path-to-pdf>"
    echo ""
    echo "Example:"
    echo "  ./run_translation.sh /path/to/your/87page-medical-record.pdf"
    echo ""
    echo "Options:"
    echo "  Add --sample to process only first 5 pages"
    echo "  Add --validate to check glossary coverage"
    exit 1
fi

# Check if PDF exists
if [ ! -f "$PDF_INPUT" ]; then
    echo "❌ Error: PDF file not found: $PDF_INPUT"
    exit 1
fi

echo "📄 Input PDF: $PDF_INPUT"
echo "📚 UMLS Glossary: 375,424 medical terms loaded"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check for --sample flag
SAMPLE_FLAG=""
if [[ "$2" == "--sample" ]]; then
    SAMPLE_FLAG="--sample"
    echo "⚡ SAMPLE MODE: Processing only first 5 pages"
    echo ""
fi

# Check for --validate flag
if [[ "$2" == "--validate" ]]; then
    echo "🔍 Validating glossary coverage..."
    python3 process_medical_pdf.py "$PDF_INPUT" --validate --glossary "$GLOSSARY"
    exit 0
fi

# Check if LibreTranslate is running
echo "🔤 Checking translation backend..."
if curl -s http://localhost:5000/languages > /dev/null 2>&1; then
    echo "✅ LibreTranslate is running"
    BACKEND="libretranslate"
else
    echo "⚠️  LibreTranslate not detected"
    echo ""
    echo "Starting LibreTranslate with Docker..."
    docker run -d -p 5000:5000 --name libretranslate \
        libretranslate/libretranslate --load-only es,en
    
    echo "Waiting for LibreTranslate to start..."
    sleep 10
    
    if curl -s http://localhost:5000/languages > /dev/null 2>&1; then
        echo "✅ LibreTranslate started successfully"
        BACKEND="libretranslate"
    else
        echo "❌ Could not start LibreTranslate"
        echo "Please start it manually with:"
        echo "  docker run -d -p 5000:5000 libretranslate/libretranslate --load-only es,en"
        exit 1
    fi
fi

echo ""
echo "🚀 Starting translation pipeline..."
echo "-----------------------------------------"

# Get PDF filename without path
PDF_NAME=$(basename "$PDF_INPUT" .pdf)
OUTPUT_PDF="$OUTPUT_DIR/${PDF_NAME}_translated.pdf"

# Run the translation pipeline
python3 process_medical_pdf.py \
    "$PDF_INPUT" \
    --output "$OUTPUT_PDF" \
    --glossary "$GLOSSARY" \
    --backend "$BACKEND" \
    $SAMPLE_FLAG

# Check if successful
if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "✅ Translation Complete!"
    echo "========================================="
    echo "📥 Input: $PDF_INPUT"
    echo "📤 Output: $OUTPUT_PDF"
    echo ""
    echo "Open the translated PDF with:"
    echo "  xdg-open $OUTPUT_PDF"
    echo "  or"
    echo "  firefox $OUTPUT_PDF"
else
    echo ""
    echo "❌ Translation failed. Check the error messages above."
    exit 1
fi