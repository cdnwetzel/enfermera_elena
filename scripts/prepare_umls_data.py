#!/usr/bin/env python3
"""
UMLS Data Preparation Script for Enfermera Elena
Prepares UMLS Metathesaurus data for Spanish-English medical translation

This script will be ready to run once UMLS license is approved (3 business days)
"""

import os
import csv
import logging
import argparse
import psycopg2
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UMLSProcessor:
    """Process UMLS RRF files for Spanish-English medical glossary"""
    
    def __init__(self, db_config: Dict[str, str], data_path: str):
        self.db_config = db_config
        self.data_path = Path(data_path)
        self.conn = None
        self.cursor = None
        
    def connect_db(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
            
    def create_tables(self):
        """Create MRCONSO and related tables"""
        
        # Main MRCONSO table for concept-term relationships
        mrconso_schema = """
        CREATE TABLE IF NOT EXISTS mrconso (
            CUI TEXT,      -- Concept Unique Identifier
            LAT TEXT,      -- Language (ENG, SPA)
            TS TEXT,       -- Term Status
            LUI TEXT,      -- Lexical Unique Identifier
            STT TEXT,      -- String Type
            SUI TEXT,      -- String Unique Identifier
            ISPREF TEXT,   -- Preferred flag
            AUI TEXT,      -- Atom Unique Identifier
            SAUI TEXT,     -- Source Atom Unique Identifier
            SCUI TEXT,     -- Source Concept Unique Identifier
            SDUI TEXT,     -- Source Descriptor Unique Identifier
            SAB TEXT,      -- Source Abbreviation (SNOMEDCT, ICD10, etc)
            TTY TEXT,      -- Term Type (PT=Preferred, SY=Synonym)
            CODE TEXT,     -- Source-specific code
            STR TEXT,      -- String/Term text
            SRL TEXT,      -- Source Restriction Level
            SUPPRESS TEXT, -- Suppression flag
            CVF TEXT       -- Content View Flag
        );
        """
        
        # Indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_mrconso_cui ON mrconso(CUI);",
            "CREATE INDEX IF NOT EXISTS idx_mrconso_lang ON mrconso(LAT);",
            "CREATE INDEX IF NOT EXISTS idx_mrconso_tty ON mrconso(TTY);",
            "CREATE INDEX IF NOT EXISTS idx_mrconso_sab ON mrconso(SAB);",
            "CREATE INDEX IF NOT EXISTS idx_mrconso_str ON mrconso(STR);",
            "CREATE INDEX IF NOT EXISTS idx_mrconso_composite ON mrconso(LAT, TTY, SAB);"
        ]
        
        # Glossary output table
        glossary_schema = """
        CREATE TABLE IF NOT EXISTS glossary_es_en (
            id SERIAL PRIMARY KEY,
            es_term TEXT NOT NULL,
            en_term TEXT NOT NULL,
            cui TEXT NOT NULL,
            source TEXT,
            priority INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(es_term, en_term, cui)
        );
        """
        
        # Mexican-specific terms table
        mexican_terms_schema = """
        CREATE TABLE IF NOT EXISTS mexican_medical_terms (
            id SERIAL PRIMARY KEY,
            es_term TEXT NOT NULL UNIQUE,
            en_term TEXT NOT NULL,
            category TEXT,  -- drug, procedure, diagnosis, etc
            imss_code TEXT,
            cofepris_id TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        try:
            # Create tables
            self.cursor.execute(mrconso_schema)
            self.cursor.execute(glossary_schema)
            self.cursor.execute(mexican_terms_schema)
            
            # Create indexes
            for idx in indexes:
                self.cursor.execute(idx)
                
            self.conn.commit()
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Table creation failed: {e}")
            self.conn.rollback()
            raise
            
    def load_mrconso(self, filepath: str = None):
        """Load MRCONSO.RRF file into database"""
        
        if not filepath:
            filepath = self.data_path / "MRCONSO.RRF"
            
        if not Path(filepath).exists():
            logger.warning(f"MRCONSO.RRF not found at {filepath}")
            logger.info("Will be available after UMLS license approval")
            return
            
        logger.info(f"Loading MRCONSO from {filepath}")
        
        try:
            # Use COPY for efficient bulk loading
            with open(filepath, 'r', encoding='utf-8') as f:
                self.cursor.copy_expert(
                    """COPY mrconso FROM STDIN WITH (
                        FORMAT csv,
                        DELIMITER '|',
                        NULL '',
                        QUOTE E'\b'
                    )""",
                    f
                )
            self.conn.commit()
            
            # Get statistics
            self.cursor.execute("SELECT COUNT(*) FROM mrconso WHERE LAT='SPA'")
            spa_count = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM mrconso WHERE LAT='ENG'")
            eng_count = self.cursor.fetchone()[0]
            
            logger.info(f"Loaded {spa_count} Spanish terms and {eng_count} English terms")
            
        except Exception as e:
            logger.error(f"Failed to load MRCONSO: {e}")
            self.conn.rollback()
            raise
            
    def build_spanish_english_glossary(self):
        """Build Spanish to English medical glossary prioritizing Mexican sources"""
        
        query = """
        -- Spanish-English Glossary with Mexican Priority
        WITH es_terms AS (
            -- Prioritize SNOMED CT Mexico and Spanish sources
            SELECT DISTINCT
                CUI,
                STR AS es_term,
                CASE 
                    WHEN SAB = 'SNOMEDCT_MX' THEN 1
                    WHEN SAB = 'SCTSPA' THEN 2
                    WHEN SAB LIKE 'SNOMED%' THEN 3
                    WHEN SAB = 'MSHSPA' THEN 4
                    WHEN SAB = 'MDRSPA' THEN 5
                    ELSE 10
                END AS priority,
                SAB AS source
            FROM mrconso
            WHERE LAT = 'SPA' 
                AND TTY IN ('PT', 'SY')  -- Preferred terms and synonyms
                AND (SUPPRESS IS NULL OR SUPPRESS != 'Y')
        ),
        en_terms AS (
            -- Get preferred English terms
            SELECT DISTINCT
                CUI,
                STR AS en_term,
                ROW_NUMBER() OVER (
                    PARTITION BY CUI 
                    ORDER BY 
                        CASE WHEN ISPREF='Y' THEN 0 ELSE 1 END,
                        CASE WHEN TTY='PT' THEN 0 ELSE 1 END,
                        CASE WHEN SAB LIKE 'SNOMED%' THEN 0 ELSE 1 END
                ) AS rn
            FROM mrconso
            WHERE LAT = 'ENG'
                AND TTY IN ('PT', 'SY')
                AND (SUPPRESS IS NULL OR SUPPRESS != 'Y')
        ),
        best_en AS (
            SELECT CUI, en_term
            FROM en_terms
            WHERE rn = 1
        )
        INSERT INTO glossary_es_en (es_term, en_term, cui, source, priority)
        SELECT DISTINCT
            LOWER(TRIM(es.es_term)) AS es_term,
            TRIM(en.en_term) AS en_term,
            es.CUI,
            es.source,
            es.priority
        FROM es_terms es
        INNER JOIN best_en en ON es.CUI = en.CUI
        WHERE es.es_term IS NOT NULL 
            AND en.en_term IS NOT NULL
            AND LENGTH(es.es_term) > 2
            AND LENGTH(en.en_term) > 2
        ON CONFLICT (es_term, en_term, cui) DO NOTHING;
        """
        
        try:
            self.cursor.execute(query)
            rows_inserted = self.cursor.rowcount
            self.conn.commit()
            
            logger.info(f"Created glossary with {rows_inserted} Spanish-English mappings")
            
            # Get statistics by source
            self.cursor.execute("""
                SELECT source, COUNT(*) as cnt 
                FROM glossary_es_en 
                GROUP BY source 
                ORDER BY cnt DESC
            """)
            
            logger.info("Glossary breakdown by source:")
            for source, count in self.cursor.fetchall():
                logger.info(f"  {source}: {count} terms")
                
        except Exception as e:
            logger.error(f"Failed to build glossary: {e}")
            self.conn.rollback()
            raise
            
    def load_mexican_terms(self, filepath: str = None):
        """Load Mexican-specific medical terms from CSV"""
        
        if not filepath:
            filepath = self.data_path / "mexican_terms.csv"
            
        if not Path(filepath).exists():
            logger.info(f"Mexican terms file not found at {filepath}, creating sample")
            self.create_sample_mexican_terms(filepath)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            insert_query = """
            INSERT INTO mexican_medical_terms 
            (es_term, en_term, category, imss_code, cofepris_id, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (es_term) DO UPDATE 
            SET en_term = EXCLUDED.en_term,
                category = EXCLUDED.category,
                imss_code = EXCLUDED.imss_code,
                cofepris_id = EXCLUDED.cofepris_id,
                notes = EXCLUDED.notes;
            """
            
            count = 0
            for row in reader:
                self.cursor.execute(insert_query, (
                    row.get('es_term'),
                    row.get('en_term'),
                    row.get('category'),
                    row.get('imss_code'),
                    row.get('cofepris_id'),
                    row.get('notes')
                ))
                count += 1
                
            self.conn.commit()
            logger.info(f"Loaded {count} Mexican-specific terms")
            
    def create_sample_mexican_terms(self, filepath: str):
        """Create sample Mexican terms CSV file"""
        
        sample_terms = [
            {
                'es_term': 'derechohabiente',
                'en_term': 'beneficiary/insured person',
                'category': 'administrative',
                'imss_code': '',
                'cofepris_id': '',
                'notes': 'IMSS/ISSSTE insurance beneficiary'
            },
            {
                'es_term': 'consulta externa',
                'en_term': 'outpatient consultation',
                'category': 'service',
                'imss_code': '',
                'cofepris_id': '',
                'notes': 'Outpatient medical visit'
            },
            {
                'es_term': 'cuadro básico',
                'en_term': 'essential medicines list',
                'category': 'administrative',
                'imss_code': '',
                'cofepris_id': '',
                'notes': 'IMSS formulary'
            },
            {
                'es_term': 'metamizol sódico',
                'en_term': 'metamizole sodium/dipyrone',
                'category': 'drug',
                'imss_code': '010.000.0102.00',
                'cofepris_id': '',
                'notes': 'Common analgesic in Mexico, restricted in US'
            },
            {
                'es_term': 'clonixinato de lisina',
                'en_term': 'lysine clonixinate',
                'category': 'drug',
                'imss_code': '010.000.0104.00',
                'cofepris_id': '',
                'notes': 'NSAID common in Mexico'
            }
        ]
        
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['es_term', 'en_term', 'category', 
                         'imss_code', 'cofepris_id', 'notes']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sample_terms)
            
        logger.info(f"Created sample Mexican terms file at {filepath}")
        
    def export_glossary(self, output_path: str = None):
        """Export final glossary to CSV for translation pipeline"""
        
        if not output_path:
            output_path = self.data_path / "glossary_es_en.csv"
            
        query = """
        -- Combine UMLS and Mexican-specific terms
        WITH combined AS (
            -- UMLS terms
            SELECT 
                es_term,
                en_term,
                'UMLS-' || source AS source,
                priority
            FROM glossary_es_en
            
            UNION ALL
            
            -- Mexican-specific terms (highest priority)
            SELECT 
                LOWER(es_term) AS es_term,
                en_term,
                'MEXICAN-' || category AS source,
                1 AS priority
            FROM mexican_medical_terms
        )
        SELECT DISTINCT ON (es_term)
            es_term,
            en_term,
            source
        FROM combined
        ORDER BY es_term, priority, en_term;
        """
        
        try:
            # Use COPY for efficient export
            with open(output_path, 'w', encoding='utf-8') as f:
                self.cursor.copy_expert(
                    f"COPY ({query}) TO STDOUT WITH CSV HEADER",
                    f
                )
                
            # Get count
            self.cursor.execute(f"SELECT COUNT(DISTINCT es_term) FROM ({query}) AS t")
            count = self.cursor.fetchone()[0]
            
            logger.info(f"Exported {count} unique Spanish terms to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to export glossary: {e}")
            raise
            
    def cleanup(self):
        """Close database connections"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connections closed")
        

def main():
    parser = argparse.ArgumentParser(
        description="Prepare UMLS data for Enfermera Elena translation pipeline"
    )
    parser.add_argument(
        '--data-path',
        default='../data/umls',
        help='Path to UMLS data directory'
    )
    parser.add_argument(
        '--db-host',
        default='localhost',
        help='PostgreSQL host'
    )
    parser.add_argument(
        '--db-name',
        default='enfermera_elena',
        help='Database name'
    )
    parser.add_argument(
        '--db-user',
        default='psadmin',
        help='Database user'
    )
    parser.add_argument(
        '--db-password',
        default='',
        help='Database password'
    )
    parser.add_argument(
        '--create-db',
        action='store_true',
        help='Create database if it does not exist'
    )
    parser.add_argument(
        '--skip-load',
        action='store_true',
        help='Skip loading MRCONSO (if already loaded)'
    )
    
    args = parser.parse_args()
    
    # Database configuration
    db_config = {
        'host': args.db_host,
        'database': args.db_name,
        'user': args.db_user,
    }
    
    if args.db_password:
        db_config['password'] = args.db_password
        
    # Create data directory if it doesn't exist
    data_path = Path(args.data_path)
    data_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize processor
    processor = UMLSProcessor(db_config, data_path)
    
    try:
        # Connect to database
        processor.connect_db()
        
        # Create tables
        processor.create_tables()
        
        # Load MRCONSO if not skipping
        if not args.skip_load:
            processor.load_mrconso()
        else:
            logger.info("Skipping MRCONSO load (--skip-load flag)")
            
        # Build glossary
        processor.build_spanish_english_glossary()
        
        # Load Mexican-specific terms
        processor.load_mexican_terms()
        
        # Export final glossary
        processor.export_glossary()
        
        logger.info("✅ UMLS data preparation completed successfully!")
        logger.info(f"📁 Glossary exported to: {data_path / 'glossary_es_en.csv'}")
        logger.info("Next step: Use glossary in translation pipeline")
        
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        raise
        
    finally:
        processor.cleanup()


if __name__ == "__main__":
    main()