# Enfermera Elena - Project Root Inventory

## Project Overview
Mexican Spanish-to-English medical record translation system with HIPAA compliance and GPU acceleration.

## Directory Structure
```
enfermera_elena/
├── CLAUDE.md (THIS FILE - Root inventory)
├── docs/
│   ├── CLAUDE.md (Documentation inventory)
│   ├── PRD.md
│   ├── TECHNICAL_REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── MEDICAL_GLOSSARY.md
│   ├── COMPLIANCE.md
│   ├── COMPETITIVE_ANALYSIS.md
│   ├── BUILD_VS_BUY_ANALYSIS.md
│   └── DE-IDENTIFICATION_STRATEGY.md
├── src/              [Future - Source code]
├── tests/            [Future - Test suites]
├── data/             [Future - Data files]
├── models/           [Future - ML models]
├── config/           [Future - Configuration]
└── scripts/          [Future - Utility scripts]
```

## Project Status
- **Phase**: Planning & Design
- **Documentation**: Complete (8 documents)
- **Timeline**: 4-5 months to production
- **Focus**: Mexican healthcare (IMSS/ISSSTE)

## Key Components

### 1. Documentation (`docs/`)
Comprehensive planning and design documents for the system. See `docs/CLAUDE.md` for detailed inventory.

### 2. Future Directories

#### `src/` - Application Source Code
Will contain:
- Translation pipeline
- De-identification module
- Mexican drug mapper
- IMSS terminology converter
- API endpoints

#### `models/` - Machine Learning Models
Will contain:
- Fine-tuned translation models
- PHI detection models
- Mexican medical NER

#### `data/` - Reference Data
Will contain:
- IMSS terminology database
- COFEPRIS drug mappings
- Mexican brand → US generic lookups
- Test documents

#### `config/` - Configuration Files
Will contain:
- Environment settings
- API credentials
- Model parameters
- HIPAA compliance rules

#### `tests/` - Test Suites
Will contain:
- Unit tests
- Integration tests
- Compliance tests
- Performance benchmarks

#### `scripts/` - Utility Scripts
Will contain:
- Setup scripts
- Data preprocessing
- Model training
- Deployment tools

## Quick Start Guide

### For Planning Phase (Current)
1. Review documentation in `docs/` folder
2. Start with `docs/PRD.md` for product vision
3. Check `docs/TECHNICAL_REQUIREMENTS.md` for tech stack
4. See `docs/DE-IDENTIFICATION_STRATEGY.md` for HIPAA compliance

### For Development Phase (Next)
1. Set up development environment
2. Integrate Mexican medical resources
3. Build de-identification pipeline
4. Implement translation layer
5. Add Mexican-specific mappings

## Key Technologies
- **Translation**: AWS/Google Translate API
- **Models**: Spanish Medical BERT (PlanTL)
- **GPU**: NVIDIA CUDA with TensorRT
- **Databases**: PostgreSQL, Redis
- **Framework**: FastAPI (Python)
- **Compliance**: HIPAA de-identification pipeline

## Contact & Resources
- **Documentation**: See `docs/` folder
- **Mexican Resources**: IMSS, COFEPRIS, CONAMED
- **Target Market**: US hospitals with Mexican patients

---
*Last Updated: 2025-09-05*
*Status: Planning Phase Complete*
*Next Step: Development Environment Setup*