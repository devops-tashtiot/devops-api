FROM python:3.10-slim

# kubectl is required by app/v1/argocd/operations.py's _check_cluster_permissions(), which
# shells out to `kubectl auth can-i` to validate a caller-supplied cluster token before
# creating a cluster-secret Application. Pinned to the minikube-on-EC2 cluster's own server
# version (v1.35.1) rather than "stable" for reproducible builds.
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client curl \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.35.1/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

WORKDIR /
COPY /app /app

CMD ["python","-m","app.main","--host","0.0.0.0","--port","5000"]
