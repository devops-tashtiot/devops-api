FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

WORKDIR /
COPY /app /app

CMD ["python","-m","app.main","--host","0.0.0.0","--port","5000"]
