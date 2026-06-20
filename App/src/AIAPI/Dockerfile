FROM ubuntu:22.04

WORKDIR /app

# Cài đặt Python và các công cụ cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt PyTorch bản CPU và các dependencies khác
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn ứng dụng
COPY main.py .
COPY api/ api/
COPY core/ core/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]