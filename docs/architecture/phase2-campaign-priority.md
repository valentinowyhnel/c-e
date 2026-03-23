# Cortex Phase 2 - Campaign Memory and Priority Engine V2

## Objectif

La phase 2 ajoute deux services d'analyse non decisifs:

- `cortex-campaign-memory` pour detecter les campagnes low-and-slow sur 24h, 7j, 30j et 90j
- `cortex-priority-engine` pour router les dossiers vers `fast_path`, `hybrid_analysis`, `deep_graph_reasoning` ou `sentinel_immediate_attention`

## Alignement Cortex

- aucun des deux services ne prend la decision finale
- `campaign_likelihood` et `priority_v2` restent des signaux explicables
- Policy Engine garde l'autorite sur les actions critiques

## Flux

1. Des evenements faibles sont stockes dans la campaign memory.
2. Une evaluation produit:
   - `progressive_deviation_score`
   - `campaign_likelihood_score`
   - `evidence[]`
3. Le Priority Engine combine:
   - anomaly
   - novelty
   - trust inverse
   - graph expansion
   - asset criticality
   - campaign likelihood
4. Le route hint alimente ensuite les couches Trust, Graph et Sentinel.
