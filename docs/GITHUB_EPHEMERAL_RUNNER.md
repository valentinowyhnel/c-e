# GitHub Ephemeral Runner

## Objectif

Installer un runner GitHub Actions `self-hosted` ephemere, dedie a `valentinowyhnel/c-e`, avec generation automatique du token d'enregistrement via GitHub App.

## Pourquoi ephemere

Le depot est public. Un runner persistant est plus expose aux PR malicieuses. Le mode `--ephemeral` reduit le risque: le runner s'enregistre, execute un job, puis sort du pool.

## Pre-requis

- VM Ubuntu dediee
- GitHub App installee sur le depot
- permission App:
  - Repository administration: read/write
- identifiants disponibles:
  - `GITHUB_APP_ID`
  - `GITHUB_INSTALLATION_ID`
  - cle privee `.pem`

## Fichiers

- [scripts/github-runner/install-ephemeral-runner.sh](/C:/Users/dell/Desktop/coco/scripts/github-runner/install-ephemeral-runner.sh)
- [scripts/github-runner/bootstrap-ephemeral-runner.sh](/C:/Users/dell/Desktop/coco/scripts/github-runner/bootstrap-ephemeral-runner.sh)
- [scripts/github-runner/github-runner.service](/C:/Users/dell/Desktop/coco/scripts/github-runner/github-runner.service)

## Installation

Depuis le depot sur la VM:

```bash
chmod +x scripts/github-runner/install-ephemeral-runner.sh
bash scripts/github-runner/install-ephemeral-runner.sh
```

## Configuration

Creer l'environnement:

```bash
sudo mkdir -p /etc/github-runner
sudo tee /etc/github-runner/runner.env >/dev/null <<'EOF'
GITHUB_APP_ID=APP_ID
GITHUB_INSTALLATION_ID=INSTALLATION_ID
GITHUB_OWNER=valentinowyhnel
GITHUB_REPO=c-e
RUNNER_NAME=c-e-ephemeral-01
RUNNER_LABELS=self-hosted,linux,x64,cortex,ephemeral
RUNNER_WORKDIR=/opt/actions-runner
EOF
sudo chmod 600 /etc/github-runner/runner.env
```

Copier la cle GitHub App:

```bash
sudo cp github-app.pem /etc/github-runner/app.pem
sudo chmod 600 /etc/github-runner/app.pem
```

## Demarrage

```bash
sudo systemctl enable --now github-runner.service
sudo systemctl status github-runner.service
journalctl -u github-runner.service -f
```

## Workflow

Utiliser:

```yaml
runs-on: [self-hosted, linux, x64, cortex, ephemeral]
```

## Durcissement recommande

- VM dediee uniquement au runner
- aucun secret humain stocke sur la machine
- rotation reguliere de la GitHub App key
- destruction/recreation reguliere de la VM
- pas de montage du socket Docker hote sauf necessite explicite
