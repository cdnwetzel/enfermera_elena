#!/bin/bash
# ALIA-40b Deployment Script with vLLM
# Optimized for Enfermera Elena medical translation

set -e

echo "========================================="
echo "ALIA-40b vLLM Deployment for Enfermera Elena"
echo "========================================="

# Configuration
MODEL_NAME="BSC-LT/ALIA-40b"
MODEL_DIR="/home/psadmin/ai/enfermera_elena/models/alia-40b"
VLLM_PORT=8504
CACHE_DIR="/home/psadmin/.cache/huggingface"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check GPU availability
check_gpu() {
    echo -e "${YELLOW}Checking GPU resources...${NC}"
    
    if ! command -v nvidia-smi &> /dev/null; then
        echo -e "${RED}nvidia-smi not found. Please install NVIDIA drivers.${NC}"
        exit 1
    fi
    
    nvidia-smi
    
    # Get total VRAM
    TOTAL_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | awk '{sum+=$1} END {print sum}')
    echo -e "${GREEN}Total VRAM available: ${TOTAL_VRAM} MB${NC}"
    
    if [ "$TOTAL_VRAM" -lt 40000 ]; then
        echo -e "${YELLOW}Warning: Less than 40GB VRAM detected.${NC}"
        echo "Will use quantization for deployment."
        USE_QUANTIZATION=true
    else
        echo -e "${GREEN}Sufficient VRAM for full precision model.${NC}"
        USE_QUANTIZATION=false
    fi
    
    # Count GPUs
    GPU_COUNT=$(nvidia-smi --query-gpu=count --format=csv,noheader | head -1)
    echo -e "${GREEN}Number of GPUs: ${GPU_COUNT}${NC}"
}

# Install vLLM and dependencies
install_vllm() {
    echo -e "${YELLOW}Installing vLLM and dependencies...${NC}"
    
    # Check Python version
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc) -eq 1 ]]; then
        echo -e "${RED}Python 3.8+ required. Current version: $PYTHON_VERSION${NC}"
        exit 1
    fi
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "../venv_alia" ]; then
        python3 -m venv ../venv_alia
    fi
    
    source ../venv_alia/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install vLLM with CUDA support
    pip install vllm
    
    # Install flash attention for better performance (optional)
    pip install flash-attn --no-build-isolation || echo "Flash attention optional, continuing..."
    
    # Install other dependencies
    pip install transformers accelerate sentencepiece protobuf
    
    echo -e "${GREEN}vLLM installation complete.${NC}"
}

# Download or check model
download_model() {
    echo -e "${YELLOW}Checking model availability...${NC}"
    
    if [ -d "$MODEL_DIR" ] && [ "$(ls -A $MODEL_DIR)" ]; then
        echo -e "${GREEN}Model already downloaded at $MODEL_DIR${NC}"
        return 0
    fi
    
    echo "Model not found locally. Checking HuggingFace..."
    
    # Create model directory
    mkdir -p "$MODEL_DIR"
    
    # Check if quantized version is available
    python3 << EOF
from huggingface_hub import list_models, snapshot_download
import sys

# Check for quantized versions
models = list(list_models(search="ALIA-40b"))
quantized_versions = [m for m in models if 'gptq' in m.modelId.lower() or 'gguf' in m.modelId.lower()]

if quantized_versions:
    print(f"Found quantized versions: {[m.modelId for m in quantized_versions]}")
    model_to_download = quantized_versions[0].modelId
else:
    print("No quantized version found, will use full model with quantization")
    model_to_download = "$MODEL_NAME"

print(f"Downloading {model_to_download}...")
try:
    snapshot_download(
        repo_id=model_to_download,
        local_dir="$MODEL_DIR",
        cache_dir="$CACHE_DIR",
        resume_download=True
    )
    print("Download complete!")
except Exception as e:
    print(f"Error downloading model: {e}")
    sys.exit(1)
EOF
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Model download failed.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Model ready at $MODEL_DIR${NC}"
}

# Create vLLM service configuration
create_service() {
    echo -e "${YELLOW}Creating systemd service...${NC}"
    
    # Determine tensor parallel size based on GPU count
    if [ "$GPU_COUNT" -gt 1 ]; then
        TENSOR_PARALLEL_SIZE=$GPU_COUNT
    else
        TENSOR_PARALLEL_SIZE=1
    fi
    
    # Create service file
    cat << EOF | sudo tee /etc/systemd/system/alia-vllm.service
[Unit]
Description=ALIA-40b vLLM Server for Enfermera Elena
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/psadmin/ai/enfermera_elena
Environment="PATH=/home/psadmin/ai/enfermera_elena/venv_alia/bin:/usr/local/bin:/usr/bin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0,1"
ExecStart=/home/psadmin/ai/enfermera_elena/venv_alia/bin/python -m vllm.entrypoints.openai.api_server \
    --model $MODEL_DIR \
    --tensor-parallel-size $TENSOR_PARALLEL_SIZE \
    --dtype float16 \
    --max-model-len 4096 \
    --port $VLLM_PORT \
    --trust-remote-code \
    $(if [ "$USE_QUANTIZATION" = true ]; then echo "--quantization gptq"; fi)
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    echo -e "${GREEN}Service created: alia-vllm.service${NC}"
}

# Create nginx reverse proxy configuration
create_nginx_config() {
    echo -e "${YELLOW}Creating nginx configuration...${NC}"
    
    cat << EOF | sudo tee /etc/nginx/sites-available/alia-vllm
server {
    listen 8505 ssl;
    server_name localhost;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:$VLLM_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts for long-running requests
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
        
        # WebSocket support for streaming
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
    
    # Enable site if nginx is installed
    if command -v nginx &> /dev/null; then
        sudo ln -sf /etc/nginx/sites-available/alia-vllm /etc/nginx/sites-enabled/
        sudo nginx -t && sudo systemctl reload nginx
        echo -e "${GREEN}Nginx configured for ALIA vLLM on port 8505 (HTTPS)${NC}"
    else
        echo -e "${YELLOW}Nginx not installed. Skipping reverse proxy setup.${NC}"
    fi
}

# Test the deployment
test_deployment() {
    echo -e "${YELLOW}Testing ALIA deployment...${NC}"
    
    # Wait for service to be ready
    echo "Waiting for vLLM server to start..."
    sleep 10
    
    # Test with curl
    python3 << 'EOF'
import requests
import json

url = "http://localhost:8504/v1/chat/completions"
test_text = "Translate to English: El paciente presenta hipertensión arterial controlada"

payload = {
    "model": "ALIA-40b",
    "messages": [
        {"role": "user", "content": test_text}
    ],
    "temperature": 0.3,
    "max_tokens": 100
}

try:
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Test successful!")
        print(f"Translation: {result['choices'][0]['message']['content']}")
    else:
        print(f"❌ Test failed with status {response.status_code}")
        print(response.text)
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to vLLM server. Make sure it's running.")
except Exception as e:
    print(f"❌ Test error: {e}")
EOF
}

# Main deployment flow
main() {
    echo -e "${GREEN}Starting ALIA-40b deployment...${NC}"
    
    # Check prerequisites
    check_gpu
    
    # Install vLLM
    install_vllm
    
    # Download model
    download_model
    
    # Create service
    create_service
    
    # Create nginx config
    create_nginx_config
    
    # Start service
    echo -e "${YELLOW}Starting vLLM service...${NC}"
    sudo systemctl enable alia-vllm
    sudo systemctl start alia-vllm
    
    # Show status
    sudo systemctl status alia-vllm --no-pager
    
    # Test deployment
    test_deployment
    
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}ALIA-40b Deployment Complete!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo "Service: alia-vllm.service"
    echo "API Endpoint: http://localhost:$VLLM_PORT"
    echo "HTTPS Endpoint: https://localhost:8505 (if nginx configured)"
    echo ""
    echo "Commands:"
    echo "  Start:   sudo systemctl start alia-vllm"
    echo "  Stop:    sudo systemctl stop alia-vllm"
    echo "  Status:  sudo systemctl status alia-vllm"
    echo "  Logs:    sudo journalctl -u alia-vllm -f"
    echo ""
    echo "Test with:"
    echo "  curl http://localhost:$VLLM_PORT/v1/models"
    echo ""
}

# Handle command line arguments
case "${1:-}" in
    install)
        install_vllm
        ;;
    download)
        download_model
        ;;
    service)
        create_service
        ;;
    test)
        test_deployment
        ;;
    stop)
        sudo systemctl stop alia-vllm
        echo "Service stopped"
        ;;
    start)
        sudo systemctl start alia-vllm
        echo "Service started"
        ;;
    status)
        sudo systemctl status alia-vllm
        ;;
    logs)
        sudo journalctl -u alia-vllm -f
        ;;
    *)
        main
        ;;
esac