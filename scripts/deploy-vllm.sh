#!/bin/bash
set -euo pipefail

echo "=== Deploy vLLM CPU in Kind ==="

AVAIL=$(free -m | awk '/^Mem:/ {print $7}')
echo "Available RAM: ${AVAIL}Mi"

if [ "$AVAIL" -lt "3000" ]; then
  echo "ERROR: at least 3000Mi free RAM required for Phi-3 Mini"
  exit 1
fi

kubectl create namespace cortex-system --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vllm-models-pvc
  namespace: cortex-system
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 15Gi
EOF

docker build -t cortex/cortex-vllm:dev services/cortex-vllm
kind load docker-image cortex/cortex-vllm:dev --name cortex-dev

helm upgrade --install cortex-vllm helm/cortex-vllm \
  --namespace cortex-system \
  --wait --timeout=180s

kubectl get pods -n cortex-system -l app.kubernetes.io/part-of=vllm
