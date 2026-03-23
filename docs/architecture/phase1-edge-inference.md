# Cortex Phase 1 - Edge Trust Inference

## Objectif

`cortex-edge-inference` ajoute une couche d'inference d'entree reseau quand l'equipement edge reel n'est pas directement observe. Le service ne prend jamais la decision finale. Il produit un signal explicable, infere, versionne et trace, puis le transmet au `cortex-trust-engine`.

## Flux

1. Un appel `POST /v1/edge/infer` arrive avec contexte d'auth, chemin reseau, reputation IP et signaux de session.
2. Le service calcule `EdgeRiskSignal` avec `inferred=true`, `confidence`, `evidence[]`, `trace_id` et `route_hint`.
3. Le service ecrit un evenement d'audit immuable dans `cortex-audit`.
4. Si `EDGE_INFERENCE_SHADOW_MODE=false`, il transmet un `SecurityEvidence` structure au `cortex-trust-engine`.
5. Le Trust Engine reste la source de score final avant evaluation Policy Engine.

## Garde-fous

- Feature flags:
  - `EDGE_INFERENCE_ENABLED`
  - `EDGE_INFERENCE_SHADOW_MODE`
- Fail-closed:
  - si l'audit est requis et indisponible, la requete echoue
  - si le forward Trust est requis et indisponible, la requete echoue
- Aucun fait infere n'est presente comme certitude:
  - `signal=inferred`
  - `evidence` explique les limites

## Sante et observabilite

- `/health/live`
- `/health/ready`
- `/health/startup`
- `/metrics`
- `/version`

La readiness verifie `cortex-audit` et `cortex-trust-engine` quand ces dependances sont marquees critiques par configuration.
