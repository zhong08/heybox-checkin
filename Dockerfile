FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Shanghai
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && mkdir logs
COPY main.py heybox.py native_sign.py notify.py config.py utils.py login.py ./
COPY signer/ signer/
COPY THIRD_PARTY_LICENSES.txt ./
CMD ["python", "main.py"]
