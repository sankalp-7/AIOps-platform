#!/usr/bin/env bash

set -euo pipefail

SERVICE="${1:?Usage: $0 <service> [delay]}"
DELAY="${2:-2s}"
NAMESPACE="otel-demo"

echo "Injecting ${DELAY} latency into traffic targeting ${SERVICE}"

# Make sure only one experimental fault is active.
kubectl delete virtualservice \
  -n "${NAMESPACE}" \
  -l aiops-fault=delay \
  --ignore-not-found >/dev/null 2>&1 || true

cat <<EOF | kubectl apply -f -
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: aiops-delay-${SERVICE}
  namespace: ${NAMESPACE}
  labels:
    aiops-fault: delay
    aiops-target: ${SERVICE}
spec:
  hosts:
  - ${SERVICE}.${NAMESPACE}.svc.cluster.local

  http:
  - fault:
      delay:
        percentage:
          value: 100
        fixedDelay: ${DELAY}

    route:
    - destination:
        host: ${SERVICE}.${NAMESPACE}.svc.cluster.local
EOF

echo
echo "Fault active:"
kubectl get virtualservice \
  aiops-delay-${SERVICE} \
  -n "${NAMESPACE}"