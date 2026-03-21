# Google Colab Local Backend for Cortex

## Goal

Connect Google Colab to a local Jupyter backend on the Cortex machine so you can:

- inspect curated training corpora
- run defensive analysis notebooks
- train or evaluate bounded decision-support models on local Cortex exports

Do **not** expose raw Cortex internals or sensitive secrets to Colab unless strictly necessary.

## Safety first

With a Colab local connection, notebook code runs on your machine and can:

- read files
- write files
- delete files

For Cortex, the safe default is:

1. expose only curated exports, not the whole repo state
2. keep secrets out of notebooks
3. tick `Omettre l'élément de sortie des cellules de code...` in Colab if the notebook may print sensitive data
4. prefer JSON exports from the defensive training pipeline rather than direct service credentials

## Install Jupyter locally

```powershell
python -m pip install jupyterlab
```

## Start the local backend

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/runtime/start-colab-local-backend.ps1 -Port 8888 -Lab
```

This prints a URL like:

```text
http://localhost:8888/?token=abc123...
```

That is the exact value to paste into the Colab field:

- `URL du backend`

## Recommended Cortex workflow

Do not train directly from arbitrary raw logs.

Instead:

1. build a curated training plan
2. export the accepted items
3. open that export from Colab

Examples:

```powershell
python scripts/runtime/build-attack-training-plan.py samples.json --known known.json --output plan.json
```

```powershell
python scripts/runtime/build-internal-training-plan.py --audit audit-events.json --drifts ad-drifts.json --attack-paths bloodhound-paths.json --soc-reports soc-reports.json --known known.json --output internal-plan.json
```

Then in Colab, work only from:

- `plan.json`
- `internal-plan.json`

## What to paste into Colab

Use the URL printed by the script, for example:

```text
http://localhost:8888/?token=abc123
```

## Trust boundary

Colab is acceptable here for:

- experimentation
- evaluation
- notebook-driven enrichment
- comparative model analysis

Colab is **not** the execution authority for Cortex. Any model artifact or recommendation coming from Colab must still be:

- reviewed
- filtered
- policy-bounded
- kept advisory-first for decision workflows

## Real-time verified result injection into Cortex

The safe ingestion path is:

1. Curate a plan locally
2. Train or evaluate from Colab
3. Build a verified result payload
4. Push it into `cortex-orchestrator`
5. Let Cortex validate and only then consider promotion

Endpoint:

```text
POST /v1/training/colab/ingest
```

Security model:

- HMAC signature via `x-cortex-colab-signature`
- shared secret: `CORTEX_COLAB_SHARED_SECRET`
- novelty gate required
- known-attack filter required
- offensive-content filter required
- human review required if a model candidate is attached

Helper client:

```powershell
python scripts/runtime/colab_sync_client.py verified-colab-result.json --url http://127.0.0.1:8080/v1/training/colab/ingest --secret YOUR_SHARED_SECRET
```

One-shot helper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/runtime/start-colab-cortex-sync.ps1 -Secret YOUR_SHARED_SECRET
```

Artifacts provided in the repo:

- `examples/verified-colab-result.example.json`
- `notebooks/cortex_colab_sync.ipynb`
- `notebooks/cortex_apt_multiagent_rl.ipynb`
- `scripts/runtime/start-colab-cortex-sync.ps1`

The APT notebook now includes a final section that:

- builds a verified Colab payload from the simulated/runtime risk signals
- saves it as `verified_colab_result.json`
- can push it directly to `cortex-orchestrator` with HMAC signing

Expected verified payload shape:

```json
{
  "source": "google_colab",
  "run_id": "run-2",
  "training_plan_id": "plan-2",
  "target_agents": ["decision", "ad"],
  "dataset_fingerprint": "fingerprint-abcdef123456",
  "knowledge_registry_fingerprint": "known-1234",
  "accepted_item_ids": ["evt-9", "drift-9"],
  "verification": {
    "status": "verified",
    "novelty_gate_applied": true,
    "offensive_content_filtered": true,
    "known_attack_filter_applied": true,
    "human_reviewed": true,
    "accepted_count": 2,
    "reviewer": "analyst@cortex.local"
  }
}
```

## Production note

This local backend flow is for operator training and preprod experimentation.

It is not a production control-plane dependency.
