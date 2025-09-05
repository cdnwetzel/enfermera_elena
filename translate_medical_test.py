#!/usr/bin/env python3
"""
Quick test of AI-enhanced medical translation
"""

import os
from pathlib import Path

# Load .env file
env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")

from openai import OpenAI

# Sample medical text from the document
sample_text = """
DETALLADO DE CARGOS DE HOSPITALIZACIÓN
12/03/2025 4355 TOMOGRAFIA TORAX SIMPLE 1 ES $5,330.50
12/03/2025 3646 BIOMETRIA HEMATICA COMPLETA 1 SERV. $263.40
12/03/2025 16982 ADMINISTRACION DE MEDICAMENTOS POR VIA INHALADA POR SESION
13/03/2025 2307 CLEXANE 60MG JGA 1 AMP $944.00
"""

def test_translation():
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("No API key found")
        return
    
    client = OpenAI(api_key=api_key)
    
    print("Testing medical translation with OpenAI...")
    print("="*60)
    print("Original Spanish:")
    print(sample_text)
    print("="*60)
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": """You are a medical translator specializing in Mexican Spanish to English translation.
                    Translate medical records accurately, preserving:
                    - Medical terminology and drug names
                    - Dates and numerical values
                    - Units and abbreviations
                    - Document structure"""
                },
                {
                    "role": "user", 
                    "content": f"Translate this medical billing record to English:\n{sample_text}"
                }
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        translation = response.choices[0].message.content
        print("AI Translation:")
        print(translation)
        print("="*60)
        print("✓ OpenAI translation successful!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_translation()