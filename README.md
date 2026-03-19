# Cortex

Plateforme de sécurité orientée décision, observation, confiance et orchestration, construite par phases avec gates binaires.

## Structure

```text
cortex/
  proto/
  services/
  helm/
  infra/
  policies/
  scripts/
  tests/
```

## Composants principaux

- `services/cortex-auth`: contrôle d'accès et capacités.
- `services/cortex-gateway`: surface API et ingress internes.
- `services/cortex-trust-engine`: calcul de confiance et scoring.
- `services/cortex-orchestrator`: gouvernance et promotion de modèles.
- `services/cortex-sentinel`: agent Sentinel historique.
- `services/python/cortex-sentinel-machine`: agent endpoint de nouvelle génération.
- `services/cortex-console`: console opérateur.

## Sentinel Machine

Le service `services/python/cortex-sentinel-machine` fournit:

- collecte endpoint locale avec redaction,
- scoring temps réel et détection de drift,
- shadow training, promotion contrôlée et rollback,
- transport gRPC/mTLS, NATS JetStream, WAL locale,
- intégration Gateway, Trust Engine et Orchestrator,
- chart Helm et runbooks d'exploitation.

## Démarrage

Les scripts de bootstrap se trouvent dans `scripts/`.

Exemples:

```bash
scripts/setup-env.sh
scripts/setup-cluster.sh
scripts/setup-agents.sh
scripts/validate-sentinel-machine.sh
```

## Références

- `AGENTS.md`: contraintes d'exécution pour les agents.
- `BLACKEVOUPAPER.md`: cible fonctionnelle et d'architecture.
- `docs/`: runbooks, architecture et checklists.
