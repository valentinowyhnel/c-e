# Installation Cortex Lean sur VM Ubuntu 8 Go

## Objectif

Installer Cortex sur une VM Ubuntu contrainte:

- 8 Go RAM
- 4 CPU
- 250 Go disque

Le script dedie:

- nettoie la machine en mode `dry-run` par defaut
- reset le cluster Cortex
- rebuild les images Cortex
- demarre les backends d'abord
- installe et lance le frontend en dernier
- evite `vLLM` si la RAM est insuffisante

## Fichier

- [scripts/install-cortex-ubuntu-lean.sh](/C:/Users/dell/Desktop/coco/scripts/install-cortex-ubuntu-lean.sh)

## Important

Le script ne supprime pas arbitrairement "tout Ubuntu sauf le navigateur".

Il applique un nettoyage controle:

- arret/desactivation de services frequents non essentiels
- purge de paquets lourds courants
- nettoyage Docker
- `autoremove` et `apt clean`

Toute suppression hote est en `dry-run` tant que tu ne passes pas:

```bash
CLEANUP_MODE=apply
```

## Execution

Dry-run cleanup:

```bash
chmod +x scripts/install-cortex-ubuntu-lean.sh
bash scripts/install-cortex-ubuntu-lean.sh
```

Application reelle du nettoyage:

```bash
CLEANUP_MODE=apply bash scripts/install-cortex-ubuntu-lean.sh
```

Ne pas reset le cluster:

```bash
RESET_CLUSTER=0 bash scripts/install-cortex-ubuntu-lean.sh
```

Ignorer les validations:

```bash
SKIP_VALIDATION=1 bash scripts/install-cortex-ubuntu-lean.sh
```

Forcer ou interdire `vLLM`:

```bash
ENABLE_VLLM=1 bash scripts/install-cortex-ubuntu-lean.sh
ENABLE_VLLM=0 bash scripts/install-cortex-ubuntu-lean.sh
```

## Ordre applique

1. prerequis Ubuntu
2. nettoyage hote
3. Docker
4. outillage repo
5. reset Cortex
6. cluster
7. Vault
8. SPIRE
9. identite
10. enforcement backend
11. observabilite backend
12. agents backend
13. streams NATS
14. validation backend
15. frontend console en dernier
