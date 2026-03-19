# Cortex v2 Contract

Ce depot suit une construction par phases avec gates binaires.

## Regles absolues

1. Gate FAILED = rester dans la phase.
2. LLM jamais dans le chemin critique auth/authz.
3. Sentinel valide chaque appel MCP.
4. Dry-run obligatoire avant toute action irreversible.
5. Fail-closed partout.
6. Zero secret en variable d'environnement en cible produit.
7. Audit event sur chaque decision de securite.
8. Versions epinglees, pas de `latest`.

## Phases

- Phase 0: environnement local reproductible
- Phase 1: fondations securite
- Phase 2: identite de base
- Phase 3: enforcement
- Phase 4: multi-agents
- Phase 5: frontend pro
- Phase 6: production
- Phase 7: go-to-market

## Cible repo

```text
cortex/
  .github/workflows/
  proto/
  services/
  helm/
  infra/
  policies/
  scripts/
  tests/
```
