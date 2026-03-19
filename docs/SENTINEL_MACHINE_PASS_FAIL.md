# Sentinel Machine PASS/FAIL

## PASS

- `cortex-sentinel-machine` déployé en `DaemonSet`
- service account dédié présent
- entrée SPIRE correspondante enregistrée
- observabilité tokenisée répond
- bus NATS optionnel fonctionnel ou désactivé explicitement
- WAL locale persistante présente
- appels vers Gateway, Trust Engine et Orchestrator possibles
- commandes `cortex.sentinel.commands` opérationnelles si NATS actif

## FAIL

- chart non déployé
- pods non prêts
- service ou ports absents
- variables de câblage control plane manquantes
- NATS exigé mais inaccessible sans fallback observé
- incohérence entre service account et identité SPIFFE
- promotions modèles acceptées sans manifest valide
- queue locale non vidable après retour du bus
