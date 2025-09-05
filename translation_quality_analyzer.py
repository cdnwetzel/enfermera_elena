#!/usr/bin/env python3
"""
Translation Quality Analyzer for Enfermera Elena
Generates confidence scores and metadata for manual review
"""

import re
import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from collections import Counter, defaultdict


class TranslationQualityAnalyzer:
    """Analyze translation quality and generate confidence scores"""
    
    def __init__(self, glossary_path: str = "data/glossaries/glossary_es_en_production.csv"):
        self.glossary = {}
        self.load_glossary(glossary_path)
        
        # Known problematic patterns
        self.high_risk_terms = {
            # Medication dosages - critical for patient safety
            'mg', 'ml', 'mcg', 'ui', 'unidades', 'dosis', 
            'miligramos', 'mililitros', 'microgramos',
            
            # Allergies - critical
            'alergia', 'alergico', 'reaccion', 'anafilaxia',
            'hipersensibilidad', 'intolerancia',
            
            # Critical conditions
            'grave', 'severo', 'critico', 'urgente', 'emergencia',
            'riesgo', 'peligro', 'fatal', 'mortal',
            
            # Negations - meaning reversal risk
            'no', 'sin', 'nunca', 'ninguno', 'tampoco',
            'ni', 'ausencia', 'negativo', 'niega',
            
            # Time-sensitive information
            'inmediato', 'urgente', 'stat', 'ahora', 'pronto',
            'cada', 'horas', 'minutos', 'diario',
        }
        
        # Medical abbreviations that need verification
        self.medical_abbreviations = {
            'hta', 'dm', 'dm2', 'iam', 'evc', 'acv', 'epoc',
            'irc', 'ira', 'ivu', 'eda', 'tb', 'vih', 'ca',
            'rx', 'tx', 'dx', 'px', 'bh', 'qs', 'ego',
            'ta', 'pa', 'fc', 'fr', 'temp', 'spo2', 'imc',
        }
        
        # Confidence scoring weights
        self.weights = {
            'glossary_match': 0.4,      # Term found in UMLS glossary
            'structure_preserved': 0.2,  # Numbers, formatting preserved
            'no_mixed_language': 0.2,    # Clean language separation
            'critical_terms': 0.1,       # Critical terms handled properly
            'abbreviations': 0.1,        # Abbreviations expanded correctly
        }
        
    def load_glossary(self, path: str):
        """Load UMLS glossary"""
        if not Path(path).exists():
            print(f"Warning: Glossary not found at {path}")
            return
            
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                es_term = row['es_term'].lower()
                en_term = row['en_term']
                source = row.get('source', 'UNKNOWN')
                self.glossary[es_term] = {
                    'en_term': en_term,
                    'source': source,
                    'confidence': 0.9 if 'SNOMED' in source else 0.7
                }
                
        print(f"Loaded {len(self.glossary)} glossary terms for quality analysis")
        
    def analyze_translation(self, original: str, translated: str) -> Dict:
        """Analyze translation quality and generate confidence scores"""
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'total_confidence': 0.0,
            'line_scores': [],
            'critical_issues': [],
            'warnings': [],
            'statistics': {},
            'review_required': []
        }
        
        # Split into lines for line-by-line analysis
        original_lines = original.split('\n')
        translated_lines = translated.split('\n')
        
        # Analyze each line
        for i, (orig_line, trans_line) in enumerate(zip(original_lines, translated_lines)):
            if not orig_line.strip():
                continue
                
            line_analysis = self.analyze_line(orig_line, trans_line, i + 1)
            analysis['line_scores'].append(line_analysis)
            
            # Collect issues
            if line_analysis['confidence'] < 0.5:
                analysis['critical_issues'].append(line_analysis)
            elif line_analysis['confidence'] < 0.7:
                analysis['warnings'].append(line_analysis)
                
            # Mark for review if needed
            if line_analysis['needs_review']:
                analysis['review_required'].append(line_analysis)
                
        # Calculate overall statistics
        analysis['statistics'] = self.calculate_statistics(
            original, translated, analysis['line_scores']
        )
        
        # Calculate total confidence
        if analysis['line_scores']:
            analysis['total_confidence'] = sum(
                score['confidence'] for score in analysis['line_scores']
            ) / len(analysis['line_scores'])
            
        return analysis
        
    def analyze_line(self, original: str, translated: str, line_num: int) -> Dict:
        """Analyze a single line translation"""
        
        result = {
            'line_number': line_num,
            'original': original[:100] + '...' if len(original) > 100 else original,
            'translated': translated[:100] + '...' if len(translated) > 100 else translated,
            'confidence': 0.0,
            'issues': [],
            'needs_review': False,
            'scores': {}
        }
        
        # Score 1: Glossary matches
        glossary_score = self.score_glossary_matches(original, translated)
        result['scores']['glossary'] = glossary_score
        
        # Score 2: Structure preservation (numbers, punctuation)
        structure_score = self.score_structure_preservation(original, translated)
        result['scores']['structure'] = structure_score
        
        # Score 3: Language mixing detection
        mixing_score = self.score_language_mixing(translated)
        result['scores']['language'] = mixing_score
        
        # Score 4: Critical terms handling
        critical_score = self.score_critical_terms(original, translated)
        result['scores']['critical'] = critical_score
        
        # Score 5: Abbreviation handling
        abbrev_score = self.score_abbreviations(original, translated)
        result['scores']['abbreviations'] = abbrev_score
        
        # Calculate weighted confidence
        result['confidence'] = (
            self.weights['glossary_match'] * glossary_score +
            self.weights['structure_preserved'] * structure_score +
            self.weights['no_mixed_language'] * mixing_score +
            self.weights['critical_terms'] * critical_score +
            self.weights['abbreviations'] * abbrev_score
        )
        
        # Identify specific issues
        if glossary_score < 0.3:
            result['issues'].append('Low glossary coverage')
        if mixing_score < 0.5:
            result['issues'].append('Mixed language detected')
        if critical_score < 0.7 and any(term in original.lower() for term in self.high_risk_terms):
            result['issues'].append('Critical term translation uncertain')
            result['needs_review'] = True
        if structure_score < 0.8 and re.search(r'\d+\.?\d*\s*(?:mg|ml|mcg)', original):
            result['issues'].append('Dosage information - verify accuracy')
            result['needs_review'] = True
            
        return result
        
    def score_glossary_matches(self, original: str, translated: str) -> float:
        """Score based on glossary term matches"""
        original_lower = original.lower()
        translated_lower = translated.lower()
        
        matches = 0
        total_terms = 0
        
        for es_term, data in self.glossary.items():
            if es_term in original_lower:
                total_terms += 1
                en_term = data['en_term'].lower()
                if en_term in translated_lower:
                    matches += 1
                    
        if total_terms == 0:
            return 0.5  # Neutral score if no glossary terms
            
        return matches / total_terms
        
    def score_structure_preservation(self, original: str, translated: str) -> float:
        """Score preservation of numbers, dates, measurements"""
        # Extract numbers and measurements
        number_pattern = r'\d+[.,]?\d*'
        orig_numbers = re.findall(number_pattern, original)
        trans_numbers = re.findall(number_pattern, translated)
        
        if not orig_numbers:
            return 1.0  # Perfect score if no numbers to preserve
            
        # Check if all numbers are preserved
        preserved = sum(1 for num in orig_numbers if num in trans_numbers)
        return preserved / len(orig_numbers)
        
    def score_language_mixing(self, translated: str) -> float:
        """Detect and score language mixing in translation"""
        # Spanish word indicators
        spanish_indicators = [
            'el', 'la', 'los', 'las', 'de', 'del', 'con', 'sin',
            'por', 'para', 'que', 'es', 'esta', 'estan', 'tiene'
        ]
        
        words = translated.lower().split()
        if len(words) < 5:
            return 1.0  # Too short to evaluate
            
        spanish_count = sum(1 for word in words if word in spanish_indicators)
        mixing_ratio = spanish_count / len(words)
        
        # Perfect score if no Spanish, decreasing with more Spanish
        return max(0, 1 - (mixing_ratio * 2))
        
    def score_critical_terms(self, original: str, translated: str) -> float:
        """Score handling of critical medical terms"""
        original_lower = original.lower()
        
        critical_found = [term for term in self.high_risk_terms 
                         if term in original_lower]
        
        if not critical_found:
            return 1.0  # No critical terms
            
        # Check if critical terms are properly handled
        # This is simplified - in production would need term-specific validation
        score = 0.5  # Base score for presence of critical terms
        
        # Check for preservation of negations
        if 'no' in critical_found or 'sin' in critical_found:
            if 'not' in translated.lower() or 'without' in translated.lower():
                score += 0.5
            else:
                score -= 0.3  # Penalty for missing negation
                
        return max(0, min(1, score))
        
    def score_abbreviations(self, original: str, translated: str) -> float:
        """Score medical abbreviation handling"""
        original_lower = original.lower()
        
        abbrevs_found = [abbrev for abbrev in self.medical_abbreviations 
                        if abbrev in original_lower.split()]
        
        if not abbrevs_found:
            return 1.0  # No abbreviations
            
        # Check if abbreviations are expanded or preserved appropriately
        expanded_count = 0
        for abbrev in abbrevs_found:
            # Check for common expansions
            if abbrev == 'hta' and 'hypertension' in translated.lower():
                expanded_count += 1
            elif abbrev == 'dm' and 'diabetes' in translated.lower():
                expanded_count += 1
            elif abbrev.upper() in translated:  # Preserved as uppercase
                expanded_count += 1
                
        return expanded_count / len(abbrevs_found)
        
    def calculate_statistics(self, original: str, translated: str, 
                            line_scores: List[Dict]) -> Dict:
        """Calculate overall translation statistics"""
        
        stats = {
            'total_lines': len(line_scores),
            'high_confidence_lines': sum(1 for s in line_scores if s['confidence'] >= 0.8),
            'medium_confidence_lines': sum(1 for s in line_scores if 0.5 <= s['confidence'] < 0.8),
            'low_confidence_lines': sum(1 for s in line_scores if s['confidence'] < 0.5),
            'lines_needing_review': sum(1 for s in line_scores if s['needs_review']),
            'original_words': len(original.split()),
            'translated_words': len(translated.split()),
            'glossary_coverage': self.calculate_glossary_coverage(original),
            'critical_terms_found': len([t for t in self.high_risk_terms if t in original.lower()]),
            'abbreviations_found': len([a for a in self.medical_abbreviations if a in original.lower()])
        }
        
        # Add percentages
        if stats['total_lines'] > 0:
            stats['high_confidence_pct'] = (stats['high_confidence_lines'] / stats['total_lines']) * 100
            stats['review_required_pct'] = (stats['lines_needing_review'] / stats['total_lines']) * 100
            
        return stats
        
    def calculate_glossary_coverage(self, text: str) -> float:
        """Calculate percentage of text covered by glossary"""
        text_lower = text.lower()
        words = text_lower.split()
        
        if not words:
            return 0
            
        covered_words = 0
        for word in words:
            if word in self.glossary:
                covered_words += 1
                
        return (covered_words / len(words)) * 100
        
    def generate_review_document(self, analysis: Dict, output_path: str):
        """Generate a human-readable review document"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TRANSLATION QUALITY ANALYSIS REPORT\n")
            f.write("Enfermera Elena - Medical Translation System\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Generated: {analysis['timestamp']}\n")
            f.write(f"Overall Confidence Score: {analysis['total_confidence']:.2%}\n\n")
            
            # Executive Summary
            f.write("EXECUTIVE SUMMARY\n")
            f.write("-" * 40 + "\n")
            stats = analysis['statistics']
            f.write(f"Total Lines Analyzed: {stats['total_lines']}\n")
            f.write(f"High Confidence (≥80%): {stats['high_confidence_lines']} ({stats.get('high_confidence_pct', 0):.1f}%)\n")
            f.write(f"Medium Confidence (50-79%): {stats['medium_confidence_lines']}\n")
            f.write(f"Low Confidence (<50%): {stats['low_confidence_lines']}\n")
            f.write(f"Lines Requiring Manual Review: {stats['lines_needing_review']} ({stats.get('review_required_pct', 0):.1f}%)\n")
            f.write(f"Glossary Coverage: {stats['glossary_coverage']:.1f}%\n")
            f.write(f"Critical Terms Found: {stats['critical_terms_found']}\n")
            f.write(f"Medical Abbreviations: {stats['abbreviations_found']}\n\n")
            
            # Critical Issues
            if analysis['critical_issues']:
                f.write("⚠️  CRITICAL ISSUES (Confidence < 50%)\n")
                f.write("-" * 40 + "\n")
                for issue in analysis['critical_issues'][:10]:  # Top 10
                    f.write(f"\nLine {issue['line_number']} (Confidence: {issue['confidence']:.2%})\n")
                    f.write(f"Original:   {issue['original']}\n")
                    f.write(f"Translated: {issue['translated']}\n")
                    f.write(f"Issues: {', '.join(issue['issues'])}\n")
                f.write("\n")
                
            # Lines Requiring Review
            if analysis['review_required']:
                f.write("🔍 LINES REQUIRING MANUAL REVIEW\n")
                f.write("-" * 40 + "\n")
                for item in analysis['review_required'][:20]:  # Top 20
                    f.write(f"\nLine {item['line_number']}: {', '.join(item['issues'])}\n")
                    f.write(f"  Original:   {item['original']}\n")
                    f.write(f"  Translated: {item['translated']}\n")
                f.write("\n")
                
            # Warnings
            if analysis['warnings']:
                f.write("⚡ WARNINGS (Confidence 50-70%)\n")
                f.write("-" * 40 + "\n")
                for warning in analysis['warnings'][:10]:  # Top 10
                    f.write(f"Line {warning['line_number']}: {', '.join(warning['issues'])}\n")
                f.write("\n")
                
            # Detailed Scoring Breakdown
            f.write("CONFIDENCE SCORE DISTRIBUTION\n")
            f.write("-" * 40 + "\n")
            
            # Create histogram
            bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
            histogram = defaultdict(int)
            for score in analysis['line_scores']:
                for i in range(len(bins)-1):
                    if bins[i] <= score['confidence'] < bins[i+1]:
                        histogram[f"{bins[i]:.0%}-{bins[i+1]:.0%}"] = histogram.get(f"{bins[i]:.0%}-{bins[i+1]:.0%}", 0) + 1
                        break
                        
            for range_label, count in sorted(histogram.items()):
                bar = '█' * int(count / max(histogram.values()) * 40)
                f.write(f"{range_label:>10}: {bar} ({count})\n")
                
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF REPORT\n")
            
    def generate_json_metadata(self, analysis: Dict, output_path: str):
        """Generate machine-readable JSON metadata"""
        
        metadata = {
            'version': '1.0',
            'timestamp': analysis['timestamp'],
            'summary': {
                'total_confidence': analysis['total_confidence'],
                'lines_analyzed': analysis['statistics']['total_lines'],
                'review_required': analysis['statistics']['lines_needing_review'],
                'critical_issues': len(analysis['critical_issues']),
                'warnings': len(analysis['warnings'])
            },
            'statistics': analysis['statistics'],
            'high_priority_reviews': [
                {
                    'line': item['line_number'],
                    'confidence': item['confidence'],
                    'issues': item['issues'],
                    'original_preview': item['original'][:50],
                    'translated_preview': item['translated'][:50]
                }
                for item in analysis['review_required'][:10]
            ],
            'confidence_distribution': {},
            'quality_indicators': {
                'glossary_coverage': analysis['statistics']['glossary_coverage'],
                'structure_preservation': sum(s['scores'].get('structure', 0) for s in analysis['line_scores']) / len(analysis['line_scores']) if analysis['line_scores'] else 0,
                'language_separation': sum(s['scores'].get('language', 0) for s in analysis['line_scores']) / len(analysis['line_scores']) if analysis['line_scores'] else 0
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)


def main():
    """Main function to analyze translation quality"""
    
    print("=" * 80)
    print("Translation Quality Analysis")
    print("Enfermera Elena - Medical Translation System")
    print("=" * 80)
    
    # File paths
    original_file = "medical_records/extracted/mr_12_03_25_MACSMA_extracted.txt"
    translated_file = "medical_records/translated/mr_12_03_25_MACSMA_translated.txt"
    
    # Load files
    print(f"\n📄 Loading original: {original_file}")
    with open(original_file, 'r', encoding='utf-8') as f:
        original_text = f.read()
        
    print(f"📄 Loading translation: {translated_file}")
    with open(translated_file, 'r', encoding='utf-8') as f:
        translated_text = f.read()
        
    # Initialize analyzer
    print("\n🔍 Initializing quality analyzer...")
    analyzer = TranslationQualityAnalyzer()
    
    # Analyze translation
    print("📊 Analyzing translation quality...")
    analysis = analyzer.analyze_translation(original_text, translated_text)
    
    # Generate reports
    review_doc = "medical_records/quality/quality_review.txt"
    metadata_json = "medical_records/quality/quality_metadata.json"
    
    print(f"\n📝 Generating review document: {review_doc}")
    analyzer.generate_review_document(analysis, review_doc)
    
    print(f"📝 Generating JSON metadata: {metadata_json}")
    analyzer.generate_json_metadata(analysis, metadata_json)
    
    # Print summary
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Overall Confidence Score: {analysis['total_confidence']:.2%}")
    print(f"Lines Requiring Review: {analysis['statistics']['lines_needing_review']}")
    print(f"Critical Issues Found: {len(analysis['critical_issues'])}")
    print(f"Warnings: {len(analysis['warnings'])}")
    
    print("\n📁 Output Files:")
    print(f"  - Review Document: {review_doc}")
    print(f"  - JSON Metadata: {metadata_json}")
    
    print("\n✅ Quality analysis complete!")
    print(f"\nView the review document: cat {review_doc}")


if __name__ == "__main__":
    main()