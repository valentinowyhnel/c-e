# Runbook - Low and Slow Phase 2

## Verification rapide

```bash
kubectl get deploy -n cortex-system cortex-campaign-memory cortex-priority-engine
kubectl port-forward -n cortex-system svc/cortex-campaign-memory 8089:8080
kubectl port-forward -n cortex-system svc/cortex-priority-engine 8090:8080
curl http://127.0.0.1:8089/health/ready
curl http://127.0.0.1:8090/health/ready
```

## Sequence de test

1. Injecter plusieurs weak signals espaces sur 30 jours.
2. Evaluer `campaign_likelihood`.
3. Evaluer `priority_v2`.
4. Verifier que les cas crown jewel restent bloques par Policy Engine via `approval_required`.

## Symptomes de rollback

- `campaign_likelihood_score` reste a zero malgre accumulation evidente
- `priority_v2` ne route jamais vers `deep_graph_reasoning`
- hausse anormale de routes profondes sans support de campagne
