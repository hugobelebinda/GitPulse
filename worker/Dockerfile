FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng cmake g++ make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF" \
    FORCE_CMAKE=1
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 \
    SUMMARY_MODEL=bartowski/Qwen2.5-7B-Instruct-GGUF \
    SUMMARY_MODEL_FILE=Qwen2.5-7B-Instruct-Q4_K_M.gguf \
    NER_DEVICE=cpu

RUN python -c "import os; from huggingface_hub import hf_hub_download; hf_hub_download(repo_id=os.environ['SUMMARY_MODEL'], filename=os.environ['SUMMARY_MODEL_FILE'])"

COPY omnidoc_worker ./omnidoc_worker

CMD ["python", "-m", "omnidoc_worker"]
