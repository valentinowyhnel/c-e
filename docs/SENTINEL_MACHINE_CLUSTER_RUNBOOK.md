# Runbook Cluster Sentinel Machine

## Objectif

Valider que `cortex-sentinel-machine` est correctement déployé dans le cluster Cortex, qu’il est câblé à NATS, au Trust Engine, au Gateway et à l’Orchestrator, et qu’il reste fail-safe si un composant manque.

## Pré-requis

- cluster `cortex-dev` accessible via `kubectl`
- chart `helm/cortex-sentinel-machine` déployé
- entrée SPIRE enregistrée pour `cortex-sentinel-machine`
- images `cortex/cortex-sentinel-machine:dev`, `cortex/cortex-gateway:dev`, `cortex/cortex-orchestrator:dev` chargées

## Déploiement

```bash
bash scripts/register-spire-entries.sh
bash scripts/setup-agents.sh
```

## Validation rapide

```bash
bash scripts/validate-sentinel-machine.sh
```

## Vérifications obligatoires

1. `daemonset/cortex-sentinel-machine` est `Available` sur les nœuds ciblés.
2. Le service `cortex-sentinel-machine` expose `50061` et `18080`.
3. Les variables d’environnement suivantes sont présentes dans le pod:
   - `NATS_URL`
   - `SENTINEL_CORTEX_INGEST_URL`
   - `SENTINEL_CORTEX_TRUST_URL`
   - `SENTINEL_CORTEX_MODEL_URL`
   - `SENTINEL_ENABLE_NATS_BUS`
4. `/health` répond avec le bearer token d’observabilité.
5. Le répertoire `/var/lib/cortex/sentinel-machine` existe et contient la WAL/état local.
6. Les logs ne montrent ni boucle de crash, ni refus de policy signée, ni erreur de queue chiffrée.

## Vérifications de connectivité

Depuis un pod `cortex-sentinel-machine`:

```bash
wget -qO- http://cortex-gateway:8080/health
wget -qO- http://cortex-trust-engine:8080/health
wget -qO- http://cortex-orchestrator:8080/health
```

Si `SENTINEL_ENABLE_NATS_BUS=1`, vérifier aussi:

```bash
printenv NATS_URL
```

et consulter les logs pour confirmer que le bus NATS est actif sans erreurs de connexion répétées.

## Vérification fonctionnelle minimale

1. Générer une activité locale normale sur un nœud.
2. Vérifier que la WAL locale se remplit ou se vide selon la disponibilité NATS.
3. Vérifier qu’un événement est accepté par `POST /v1/sentinel/events`.
4. Vérifier qu’un appel Trust est observé vers `POST /trust/evaluate/v2`.
5. Vérifier qu’un modèle shadow valide peut être soumis à `POST /v1/model/promote`.

## Vérification du bus de commandes

Quand NATS/JetStream est disponible:

1. Publier une commande sur `cortex.sentinel.commands`.
2. Utiliser `flush_pending` pour vider la WAL.
3. Vérifier que la profondeur de file diminue sans perte d’intégrité.

## Conditions PASS

- pods stables
- health observability OK
- variables d’environnement de control plane présentes
- WAL locale accessible
- aucun refus inattendu de manifest ou de policy
- connectivité HTTP inter-services OK
- commandes NATS supportées si le bus est activé

## Conditions FAIL

- pod en crash loop
- `/health` inaccessible
- WAL absente ou corrompue
- NATS en erreur répétée alors qu’il est requis
- endpoint Cortex cible non joignable
- entrée SPIRE/service account incohérents

## Remédiation rapide

- si NATS est absent: mettre `SENTINEL_ENABLE_NATS_BUS=0` temporairement et valider la WAL locale
- si SPIRE est incohérent: rejouer `scripts/register-spire-entries.sh`
- si le chart n’est pas appliqué: relancer `helm upgrade --install cortex-sentinel-machine helm/cortex-sentinel-machine -n cortex-system`
- si Gateway/Trust/Orchestrator ne répondent pas: valider les déploiements correspondants avant de conclure sur Sentinel Machine

