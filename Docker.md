# Docker Build & Push

Image: `yourusername/finance-rag` (Docker Hub, public — no pull secret needed by the cluster).

## Before you build

Secrets are injected at runtime by k8s (`finance-rag-secret`), **not** baked into the image. `.dockerignore` already excludes `.env`, `.env.*`, and `storage/documents`, so a normal build is safe — just never `COPY` a real `.env` into the image.

## Versioning

Bump the tag every time the code changes. Match it in `05-app.yaml` (two refs: the `migrate` init container and the app container).

Current: `v0.1.5`

## Build

```bash
cd ~/Downloads/Books/code/finance_rag
docker build -t yourusername/finance-rag:v0.1.5 .
```

## Push

```bash
docker login            # once, if not already logged in
docker push yourusername/finance-rag:v0.1.5
```

## Deploy

```bash
kubectl --kubeconfig ~/.kube/contabo-config apply -f ~/Desktop/kbctl/finance-rag-k8s/05-app.yaml
kubectl --kubeconfig ~/.kube/contabo-config -n finance-rag rollout restart deployment/finance-rag
```

## Image internals

- `FROM python:3.14-slim`, `uv` as the package manager.
- Layer-cached: `pyproject.toml` + `uv.lock` copied and synced first, source copied after.
- Entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
