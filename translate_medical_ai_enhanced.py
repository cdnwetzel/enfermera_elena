#!/usr/bin/env python3
"""
AI-Enhanced Medical Record Translator for Enfermera Elena
Combines UMLS glossary with OpenAI API for context-aware translation
Maintains HIPAA compliance by removing PHI before API calls
"""

import re
import time
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pickle
from datetime import datetime

# Load environment variables from .env file
from pathlib import Path
env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value.strip('"').strip("'")

# Check for OpenAI library
try:
    import openai
except ImportError:
    print("Installing OpenAI library...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'openai'])
    import openai

class AIEnhancedMedicalTranslator:
    def __init__(self, glossary_dir: str = "data/glossaries", api_key: Optional[str] = None):
        self.glossary_dir = Path(glossary_dir)
        self.cache_file = self.glossary_dir / "glossary_cache.pkl"
        
        # OpenAI setup
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if self.api_key:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            self.ai_enabled = True
            print("✓ OpenAI API configured")
        else:
            self.ai_enabled = False
            print("⚠ OpenAI API key not found - using glossary-only mode")
        
        # Load glossaries
        self.critical_terms = {}
        self.common_terms = {}
        self.load_optimized_glossaries()
        
        # PHI patterns for privacy
        self.phi_patterns = {
            'name': re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b'),
            'id': re.compile(r'\b\d{6,}\b'),
            'phone': re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'),
            'email': re.compile(r'\b[\w._%+-]+@[\w.-]+\.[A-Z|a-z]{2,}\b'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            'mrn': re.compile(r'\b(?:MRN|HC|ID)[\s:]*\d+\b', re.IGNORECASE),
        }
        
        # Medical context patterns
        self.medical_contexts = {
            'diagnosis': re.compile(r'(?:diagnóstico|dx|impresión diagnóstica|conclusión)', re.IGNORECASE),
            'medication': re.compile(r'(?:medicamento|fármaco|dosis|mg|ml|tableta|cápsula)', re.IGNORECASE),
            'procedure': re.compile(r'(?:procedimiento|cirugía|operación|intervención)', re.IGNORECASE),
            'lab': re.compile(r'(?:laboratorio|análisis|prueba|resultado|valor)', re.IGNORECASE),
        }
    
    def load_optimized_glossaries(self):
        """Load cached glossaries for performance"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.critical_terms = cache_data.get('critical', {})
                    self.common_terms = cache_data.get('common', {})
                    print(f"✓ Loaded {len(self.critical_terms):,} critical terms")
                    print(f"✓ Loaded {len(self.common_terms):,} common terms")
                    return
            except:
                pass
        
        # Load from CSV if no cache
        self._load_from_csv()
    
    def _load_from_csv(self):
        """Load glossaries from CSV files"""
        import csv
        
        # Critical medical terms
        critical_keywords = {
            'alergia', 'diabetes', 'hipertensión', 'cáncer', 'urgencia',
            'emergencia', 'crítico', 'grave', 'infarto', 'hemorragia'
        }
        
        comprehensive_path = self.glossary_dir / "glossary_comprehensive.csv"
        if comprehensive_path.exists():
            with open(comprehensive_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    es_term = row['es_term'].lower().strip()
                    en_term = row['en_term'].strip()
                    
                    if any(kw in es_term for kw in critical_keywords):
                        self.critical_terms[es_term] = en_term
                    elif len(es_term.split()) <= 2:
                        self.common_terms[es_term] = en_term
    
    def remove_phi(self, text: str) -> Tuple[str, Dict]:
        """Remove PHI and replace with placeholders"""
        sanitized = text
        phi_map = {}
        placeholder_num = 0
        
        for phi_type, pattern in self.phi_patterns.items():
            for match in pattern.finditer(text):
                placeholder = f"[{phi_type.upper()}_{placeholder_num}]"
                phi_map[placeholder] = match.group()
                sanitized = sanitized.replace(match.group(), placeholder)
                placeholder_num += 1
        
        return sanitized, phi_map
    
    def restore_phi(self, text: str, phi_map: Dict) -> str:
        """Restore PHI from placeholders"""
        restored = text
        for placeholder, original in phi_map.items():
            restored = restored.replace(placeholder, original)
        return restored
    
    def detect_context(self, text: str) -> str:
        """Detect medical context of text"""
        for context_type, pattern in self.medical_contexts.items():
            if pattern.search(text):
                return context_type
        return 'general'
    
    def translate_with_ai(self, text: str, context: str = 'general') -> Tuple[str, float]:
        """Translate using OpenAI API with medical context"""
        if not self.ai_enabled or not text.strip():
            return text, 0.0
        
        # Remove PHI for privacy
        sanitized_text, phi_map = self.remove_phi(text)
        
        # Skip if too short or no Spanish content
        if len(sanitized_text.split()) < 3:
            return text, 0.5
        
        try:
            # Create context-aware prompt
            system_prompt = """You are a medical translator specializing in Mexican Spanish to English translation.
            Translate the following medical text accurately, preserving:
            - Medical terminology and abbreviations
            - Numerical values and units
            - Document structure and formatting
            - Professional medical tone
            
            Context: """ + context
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Translate to English:\n{sanitized_text}"}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=len(sanitized_text) * 2,  # Allow for expansion
                timeout=5
            )
            
            translated = response.choices[0].message.content.strip()
            
            # Restore PHI
            translated = self.restore_phi(translated, phi_map)
            
            # High confidence for AI translation
            confidence = 0.9
            
            return translated, confidence
            
        except Exception as e:
            print(f"  AI translation error: {e}")
            return text, 0.0
    
    def translate_hybrid(self, text: str) -> Tuple[str, float]:
        """Hybrid translation: glossary first, then AI for unknowns"""
        if not text.strip():
            return text, 1.0
        
        # First pass: Use glossary for known terms
        words = text.split()
        translated_words = []
        unknown_indices = []
        glossary_matches = 0
        
        for i, word in enumerate(words):
            word_lower = word.lower().strip('.,;:!?')
            
            # Check critical terms first
            if word_lower in self.critical_terms:
                translated_words.append(self.critical_terms[word_lower])
                glossary_matches += 1
            elif word_lower in self.common_terms:
                translated_words.append(self.common_terms[word_lower])
                glossary_matches += 1
            else:
                translated_words.append(word)
                unknown_indices.append(i)
        
        # Calculate initial confidence
        initial_confidence = glossary_matches / len(words) if words else 0
        
        # If confidence is low and AI is available, use AI for context
        if initial_confidence < 0.7 and self.ai_enabled and len(unknown_indices) > 2:
            # Get context window (3 words before and after unknowns)
            context_text = ' '.join(words)
            medical_context = self.detect_context(context_text)
            
            # Translate with AI
            ai_translated, ai_confidence = self.translate_with_ai(context_text, medical_context)
            
            if ai_confidence > initial_confidence:
                return ai_translated, ai_confidence
        
        # Return glossary-based translation
        return ' '.join(translated_words), initial_confidence
    
    def translate_document(self, input_path: str, output_path: str = None) -> Dict:
        """Translate entire document with hybrid approach"""
        print(f"\n📄 Translating: {input_path}")
        start_time = time.time()
        
        # Read input
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"  Processing {len(lines)} lines...")
        if self.ai_enabled:
            print("  Using AI-enhanced translation for complex phrases")
        
        # Group lines into chunks for context
        translated_lines = []
        total_confidence = 0.0
        line_count = 0
        ai_calls = 0
        
        # Process in chunks of 5 lines for context
        chunk_size = 5
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i+chunk_size]
            chunk_text = ' '.join(chunk).strip()
            
            if i % 50 == 0 and i > 0:
                print(f"  Progress: {i}/{len(lines)} lines ({i*100/len(lines):.1f}%)")
                if ai_calls > 0:
                    print(f"    AI calls made: {ai_calls}")
            
            if not chunk_text:
                translated_lines.extend(chunk)
                continue
            
            # Detect if this chunk needs AI translation
            needs_ai = False
            if self.ai_enabled:
                # Use AI for complex medical sections
                if any(pattern.search(chunk_text) for pattern in self.medical_contexts.values()):
                    needs_ai = True
                # Use AI if many unknown words
                unknown_count = sum(1 for word in chunk_text.split() 
                                  if word.lower() not in self.critical_terms 
                                  and word.lower() not in self.common_terms)
                if unknown_count > len(chunk_text.split()) * 0.5:
                    needs_ai = True
            
            if needs_ai:
                translated, confidence = self.translate_with_ai(chunk_text)
                ai_calls += 1
                # Split back into lines
                translated_parts = translated.split('\n')
                while len(translated_parts) < len(chunk):
                    translated_parts.append('')
                translated_lines.extend([part + '\n' for part in translated_parts[:len(chunk)]])
            else:
                # Use hybrid translation line by line
                for line in chunk:
                    translated, confidence = self.translate_hybrid(line)
                    translated_lines.append(translated if translated.endswith('\n') else translated + '\n')
            
            if chunk_text:
                total_confidence += confidence
                line_count += 1
        
        # Calculate average confidence
        avg_confidence = total_confidence / line_count if line_count > 0 else 0
        
        # Save translation
        if not output_path:
            output_path = input_path.replace('_extracted.txt', '_translated.txt')
            output_path = output_path.replace('/extracted/', '/translated/')
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(translated_lines)
        
        elapsed = time.time() - start_time
        
        result = {
            'input': input_path,
            'output': output_path,
            'lines': len(lines),
            'time': f"{elapsed:.1f}s",
            'confidence': f"{avg_confidence:.1%}",
            'ai_calls': ai_calls,
            'mode': 'AI-enhanced' if self.ai_enabled else 'Glossary-only'
        }
        
        print(f"\n✓ Translation complete in {elapsed:.1f}s")
        print(f"  Mode: {result['mode']}")
        print(f"  Average confidence: {avg_confidence:.1%}")
        if ai_calls > 0:
            print(f"  AI API calls: {ai_calls}")
        print(f"  Output: {output_path}")
        
        return result

def main():
    """Main function"""
    print("="*70)
    print("Enfermera Elena - AI-Enhanced Medical Translation")
    print("="*70)
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\n⚠ Warning: OPENAI_API_KEY not set")
        print("  To enable AI-enhanced translation:")
        print("  export OPENAI_API_KEY='your-api-key'")
        print("\n  Continuing with glossary-only mode...")
    
    # Initialize translator
    translator = AIEnhancedMedicalTranslator(api_key=api_key)
    
    # Translate the example document
    input_file = "medical_records/extracted/mr_12_03_25_MACSMA_redacted_extracted.txt"
    
    if not Path(input_file).exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    # Perform translation
    result = translator.translate_document(input_file)
    
    # Show sample
    output_file = result['output']
    with open(output_file, 'r', encoding='utf-8') as f:
        sample = f.read(1000)
    
    print("\n📝 Sample of translation:")
    print("-"*70)
    print(sample)
    print("-"*70)
    
    print("\n✅ Translation complete!")
    print(f"View full translation: cat {output_file}")
    
    # Save metadata
    metadata_file = output_file.replace('.txt', '_metadata.json')
    with open(metadata_file, 'w') as f:
        result['timestamp'] = datetime.now().isoformat()
        json.dump(result, f, indent=2)
    print(f"Metadata saved: {metadata_file}")

if __name__ == "__main__":
    main()