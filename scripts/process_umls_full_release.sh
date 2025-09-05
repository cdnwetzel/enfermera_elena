#!/bin/bash
# UMLS Full Release Processing Script for Enfermera Elena
# Optimized for Mexican Spanish medical translation

set -e

echo "========================================="
echo "UMLS Full Release Processing"
echo "Mexican Spanish → English Medical Glossary"
echo "========================================="

# Configuration
UMLS_DIR="${1:-/home/psadmin/ai/enfermera_elena/data/umls}"
DB_NAME="${2:-enfermera_elena}"
DB_USER="${3:-psadmin}"
OUTPUT_DIR="/home/psadmin/ai/enfermera_elena/data/glossaries"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check prerequisites
check_requirements() {
    echo -e "${YELLOW}Checking requirements...${NC}"
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        echo -e "${RED}PostgreSQL not found. Installing...${NC}"
        sudo apt-get update && sudo apt-get install -y postgresql postgresql-contrib
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 not found.${NC}"
        exit 1
    fi
    
    # Check UMLS files
    if [ ! -f "$UMLS_DIR/MRCONSO.RRF" ]; then
        echo -e "${RED}MRCONSO.RRF not found in $UMLS_DIR${NC}"
        echo "Please download UMLS Full Release and extract to $UMLS_DIR"
        echo "Visit: https://www.nlm.nih.gov/research/umls/"
        exit 1
    fi
    
    echo -e "${GREEN}All requirements met.${NC}"
}

# Create database and user
setup_database() {
    echo -e "${YELLOW}Setting up PostgreSQL database...${NC}"
    
    # Create database if it doesn't exist
    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    sudo -u postgres createdb $DB_NAME
    
    # Grant privileges
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true
    
    echo -e "${GREEN}Database $DB_NAME ready.${NC}"
}

# Create optimized tables for Mexican Spanish
create_tables() {
    echo -e "${YELLOW}Creating optimized tables...${NC}"
    
    psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Drop existing tables if needed
DROP TABLE IF EXISTS mrconso CASCADE;
DROP TABLE IF EXISTS glossary_es_en CASCADE;
DROP TABLE IF EXISTS mexican_priority CASCADE;

-- MRCONSO table with only needed columns for performance
CREATE TABLE mrconso (
    CUI VARCHAR(10) NOT NULL,      -- Concept Unique Identifier
    LAT VARCHAR(3) NOT NULL,        -- Language
    TS VARCHAR(1),                  -- Term Status
    LUI VARCHAR(10),                -- Lexical Unique Identifier
    STT VARCHAR(3),                 -- String Type
    SUI VARCHAR(10),                -- String Unique Identifier
    ISPREF VARCHAR(1),              -- Preferred flag
    AUI VARCHAR(9),                 -- Atom Unique Identifier
    SAUI VARCHAR(50),               -- Source Atom Unique Identifier
    SCUI VARCHAR(100),              -- Source Concept Unique Identifier
    SDUI VARCHAR(100),              -- Source Descriptor Unique Identifier
    SAB VARCHAR(40) NOT NULL,       -- Source Abbreviation
    TTY VARCHAR(40) NOT NULL,       -- Term Type
    CODE VARCHAR(100),              -- Source-specific code
    STR TEXT NOT NULL,              -- String/Term text
    SRL VARCHAR(10),                -- Source Restriction Level
    SUPPRESS VARCHAR(1),            -- Suppression flag
    CVF VARCHAR(50)                 -- Content View Flag
);

-- Indexes for Mexican Spanish optimization
CREATE INDEX idx_mrconso_cui ON mrconso(CUI);
CREATE INDEX idx_mrconso_lat ON mrconso(LAT);
CREATE INDEX idx_mrconso_tty ON mrconso(TTY);
CREATE INDEX idx_mrconso_sab ON mrconso(SAB);
CREATE INDEX idx_mrconso_str_lower ON mrconso(LOWER(STR));
CREATE INDEX idx_mrconso_mexican ON mrconso(SAB) WHERE SAB IN ('SNOMEDCT_MX', 'SCTSPA', 'MSHSPA', 'MDRSPA');
CREATE INDEX idx_mrconso_composite ON mrconso(LAT, TTY, SAB);

-- Glossary table with Mexican priority
CREATE TABLE glossary_es_en (
    id SERIAL PRIMARY KEY,
    es_term TEXT NOT NULL,
    es_term_normalized TEXT NOT NULL,
    en_term TEXT NOT NULL,
    cui VARCHAR(10) NOT NULL,
    source VARCHAR(40),
    priority INTEGER DEFAULT 100,
    is_mexican BOOLEAN DEFAULT FALSE,
    frequency INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(es_term_normalized, en_term, cui)
);

CREATE INDEX idx_glossary_es_term ON glossary_es_en(es_term_normalized);
CREATE INDEX idx_glossary_cui ON glossary_es_en(cui);
CREATE INDEX idx_glossary_mexican ON glossary_es_en(is_mexican) WHERE is_mexican = TRUE;

-- Mexican-specific priority table
CREATE TABLE mexican_priority (
    cui VARCHAR(10) PRIMARY KEY,
    mexican_term TEXT NOT NULL,
    english_term TEXT NOT NULL,
    source VARCHAR(40),
    notes TEXT
);

-- Statistics table
CREATE TABLE processing_stats (
    id SERIAL PRIMARY KEY,
    stage VARCHAR(50),
    count INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

GRANT ALL ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
EOF
    
    echo -e "${GREEN}Tables created successfully.${NC}"
}

# Load MRCONSO with Mexican Spanish priority
load_mrconso() {
    echo -e "${YELLOW}Loading MRCONSO.RRF (this may take several minutes)...${NC}"
    
    # Get file size for progress estimation
    FILE_SIZE=$(stat -c%s "$UMLS_DIR/MRCONSO.RRF")
    LINE_COUNT=$(wc -l < "$UMLS_DIR/MRCONSO.RRF")
    
    echo "Processing $LINE_COUNT lines from MRCONSO.RRF..."
    
    # Use COPY for efficient loading
    psql -U $DB_USER -d $DB_NAME << EOF
\copy mrconso FROM '$UMLS_DIR/MRCONSO.RRF' WITH (FORMAT csv, DELIMITER '|', NULL '', QUOTE E'\b');

-- Log statistics
INSERT INTO processing_stats (stage, count)
SELECT 'total_loaded', COUNT(*) FROM mrconso;

INSERT INTO processing_stats (stage, count)
SELECT 'spanish_terms', COUNT(*) FROM mrconso WHERE LAT='SPA';

INSERT INTO processing_stats (stage, count)
SELECT 'english_terms', COUNT(*) FROM mrconso WHERE LAT='ENG';

INSERT INTO processing_stats (stage, count)
SELECT 'mexican_snomed', COUNT(*) FROM mrconso WHERE SAB='SNOMEDCT_MX';
EOF
    
    # Show statistics
    psql -U $DB_USER -d $DB_NAME -c "
    SELECT stage, count 
    FROM processing_stats 
    ORDER BY timestamp DESC;"
    
    echo -e "${GREEN}MRCONSO loaded successfully.${NC}"
}

# Build Spanish-English glossary with Mexican priority
build_glossary() {
    echo -e "${YELLOW}Building Spanish→English glossary with Mexican priority...${NC}"
    
    psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Clear previous glossary
TRUNCATE TABLE glossary_es_en;

-- Build glossary with Mexican Spanish priority
WITH spanish_terms AS (
    -- Prioritize Mexican sources
    SELECT DISTINCT
        CUI,
        STR AS es_term,
        LOWER(TRIM(STR)) AS es_term_normalized,
        CASE 
            WHEN SAB = 'SNOMEDCT_MX' THEN 1     -- Mexican SNOMED CT (highest priority)
            WHEN SAB = 'SCTSPA' THEN 2          -- Spanish SNOMED CT
            WHEN SAB = 'MSHSPA' THEN 3          -- MeSH Spanish
            WHEN SAB = 'MDRSPA' THEN 4          -- MedDRA Spanish
            WHEN SAB LIKE '%SPA%' THEN 5        -- Other Spanish sources
            WHEN SAB = 'SNOMEDCT' AND LAT = 'SPA' THEN 6
            ELSE 10
        END AS priority,
        SAB AS source,
        CASE WHEN SAB = 'SNOMEDCT_MX' THEN TRUE ELSE FALSE END AS is_mexican
    FROM mrconso
    WHERE LAT = 'SPA' 
        AND TTY IN ('PT', 'SY', 'FN', 'MTH_PT', 'MTH_SY')  -- Include more term types
        AND (SUPPRESS IS NULL OR SUPPRESS != 'Y')
        AND LENGTH(STR) > 2  -- Skip very short terms
        AND STR NOT LIKE '%[%]%'  -- Skip bracketed annotations
),
english_preferred AS (
    -- Get best English term for each CUI
    SELECT DISTINCT ON (CUI)
        CUI,
        STR AS en_term,
        SAB
    FROM mrconso
    WHERE LAT = 'ENG'
        AND TTY IN ('PT', 'FN', 'MTH_PT')  -- Preferred terms only
        AND (SUPPRESS IS NULL OR SUPPRESS != 'Y')
        AND LENGTH(STR) > 2
    ORDER BY CUI,
        CASE WHEN ISPREF = 'Y' THEN 0 ELSE 1 END,
        CASE WHEN TTY = 'PT' THEN 0 ELSE 1 END,
        CASE WHEN SAB LIKE 'SNOMED%' THEN 0 ELSE 1 END
)
INSERT INTO glossary_es_en (es_term, es_term_normalized, en_term, cui, source, priority, is_mexican)
SELECT DISTINCT ON (s.es_term_normalized, s.CUI)
    s.es_term,
    s.es_term_normalized,
    e.en_term,
    s.CUI,
    s.source,
    s.priority,
    s.is_mexican
FROM spanish_terms s
INNER JOIN english_preferred e ON s.CUI = e.CUI
WHERE e.en_term IS NOT NULL
ORDER BY s.es_term_normalized, s.CUI, s.priority;

-- Log glossary statistics
INSERT INTO processing_stats (stage, count)
SELECT 'glossary_total', COUNT(*) FROM glossary_es_en;

INSERT INTO processing_stats (stage, count)
SELECT 'glossary_mexican', COUNT(*) FROM glossary_es_en WHERE is_mexican = TRUE;

INSERT INTO processing_stats (stage, count)
SELECT 'unique_spanish_terms', COUNT(DISTINCT es_term_normalized) FROM glossary_es_en;

INSERT INTO processing_stats (stage, count)
SELECT 'unique_concepts', COUNT(DISTINCT cui) FROM glossary_es_en;
EOF
    
    echo -e "${GREEN}Glossary built successfully.${NC}"
}

# Add Mexican-specific medical terms
add_mexican_terms() {
    echo -e "${YELLOW}Adding Mexican-specific medical terms...${NC}"
    
    psql -U $DB_USER -d $DB_NAME << 'EOF'
-- Add common Mexican medications and terms not in UMLS
INSERT INTO glossary_es_en (es_term, es_term_normalized, en_term, cui, source, priority, is_mexican)
VALUES 
    ('metamizol', 'metamizol', 'dipyrone/metamizole', 'MX001', 'MEXICAN_CUSTOM', 1, TRUE),
    ('metamizol sódico', 'metamizol sodico', 'metamizole sodium', 'MX002', 'MEXICAN_CUSTOM', 1, TRUE),
    ('clonixinato de lisina', 'clonixinato de lisina', 'lysine clonixinate', 'MX003', 'MEXICAN_CUSTOM', 1, TRUE),
    ('butilhioscina', 'butilhioscina', 'hyoscine butylbromide', 'MX004', 'MEXICAN_CUSTOM', 1, TRUE),
    ('derechohabiente', 'derechohabiente', 'beneficiary/insured person', 'MX005', 'IMSS', 1, TRUE),
    ('consulta externa', 'consulta externa', 'outpatient consultation', 'MX006', 'IMSS', 1, TRUE),
    ('cuadro básico', 'cuadro basico', 'essential medicines formulary', 'MX007', 'IMSS', 1, TRUE),
    ('urgencias calificadas', 'urgencias calificadas', 'qualified emergency', 'MX008', 'IMSS', 1, TRUE),
    ('pase a especialidad', 'pase a especialidad', 'specialty referral', 'MX009', 'IMSS', 1, TRUE),
    ('contrarreferencia', 'contrarreferencia', 'counter-referral', 'MX010', 'IMSS', 1, TRUE)
ON CONFLICT (es_term_normalized, en_term, cui) DO NOTHING;

-- Update statistics
INSERT INTO processing_stats (stage, count)
SELECT 'mexican_custom_terms', COUNT(*) 
FROM glossary_es_en 
WHERE source IN ('MEXICAN_CUSTOM', 'IMSS');
EOF
    
    echo -e "${GREEN}Mexican-specific terms added.${NC}"
}

# Export glossary to CSV
export_glossary() {
    echo -e "${YELLOW}Exporting glossary to CSV...${NC}"
    
    mkdir -p "$OUTPUT_DIR"
    
    # Export full glossary
    psql -U $DB_USER -d $DB_NAME << EOF
\copy (
    SELECT DISTINCT ON (es_term_normalized)
        es_term,
        en_term,
        source,
        cui,
        CASE WHEN is_mexican THEN 'mexican' ELSE 'general' END AS category
    FROM glossary_es_en
    ORDER BY es_term_normalized, priority, en_term
) TO '$OUTPUT_DIR/umls_glossary_full.csv' WITH CSV HEADER;
EOF
    
    # Export Mexican-priority glossary (production use)
    psql -U $DB_USER -d $DB_NAME << EOF
\copy (
    WITH prioritized AS (
        SELECT DISTINCT ON (es_term_normalized)
            es_term,
            en_term,
            source,
            is_mexican
        FROM glossary_es_en
        ORDER BY es_term_normalized, 
                CASE WHEN is_mexican THEN 0 ELSE 1 END,
                priority
    )
    SELECT 
        es_term,
        en_term,
        source
    FROM prioritized
) TO '$OUTPUT_DIR/glossary_es_en_production.csv' WITH CSV HEADER;
EOF
    
    # Export Mexican-only terms
    psql -U $DB_USER -d $DB_NAME << EOF
\copy (
    SELECT es_term, en_term, source
    FROM glossary_es_en
    WHERE is_mexican = TRUE
    ORDER BY es_term
) TO '$OUTPUT_DIR/glossary_mexican_only.csv' WITH CSV HEADER;
EOF
    
    # Show final statistics
    echo ""
    echo -e "${GREEN}Export complete!${NC}"
    echo ""
    
    psql -U $DB_USER -d $DB_NAME -t << EOF
SELECT '📊 Glossary Statistics:' AS info
UNION ALL
SELECT '  Total mappings: ' || COUNT(*)::text FROM glossary_es_en
UNION ALL
SELECT '  Unique Spanish terms: ' || COUNT(DISTINCT es_term_normalized)::text FROM glossary_es_en
UNION ALL
SELECT '  Mexican-specific: ' || COUNT(*)::text FROM glossary_es_en WHERE is_mexican = TRUE
UNION ALL
SELECT '  SNOMED CT Mexico: ' || COUNT(*)::text FROM glossary_es_en WHERE source = 'SNOMEDCT_MX'
UNION ALL
SELECT '  Spanish SNOMED: ' || COUNT(*)::text FROM glossary_es_en WHERE source = 'SCTSPA'
UNION ALL
SELECT '  MeSH Spanish: ' || COUNT(*)::text FROM glossary_es_en WHERE source = 'MSHSPA';
EOF
    
    echo ""
    echo "📁 Files created:"
    echo "  - $OUTPUT_DIR/umls_glossary_full.csv (all terms)"
    echo "  - $OUTPUT_DIR/glossary_es_en_production.csv (production use)"
    echo "  - $OUTPUT_DIR/glossary_mexican_only.csv (Mexican-specific)"
}

# Create Python integration script
create_integration_script() {
    echo -e "${YELLOW}Creating Python integration script...${NC}"
    
    cat > "$OUTPUT_DIR/use_umls_glossary.py" << 'EOF'
#!/usr/bin/env python3
"""
UMLS Glossary Integration for Enfermera Elena
Uses the generated Spanish-English medical glossary
"""

import csv
import re
from pathlib import Path
from typing import Dict, Set, Tuple

class UMLSMedicalGlossary:
    def __init__(self, glossary_path: str = "glossary_es_en_production.csv"):
        self.glossary = {}
        self.mexican_terms = set()
        self.load_glossary(glossary_path)
        
    def load_glossary(self, path: str):
        """Load UMLS glossary from CSV"""
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row['es_term'].lower()
                en_term = row['en_term']
                source = row.get('source', '')
                
                self.glossary[es_term] = en_term
                
                if 'MX' in source or source == 'IMSS':
                    self.mexican_terms.add(es_term)
                    
        print(f"Loaded {len(self.glossary)} terms ({len(self.mexican_terms)} Mexican-specific)")
        
    def translate_term(self, spanish_term: str) -> str:
        """Translate a single medical term"""
        normalized = spanish_term.lower().strip()
        return self.glossary.get(normalized, spanish_term)
        
    def apply_to_text(self, text: str) -> Tuple[str, int]:
        """Apply glossary to text, return (text, replacements_made)"""
        replacements = 0
        result = text
        
        # Sort by length (longest first) to match phrases before words
        sorted_terms = sorted(self.glossary.keys(), key=len, reverse=True)
        
        for es_term in sorted_terms:
            if es_term in result.lower():
                en_term = self.glossary[es_term]
                # Case-insensitive replacement
                pattern = re.compile(re.escape(es_term), re.IGNORECASE)
                result, count = pattern.subn(en_term, result)
                replacements += count
                
        return result, replacements
        
    def get_mexican_mappings(self) -> Dict[str, str]:
        """Get only Mexican-specific mappings"""
        return {term: self.glossary[term] for term in self.mexican_terms}

# Example usage
if __name__ == "__main__":
    glossary = UMLSMedicalGlossary()
    
    # Test translation
    test_text = "El paciente presenta hipertensión arterial y diabetes mellitus tipo 2"
    translated, count = glossary.apply_to_text(test_text)
    
    print(f"Original: {test_text}")
    print(f"Translated: {translated}")
    print(f"Replacements made: {count}")
    
    # Show Mexican terms
    mexican = glossary.get_mexican_mappings()
    print(f"\nMexican-specific terms: {len(mexican)}")
    for es, en in list(mexican.items())[:10]:
        print(f"  {es} → {en}")
EOF
    
    chmod +x "$OUTPUT_DIR/use_umls_glossary.py"
    echo -e "${GREEN}Integration script created.${NC}"
}

# Main workflow
main() {
    echo "Starting UMLS Full Release processing..."
    echo "Target: Mexican Spanish → English medical glossary"
    echo ""
    
    check_requirements
    setup_database
    create_tables
    load_mrconso
    build_glossary
    add_mexican_terms
    export_glossary
    create_integration_script
    
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}✅ UMLS Processing Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Review glossary at: $OUTPUT_DIR/glossary_es_en_production.csv"
    echo "2. Test with: python3 $OUTPUT_DIR/use_umls_glossary.py"
    echo "3. Integrate with translation adapters (LibreTranslate, ALIA, etc.)"
    echo ""
    echo "To use in your pipeline:"
    echo "  cp $OUTPUT_DIR/glossary_es_en_production.csv ../src/mt/"
    echo "  python3 ../src/mt/libretranslate_adapter.py --glossary glossary_es_en_production.csv"
}

# Parse command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [UMLS_DIR] [DB_NAME] [DB_USER]"
        echo ""
        echo "Arguments:"
        echo "  UMLS_DIR  Directory containing MRCONSO.RRF (default: ../data/umls)"
        echo "  DB_NAME   PostgreSQL database name (default: enfermera_elena)"
        echo "  DB_USER   PostgreSQL username (default: psadmin)"
        echo ""
        echo "Example:"
        echo "  $0 /path/to/umls/2024AA/META enfermera_elena psadmin"
        ;;
    --clean)
        echo "Cleaning database tables..."
        psql -U $DB_USER -d $DB_NAME -c "DROP TABLE IF EXISTS mrconso, glossary_es_en, mexican_priority CASCADE;"
        echo "Tables dropped."
        ;;
    *)
        main
        ;;
esac