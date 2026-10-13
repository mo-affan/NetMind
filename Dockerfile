# NetMind in a container: dashboard on :8501, API on :8000
#   docker build -t netmind .
#   docker run -p 8501:8501 netmind                         # dashboard
#   docker run -p 8000:8000 netmind python -m netmind api --host 0.0.0.0
# Live capture inside Docker needs: --net=host --cap-add=NET_RAW --cap-add=NET_ADMIN
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpcap0.8 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m netmind demo --save-pcap ""
EXPOSE 8501 8000
ENV ANTHROPIC_API_KEY=""
CMD ["python", "-m", "streamlit", "run", "netmind/dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
