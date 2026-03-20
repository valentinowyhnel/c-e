# Cortex Sizing Reference

## Objectif

Donner une estimation réaliste des ressources nécessaires pour faire tourner Cortex selon trois modes:

- laboratoire contraint
- démo/dev confortable
- mono-machine renforcée

Ce document est volontairement pragmatique. Ce ne sont pas des promesses de performance. Ce sont des ordres de grandeur pour éviter de sous-dimensionner la machine.

## Résumé rapide

| Profil | RAM | CPU | Disque | Verdict |
|---|---:|---:|---:|---|
| Contraint | 8 Go | 4 vCPU | 120 Go SSD | Démarre en mode réduit, peu de marge |
| Réaliste | 16 Go | 8 vCPU | 150 Go SSD | Première base correcte |
| Confort | 32 Go | 8-12 vCPU | 200 Go NVMe | Recommandé en mono-machine |

## Verdict par profil

### 1. Profil contraint

- `8 Go RAM`
- `4 vCPU`
- `120 Go SSD`

Ce profil permet:

- cluster local `kind`
- backend Cortex réduit
- console frontend
- Sentinel / Sentinel Machine
- Gateway / Trust / Graph / Audit / Approval / OPA / Envoy / NATS

Ce profil n'est pas adapté à:

- `vLLM` local stable
- forte parallélisation
- builds Docker répétés sans lenteur
- observabilité lourde
- plusieurs replicas

### 2. Profil réaliste

- `16 Go RAM`
- `8 vCPU`
- `150 Go SSD`

Ce profil permet:

- backend complet avec marge
- console stable
- rebuilds corrects
- agents plus utilisables
- NATS, Postgres, Neo4j, OTel plus sereins

### 3. Profil confort mono-machine

- `32 Go RAM`
- `8 à 12 vCPU`
- `200 Go SSD/NVMe`

Ce profil est recommandé si tu veux:

- une stack complète mono-machine
- moins de contention Docker/Kubernetes
- observabilité plus riche
- quelques replicas
- intégration et démo sérieuses

## Référence par composant

Les chiffres ci-dessous sont des budgets réalistes pour une instance unique, pas des limites exactes.

| Composant | RAM mini | RAM conseillée | CPU mini | CPU conseillé | Notes |
|---|---:|---:|---:|---:|---|
| `kind` + kube-system + Calico | 700 Mo | 1.5 Go | 0.5 | 1 | Coût incompressible du cluster local |
| `cortex-auth` | 100 Mo | 200 Mo | 0.2 | 0.5 | Léger, surtout CPU faible |
| `cortex-sync` | 100 Mo | 200 Mo | 0.2 | 0.5 | Peu coûteux hors gros flux |
| `cortex-gateway` | 150 Mo | 300 Mo | 0.3 | 1 | Monte avec `ext_authz` et trafic |
| `cortex-graph` | 150 Mo | 300 Mo | 0.3 | 1 | Léger côté API, lourd côté Neo4j |
| `Neo4j` | 1.5 Go | 4 Go | 1 | 2 | Un des plus gros consommateurs |
| `Postgres` | 400 Mo | 1 Go | 0.5 | 1 | Monte avec audit/approval/sync |
| `cortex-trust-engine` | 150 Mo | 400 Mo | 0.5 | 1 | Monte avec scoring continu |
| `OPA` | 100 Mo | 250 Mo | 0.2 | 0.5 | Faible, mais sensible latence |
| `Envoy ext_authz` | 150 Mo | 300 Mo | 0.3 | 1 | Important pour les chemins critiques |
| `cortex-audit` | 150 Mo | 300 Mo | 0.3 | 0.7 | Monte avec volume d'événements |
| `cortex-approval` | 150 Mo | 250 Mo | 0.2 | 0.5 | Peu coûteux seul |
| `cortex-obs-agent` | 200 Mo | 500 Mo | 0.5 | 1 | Monte avec collecte et polling |
| `cortex-nats-bridge` | 100 Mo | 200 Mo | 0.2 | 0.5 | Faible seul |
| `NATS / JetStream` | 250 Mo | 800 Mo | 0.5 | 1 | Monte avec persistance et backlog |
| `OTel collector` | 200 Mo | 700 Mo | 0.5 | 1 | Peut grossir vite si traces riches |
| `VictoriaMetrics` | 300 Mo | 1 Go | 0.3 | 1 | Dépend du volume de métriques |
| `cortex-console` | 250 Mo | 600 Mo | 0.5 | 1 | Build Next.js plus gourmand que runtime |
| `cortex-sentinel` | 150 Mo | 300 Mo | 0.3 | 0.7 | Léger à modéré |
| `cortex-sentinel-machine` | 200 Mo | 500 Mo | 0.5 | 1 | Monte avec NATS/WAL/scoring |
| `cortex-mcp-server` | 300 Mo | 1 Go | 1 | 2 | Un des plus sensibles à la charge |
| `cortex-orchestrator` | 200 Mo | 500 Mo | 0.5 | 1 | Modéré |
| `cortex-vllm` CPU | 2 Go | 6 Go | 2 | 4 | À éviter sur 8 Go si le reste tourne |

## Composants les plus critiques pour la mémoire

Ordre typique d'impact mémoire:

1. `cortex-vllm`
2. `Neo4j`
3. `Postgres`
4. `OTel collector` + observabilité
5. `VictoriaMetrics`
6. `cortex-mcp-server`
7. `kind` lui-même

## Composants les plus sensibles au CPU

1. `cortex-mcp-server`
2. `cortex-vllm`
3. `Envoy` + `cortex-gateway`
4. `cortex-obs-agent`
5. `cortex-trust-engine`
6. builds Docker

## Impact réel en machine 8 Go / 4 CPU

Sur une machine `8 Go / 4 CPU`:

- `vLLM` doit en pratique être désactivé
- `Neo4j` et `Postgres` doivent rester avec budgets serrés
- le build simultané de plusieurs images peut provoquer swap, OOM ou lenteur extrême
- `kind` + Docker + console + graph + observabilité peuvent déjà consommer l'essentiel de la machine

Conclusion honnête:

- ce profil permet de tester Cortex
- ce n'est pas un profil de fonctionnement confortable

## Recommandations pratiques

### Pour un laptop ou une petite VM

- désactiver `vLLM`
- lancer un seul replica par service
- éviter les rebuilds massifs en parallèle
- nettoyer Docker avant un réinstall complet
- lancer le frontend en dernier

### Pour une démo stable

- `16 Go / 8 vCPU`
- SSD rapide
- `vLLM` seulement si marge réelle

### Pour une mono-machine sérieuse

- `32 Go / 8-12 vCPU`
- NVMe
- marge disque > 100 Go libres

## Limites

- ces chiffres ne remplacent pas des benchmarks réels
- les pics dépendent fortement des builds Docker, du volume d'événements et des traces
- les modèles locaux peuvent changer complètement le budget
