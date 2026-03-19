# Installation Cortex sur VM Ubuntu

## Objectif

Installer Cortex sur une VM Ubuntu unique avec `kind`, dans l'ordre correct du depot, en enchaînant:

- environnement local
- cluster Kubernetes
- Vault
- SPIRE
- identite
- enforcement
- observabilite
- agents
- console
- validation runtime

## Pre-requis VM

- Ubuntu 22.04 ou 24.04
- 8 vCPU / 16 Go RAM minimum
- 16 vCPU / 32 Go RAM recommande pour le profil `max`
- 120 Go disque minimum

## Execution rapide

Depuis la racine du depot:

```bash
chmod +x scripts/install-cortex-ubuntu.sh
bash scripts/install-cortex-ubuntu.sh
```

## Profils

Profil standard:

```bash
CORTEX_PROFILE=standard bash scripts/install-cortex-ubuntu.sh
```

Profil max:

```bash
CORTEX_PROFILE=max bash scripts/install-cortex-ubuntu.sh
```

## Options utiles

Ignorer vLLM:

```bash
SKIP_VLLM=1 bash scripts/install-cortex-ubuntu.sh
```

Ignorer la validation finale:

```bash
SKIP_VALIDATION=1 bash scripts/install-cortex-ubuntu.sh
```

Installer depuis un autre chemin:

```bash
REPO_DIR=/opt/cortex bash scripts/install-cortex-ubuntu.sh
```

## Console

```bash
kubectl port-forward -n cortex-system svc/cortex-console 3000:3000
```

Ouvrir ensuite:

```text
http://127.0.0.1:3000
```

## Limites

- ce mode est un environnement local fort, pas une production multi-noeuds
- Vault est en mode dev dans ce parcours
- les secrets d'exemple doivent etre remplaces pour un usage reel
- les performances de `vLLM` dependent fortement de la RAM et du GPU
