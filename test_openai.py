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

# Check API key
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    print(f"✓ OpenAI API key found: {api_key[:10]}...")
    
    # Test connection
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Translate to English: Hola"}],
            max_tokens=10
        )
        print(f"✓ API working! Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ API error: {e}")
else:
    print("❌ No API key found")

# Check AWS credentials
aws_key = os.getenv('AWS_ACCESS_KEY_ID')
if aws_key:
    print(f"✓ AWS Access Key found: {aws_key[:10]}...")
