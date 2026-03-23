# Runbook - Cortex Edge Trust Inference

## Verification rapide

```bash
kubectl get deploy -n cortex-system cortex-edge-inference
kubectl get pods -n cortex-system -l app.kubernetes.io/name=cortex-edge-inference
kubectl port-forward -n cortex-system svc/cortex-edge-inference 8088:8080
curl http://127.0.0.1:8088/health/live
curl http://127.0.0.1:8088/health/ready
curl http://127.0.0.1:8088/version
curl http://127.0.0.1:8088/metrics
```

## Test fonctionnel local

```bash
curl -X POST http://127.0.0.1:8088/v1/edge/infer \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id":"sess-apt-1",
    "entity_id":"user-apt-1",
    "trace_id":"trace-apt-1",
    "context":{
      "ip_reputation":82,
      "geo_consistency":0.2,
      "device_fingerprint_present":false,
      "path_anomaly_score":78,
      "transport_risk":65,
      "vpn_or_proxy_detected":true
    }
  }'
```

## Conditions de rollback

- erreurs 503 repetitives sur `/v1/edge/infer`
- audit indisponible
- trust forward degrade sans shadow mode
- hausse anormale des rejets sur ressources critiques

## Rollback

```bash
helm rollback cortex-edge-inference -n cortex-system
```

## Mode securise

Pour couper l'impact runtime sans retirer le pod:

```bash
kubectl set env deployment/cortex-edge-inference -n cortex-system EDGE_INFERENCE_ENABLED=false
```
