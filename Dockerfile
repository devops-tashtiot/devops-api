FROM python:3.10-slim

# kubectl is required by app/v1/argocd/operations.py's _check_cluster_permissions(), which
# shells out to `kubectl auth can-i` to validate a caller-supplied cluster token before
# creating a cluster-secret Application. Pinned to the minikube-on-EC2 cluster's own server
# version (v1.35.1) rather than "stable" for reproducible builds.
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client curl ca-certificates \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.35.1/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

# Cloudflare Origin CA root cert (RSA) — trusted so devops-api's own httpx-based calls to
# *.devopstashtiot.page pass real TLS verification. These calls resolve in-cluster via a
# CoreDNS rewrite straight to ingress-nginx-controller (bypassing the Cloudflare Tunnel and
# Access's email-OTP wall, which would otherwise block any programmatic request), and
# ingress-nginx-controller presents a real Cloudflare Origin Certificate for
# *.devopstashtiot.page — signed by Cloudflare's own private Origin CA, which isn't in any
# standard trust store. Source (public, stable):
# https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/
# Added to both the system trust store (update-ca-certificates, for kubectl/git/curl) and
# certifi's bundle (for httpx, which uses certifi.where() by default — NOT the system store).
COPY cloudflare-origin-ca-rsa-root.pem /usr/local/share/ca-certificates/cloudflare-origin-ca-rsa-root.crt
RUN update-ca-certificates

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt \
    && cat /usr/local/share/ca-certificates/cloudflare-origin-ca-rsa-root.crt >> "$(python -c 'import certifi; print(certifi.where())')"

WORKDIR /
COPY /app /app

CMD ["python","-m","app.main","--host","0.0.0.0","--port","5000"]
