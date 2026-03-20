# Cortex Sizing Reference

## Objectif

Donner une estimation realiste des ressources necessaires pour faire tourner Cortex selon trois modes:

- laboratoire contraint
- demo/dev confortable
- mono-machine renforcee

Ce document est volontairement pragmatique. Ce ne sont pas des promesses de performance. Ce sont des ordres de grandeur pour eviter de sous-dimensionner la machine.

## Resume rapide

| Profil | RAM | CPU | Disque | Verdict |
|---|---:|---:|---:|---|
| Contraint | 8 Go | 4 vCPU | 120 Go SSD | Demarre en mode reduit, peu de marge |
| Realiste | 16 Go | 8 vCPU | 150 Go SSD | Premiere base correcte |
| Confort | 32 Go | 8-12 vCPU | 200 Go NVMe | Recommande en mono-machine |

## Verdict par profil

### 1. Profil contraint

- `8 Go RAM`
- `4 vCPU`
- `120 Go SSD`

Ce profil permet:

- cluster local `kind`
- backend Cortex reduit
- console frontend
- Sentinel / Sentinel Machine
- Gateway / Trust / Graph / Audit / Approval / OPA / Envoy / NATS

Ce profil n'est pas adapte a:

- `vLLM` local stable
- forte parallelisation
- builds Docker repetes sans lenteur
- observabilite lourde
- plusieurs replicas

### 2. Profil realiste

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
- `8 a 12 vCPU`
- `200 Go SSD/NVMe`

Ce profil est recommande si tu veux:

- une stack complete mono-machine
- moins de contention Docker/Kubernetes
- observabilite plus riche
- quelques replicas
- integration et demo serieuses

## Reference par composant

Les chiffres ci-dessous sont des budgets realistes pour une instance unique, pas des limites exactes.

| Composant | RAM mini | RAM conseillee | CPU mini | CPU conseille | Notes |
|---|---:|---:|---:|---:|---|
| `kind` + kube-system + Calico | 700 Mo | 1.5 Go | 0.5 | 1 | Cout incompressible du cluster local |
| `cortex-auth` | 100 Mo | 200 Mo | 0.2 | 0.5 | Leger, surtout CPU faible |
| `cortex-sync` | 100 Mo | 200 Mo | 0.2 | 0.5 | Peu couteux hors gros flux |
| `cortex-gateway` | 150 Mo | 300 Mo | 0.3 | 1 | Monte avec `ext_authz` et trafic |
| `cortex-graph` | 150 Mo | 300 Mo | 0.3 | 1 | Leger cote API, lourd cote Neo4j |
| `Neo4j` | 1.5 Go | 4 Go | 1 | 2 | Un des plus gros consommateurs |
| `Postgres` | 400 Mo | 1 Go | 0.5 | 1 | Monte avec audit/approval/sync |
| `cortex-trust-engine` | 150 Mo | 400 Mo | 0.5 | 1 | Monte avec scoring continu |
| `OPA` | 100 Mo | 250 Mo | 0.2 | 0.5 | Faible, mais sensible latence |
| `Envoy ext_authz` | 150 Mo | 300 Mo | 0.3 | 1 | Important pour les chemins critiques |
| `cortex-audit` | 150 Mo | 300 Mo | 0.3 | 0.7 | Monte avec volume d'evenements |
| `cortex-approval` | 150 Mo | 250 Mo | 0.2 | 0.5 | Peu couteux seul |
| `cortex-obs-agent` | 200 Mo | 500 Mo | 0.5 | 1 | Monte avec collecte et polling |
| `cortex-nats-bridge` | 100 Mo | 200 Mo | 0.2 | 0.5 | Faible seul |
| `NATS / JetStream` | 250 Mo | 800 Mo | 0.5 | 1 | Monte avec persistance et backlog |
| `OTel collector` | 200 Mo | 700 Mo | 0.5 | 1 | Peut grossir vite si traces riches |
| `VictoriaMetrics` | 300 Mo | 1 Go | 0.3 | 1 | Depend du volume de metriques |
| `cortex-console` | 250 Mo | 600 Mo | 0.5 | 1 | Build Next.js plus gourmand que runtime |
| `cortex-sentinel` | 150 Mo | 300 Mo | 0.3 | 0.7 | Leger a modere |
| `cortex-sentinel-machine` | 200 Mo | 500 Mo | 0.5 | 1 | Monte avec NATS/WAL/scoring |
| `cortex-mcp-server` | 300 Mo | 1 Go | 1 | 2 | Un des plus sensibles a la charge |
| `cortex-orchestrator` | 200 Mo | 500 Mo | 0.5 | 1 | Modere |
| `cortex-vllm` CPU | 2 Go | 6 Go | 2 | 4 | A eviter sur 8 Go si le reste tourne |

## Composants les plus critiques pour la memoire

Ordre typique d'impact memoire:

1. `cortex-vllm`
2. `Neo4j`
3. `Postgres`
4. `OTel collector` + observabilite
5. `VictoriaMetrics`
6. `cortex-mcp-server`
7. `kind` lui-meme

## Composants les plus sensibles au CPU

1. `cortex-mcp-server`
2. `cortex-vllm`
3. `Envoy` + `cortex-gateway`
4. `cortex-obs-agent`
5. `cortex-trust-engine`
6. builds Docker

## Impact reel en machine 8 Go / 4 CPU

Sur une machine `8 Go / 4 CPU`:

- `vLLM` doit en pratique etre desactive
- `Neo4j` et `Postgres` doivent rester avec budgets serres
- le build simultane de plusieurs images peut provoquer swap, OOM ou lenteur extreme
- `kind` + Docker + console + graph + observabilite peuvent deja consommer l'essentiel de la machine

Conclusion honnete:

- ce profil permet de tester Cortex
- ce n'est pas un profil de fonctionnement confortable

## Recommandations pratiques

### Pour un laptop ou une petite VM

- desactiver `vLLM`
- lancer un seul replica par service
- eviter les rebuilds massifs en parallele
- nettoyer Docker avant un reinstall complet
- lancer le frontend en dernier

### Pour une demo stable

- `16 Go / 8 vCPU`
- SSD rapide
- `vLLM` seulement si marge reelle

### Pour une mono-machine serieuse

- `32 Go / 8-12 vCPU`
- NVMe
- marge disque > 100 Go libres

## Voir aussi

- [docs/UBUNTU_VM_INSTALL.md](/C:/Users/dell/Desktop/coco/docs/UBUNTU_VM_INSTALL.md)
- [docs/UBUNTU_VM_LEAN_INSTALL.md](/C:/Users/dell/Desktop/coco/docs/UBUNTU_VM_LEAN_INSTALL.md)

## Limites

- ces chiffres ne remplacent pas des benchmarks reels
- les pics dependent fortement des builds Docker, du volume d'evenements et des traces
- les modeles locaux peuvent changer completement le budget
