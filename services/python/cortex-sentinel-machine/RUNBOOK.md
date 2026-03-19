# RUNBOOK Sentinel Machine

## Objectif

Sentinel Machine continue de détecter localement même si Cortex est indisponible, mais n’exécute jamais d’action critique nouvelle sans approbation Cortex signée.

## Démarrage

```bash
cd services/python/cortex-sentinel-machine
python -m pip install -e .
python -m app.main
python -m app.serve
```

## Vérifications opératoires

1. Vérifier que la queue locale WAL chiffrée grossit puis se vide côté pipeline de reprise.
2. Vérifier que le fichier `state/audit.log` reçoit les décisions de sécurité.
3. Vérifier que les manifests de modèles shadow contiennent `feature_schema_hash`, `tenant_scope` et `rollback_pointer`.
4. Vérifier qu’un bundle policy non signé est refusé.
5. Vérifier qu’un update rejoué ou extrême est mis en quarantaine.
6. Vérifier que `/health` et `/metrics` refusent les requêtes sans token.
7. En mode `mtls`, vérifier que le service refuse de démarrer si `server.crt`, `server.key` ou `ca.crt` manquent.
8. Vérifier que les appels vers `cortex-trust-engine` et `cortex-model-orchestrator` portent bien `x-cortex-internal-token`.
9. Vérifier que si NATS est indisponible, la WAL garde les enregistrements en `pending`.
10. Vérifier qu'au retour de NATS, `flush_pending` vide la file locale sans perdre `event_id` ni `trace_id`.
11. Vérifier que `cortex.sentinel.commands` accepte uniquement les commandes ciblant `machine_id` local ou `*`.

## Réponse à incident

1. Si `backpressure_queue_depth` dépasse le seuil, passer en mode collecte minimale et forcer le flush des événements critiques.
2. Si `hard_drift` persiste, geler toute promotion locale et conserver le champion précédent.
3. Si `machine_compromised` est levé, refuser les uploads de modèles et émettre un audit immédiat.
4. Si un rollback est requis, restaurer le `rollback_pointer` du champion et repasser le challenger en shadow.

## Commandes de test

```bash
cd services/python/cortex-sentinel-machine
pytest tests/unit
pytest tests/integration
pytest tests/adversarial
pytest tests/performance
```

## Checklist critique

- PASS si aucun modèle non signé n’est accepté.
- PASS si aucune promotion n’arrive sans patience ni approval signée.
- PASS si la redaction locale supprime secrets et identifiants directs.
- FAIL si une seule machine peut imposer une nouvelle normalité globale.
- FAIL si une action destructive est déclenchée localement sans garde-fou Cortex.

## Validation cluster

Pour la validation Kubernetes/Helm/SPIRE/NATS en environnement Cortex, utiliser aussi:

- `docs/SENTINEL_MACHINE_CLUSTER_RUNBOOK.md`
- `docs/SENTINEL_MACHINE_PASS_FAIL.md`
- `scripts/validate-sentinel-machine.sh`
