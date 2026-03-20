# Cortex

Plateforme de securite orientee decision, observation, confiance et orchestration, construite par phases avec gates binaires.

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

- `services/cortex-auth`: controle d'acces et capacites.
- `services/cortex-gateway`: surface API et ingress internes.
- `services/cortex-trust-engine`: calcul de confiance et scoring.
- `services/cortex-orchestrator`: gouvernance et promotion de modeles.
- `services/cortex-sentinel`: agent Sentinel historique.
- `services/python/cortex-sentinel-machine`: agent endpoint de nouvelle generation.
- `services/cortex-console`: console operateur.

## Sentinel Machine

Le service `services/python/cortex-sentinel-machine` fournit:

- collecte endpoint locale avec redaction,
- scoring temps reel et detection de drift,
- shadow training, promotion controlee et rollback,
- transport gRPC/mTLS, NATS JetStream, WAL locale,
- integration Gateway, Trust Engine et Orchestrator,
- chart Helm et runbooks d'exploitation.

## Demarrage

Les scripts de bootstrap se trouvent dans `scripts/`.

Exemples:

```bash
scripts/setup-env.sh
scripts/setup-cluster.sh
scripts/setup-agents.sh
scripts/validate-sentinel-machine.sh
```

## Installation Ubuntu

Pour une VM Ubuntu classique:

```bash
chmod +x scripts/install-cortex-ubuntu.sh
bash scripts/install-cortex-ubuntu.sh
```

Pour une VM Ubuntu contrainte `8 Go RAM / 4 CPU`:

```bash
chmod +x scripts/install-cortex-ubuntu-lean.sh
bash scripts/install-cortex-ubuntu-lean.sh
```

Documentation associee:

- `docs/UBUNTU_VM_INSTALL.md`
- `docs/UBUNTU_VM_LEAN_INSTALL.md`
- `docs/GITHUB_EPHEMERAL_RUNNER.md`

## References

- `AGENTS.md`: contraintes d'execution pour les agents.
- `BLACKEVOUPAPER.md`: cible fonctionnelle et d'architecture.
- `docs/`: runbooks, architecture et checklists.
