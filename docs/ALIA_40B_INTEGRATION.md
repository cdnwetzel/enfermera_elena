# ALIA-40b Integration Strategy for Enfermera Elena
## Spanish-First Medical Understanding with On-Premise LLM

### Executive Summary
ALIA-40b from Barcelona Supercomputing Center is a Spanish/Catalan-specialized 40B parameter model that could revolutionize our medical translation approach by providing native Spanish understanding rather than just translation.

---

## Why ALIA-40b Makes Sense

### Advantages Over Current Approaches

| Feature | LibreTranslate | OpenAI GPT-4 | ALIA-40b |
|---------|---------------|--------------|-----------|
| Spanish-first training | ❌ Generic | ❌ English-first | ✅ Spanish-native |
| Medical reasoning | ❌ None | ✅ Good | ✅ Trainable |
| On-premise | ✅ Yes | ❌ No | ✅ Yes |
| HIPAA compliant | ✅ Yes | ❓ Needs BAA | ✅ Yes |
| Mexican context | ❌ No | ⭕ Some | ✅ Adaptable |
| Cost per page | $0 | $0.10 | $0 (after setup) |
| Model size | 2GB | N/A | 40-80GB |

### Key Benefits for Medical Translation

1. **Native Understanding**: Trained on 3.6T tokens of Spanish/Catalan/English
2. **Cultural Context**: Understands Iberian and Latin American Spanish
3. **Medical Adaptability**: Can be fine-tuned on Mexican medical corpus
4. **Single-Pass Processing**: Spanish → Understanding → English in one model
5. **No External Dependencies**: Fully on-premise, no API calls

---

## Deployment Strategies

### Option 1: vLLM (RECOMMENDED) ✅

**Best for production with ChatPS GPU infrastructure**

```bash
# Install vLLM
pip install vllm

# Deploy with tensor parallelism across 2 GPUs
python -m vllm.entrypoints.openai.api_server \
    --model BSC-LT/ALIA-40b \
    --tensor-parallel-size 2 \
    --dtype float16 \
    --max-model-len 4096 \
    --port 8504
```

**Advantages:**
- PagedAttention for 24x throughput
- Continuous batching
- OpenAI-compatible API
- Tensor parallelism for multi-GPU
- Production-ready

**Requirements:**
- 2x A100 40GB or 2x RTX 4090 24GB (with quantization)
- 64GB system RAM
- NVLink preferred for multi-GPU

### Option 2: Ollama (If Available)

**Simpler deployment but needs GGUF format**

```bash
# Check if ALIA is available
ollama list | grep alia

# If not, convert to GGUF first
python convert-hf-to-gguf.py BSC-LT/ALIA-40b

# Run with Ollama
ollama run alia:40b-q4_K_M
```

**Advantages:**
- Easy deployment
- Built-in quantization
- Simple API
- Integrates with ChatPS existing Ollama setup

**Limitations:**
- ALIA might not be in Ollama library yet
- Less control over inference parameters
- Lower throughput than vLLM

### Option 3: Transformers + Accelerate

**For testing and development**

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model = AutoModelForCausalLM.from_pretrained(
    "BSC-LT/ALIA-40b",
    device_map="auto",
    load_in_4bit=True,  # For memory efficiency
    torch_dtype=torch.float16
)
tokenizer = AutoTokenizer.from_pretrained("BSC-LT/ALIA-40b")
```

**Use Cases:**
- Development testing
- Fine-tuning
- Small-scale deployment

---

## Integration with Enfermera Elena

### Architecture Changes

```
Current Pipeline:
PDF → OCR → De-ID → LibreTranslate/OpenAI → Re-ID → PDF

With ALIA-40b:
PDF → OCR → De-ID → ALIA-40b (Understanding + Translation) → Re-ID → PDF
```

### ALIA Adapter Implementation

```python
class ALIAMedicalTranslator:
    def __init__(self, vllm_url="http://localhost:8504"):
        self.client = OpenAI(
            base_url=vllm_url,
            api_key="dummy"  # vLLM doesn't need real key
        )
        
    def translate_medical(self, spanish_text: str) -> str:
        # Single prompt for understanding AND translation
        prompt = f"""Eres un traductor médico especializado en documentos del IMSS mexicano.

Texto médico en español mexicano:
{spanish_text}

Instrucciones:
1. Comprende el contexto médico mexicano (IMSS, ISSSTE, medicamentos mexicanos)
2. Traduce al inglés médico estadounidense
3. Preserva EXACTAMENTE todos los placeholders __PHI_*__
4. Convierte medicamentos mexicanos a equivalentes US:
   - Metamizol → Dipyrone (note: restricted in US)
   - Clonixinato de lisina → Lysine clonixinate
   - Paracetamol → Acetaminophen
5. Expande abreviaturas mexicanas:
   - HTA → Hypertension
   - DM2 → Type 2 Diabetes
   - EVC → Stroke

Traducción al inglés:"""

        response = self.client.chat.completions.create(
            model="ALIA-40b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048
        )
        
        return response.choices[0].message.content
```

---

## Resource Requirements

### Minimum Hardware (Quantized)
- **GPU**: 2x RTX 4090 24GB or 1x A100 80GB
- **RAM**: 64GB system memory
- **Storage**: 100GB for model weights
- **Quantization**: 4-bit (Q4_K_M) reduces to ~20GB VRAM

### Recommended Hardware (Full Precision)
- **GPU**: 2x A100 80GB with NVLink
- **RAM**: 128GB system memory
- **Storage**: 200GB NVMe SSD
- **Network**: 10Gbps for distributed inference

### ChatPS_v2_ng Integration
Since ChatPS_v2_ng already has:
- GPU infrastructure (86,748 nodes mentioned)
- Port 8504 for GPU service
- 20-45x performance boost capability

ALIA-40b would fit perfectly into the existing architecture.

---

## Deployment Guide

### Step 1: Check GPU Resources
```bash
nvidia-smi
# Need at least 40GB total VRAM (can be split across GPUs)
```

### Step 2: Install vLLM
```bash
pip install vllm
pip install flash-attn --no-build-isolation  # Optional but recommended
```

### Step 3: Download Model (Quantized)
```python
from huggingface_hub import snapshot_download

# Download quantized version if available
snapshot_download(
    repo_id="BSC-LT/ALIA-40b-GPTQ",  # Check if exists
    local_dir="./models/alia-40b"
)
```

### Step 4: Launch vLLM Server
```bash
# For 2 GPUs with tensor parallelism
CUDA_VISIBLE_DEVICES=0,1 python -m vllm.entrypoints.openai.api_server \
    --model ./models/alia-40b \
    --tensor-parallel-size 2 \
    --dtype float16 \
    --max-model-len 4096 \
    --port 8504 \
    --quantization gptq  # If using quantized model
```

### Step 5: Test Translation
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8504/v1", api_key="dummy")

response = client.chat.completions.create(
    model="ALIA-40b",
    messages=[{
        "role": "user", 
        "content": "Traduce: El paciente presenta HTA controlada con Losartán 50mg"
    }],
    temperature=0.3
)

print(response.choices[0].message.content)
# Expected: "The patient presents controlled hypertension with Losartan 50mg"
```

---

## Performance Optimization

### 1. Quantization Options
```python
# 4-bit quantization with bitsandbytes
from transformers import BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True
)
```

### 2. Batching Strategy
```python
# Process multiple pages in parallel
texts = ["page1", "page2", "page3"]
responses = client.completions.create(
    model="ALIA-40b",
    prompt=texts,
    max_tokens=2048,
    n=1,
    echo=False,
    stream=False
)
```

### 3. Caching Layer
```python
import hashlib
import redis

class CachedALIA:
    def __init__(self):
        self.cache = redis.Redis()
        self.alia = ALIAMedicalTranslator()
        
    def translate(self, text):
        key = hashlib.md5(text.encode()).hexdigest()
        
        # Check cache
        cached = self.cache.get(key)
        if cached:
            return cached.decode()
            
        # Translate and cache
        result = self.alia.translate_medical(text)
        self.cache.setex(key, 3600, result)
        return result
```

---

## Comparison with Current Options

### Translation Quality (Expected)

| Metric | LibreTranslate | OPUS-MT | OpenAI GPT-4 | ALIA-40b |
|--------|---------------|---------|--------------|----------|
| General Spanish→English | 85% | 87% | 94% | 92% |
| Mexican medical terms | 65% | 67% | 82% | 90%* |
| IMSS terminology | 60% | 62% | 78% | 88%* |
| Speed (pages/min) | 15 | 20 | 5 | 12 |
| Cost per 1000 pages | $0 | $0 | $100 | $0** |

*After fine-tuning on Mexican medical data
**After initial hardware investment

### ROI Analysis
- **Hardware Cost**: ~$20,000 (2x RTX 4090) or cloud GPU ~$2/hour
- **Break-even**: 200,000 pages vs OpenAI API
- **Additional Benefits**: 
  - Data sovereignty
  - HIPAA compliance without BAA
  - Customization capability
  - No rate limits

---

## Fine-Tuning for Mexican Medical

### Future Enhancement (Month 2-3)
```python
from transformers import TrainingArguments, Trainer

# Prepare Mexican medical dataset
dataset = load_dataset("imss_medical_records")  # After creating

# LoRA fine-tuning for efficiency
from peft import LoraConfig, get_peft_model

peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.1,
)

model = get_peft_model(model, peft_config)
```

---

## Migration Path

### Phase 1: Parallel Testing (Week 1)
- Deploy ALIA-40b alongside LibreTranslate
- A/B test translations
- Measure quality and speed

### Phase 2: Primary with Fallback (Week 2-3)
- ALIA-40b as primary translator
- LibreTranslate as fallback
- Monitor performance

### Phase 3: Full Migration (Week 4)
- ALIA-40b only
- Decommission LibreTranslate
- Begin fine-tuning prep

---

## Risk Assessment

### Challenges
1. **Memory Requirements**: 40B model needs significant VRAM
   - **Mitigation**: Use quantization, tensor parallelism
   
2. **Inference Speed**: Might be slower than smaller models
   - **Mitigation**: vLLM optimization, batching
   
3. **Spanish Dialect**: Trained on Iberian Spanish primarily
   - **Mitigation**: Fine-tune on Mexican medical corpus

4. **No Medical Specialization**: General-purpose model
   - **Mitigation**: Prompt engineering, future fine-tuning

---

## Recommendation

### ✅ **YES - Deploy ALIA-40b with vLLM**

**Rationale:**
1. **Superior Spanish Understanding**: Native Spanish training beats translation APIs
2. **On-Premise Control**: Full HIPAA compliance without external dependencies
3. **Cost Effective**: One-time hardware cost vs ongoing API fees
4. **Future-Proof**: Can fine-tune for Mexican medical specifics
5. **ChatPS Synergy**: Leverages existing GPU infrastructure

### Immediate Actions
1. Check if BSC-LT has quantized versions available
2. Test with small RTX 4090 setup first
3. Benchmark against current LibreTranslate output
4. Plan for vLLM deployment on ChatPS infrastructure

---

## Commands to Start Testing

```bash
# Quick test with transformers (development)
pip install transformers accelerate bitsandbytes

# Python test script
cat > test_alia.py << 'EOF'
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Load quantized for testing
model = AutoModelForCausalLM.from_pretrained(
    "BSC-LT/ALIA-40b",
    device_map="auto",
    load_in_4bit=True
)
tokenizer = AutoTokenizer.from_pretrained("BSC-LT/ALIA-40b")

text = "El paciente presenta hipertensión arterial sistémica"
inputs = tokenizer(f"Translate to English: {text}", return_tensors="pt")
outputs = model.generate(**inputs, max_length=100)
print(tokenizer.decode(outputs[0]))
EOF

python test_alia.py
```

---

*Last Updated: 2025-09-05*
*Status: Ready for testing*
*Integration: Compatible with ChatPS_v2_ng GPU infrastructure*