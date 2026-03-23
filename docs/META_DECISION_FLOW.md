# Meta Decision Flow

## Objectif

Ce document decrit le flux Meta Decision Agent introduit dans Cortex pour evaluer la fiabilite des agents, detecter les conflits, demander une analyse approfondie si necessaire et reduire les erreurs de raisonnement inter-agents sans casser le fast path.

## Invariants

- zero trust entre agents
- aucun LLM dans le chemin critique auth authz
- fast path preserve si pas de conflit et confiance suffisante
- deep analysis seulement si conflit, faible confiance, nouveaute ou asset critique
- outputs MDA toujours auditables
- mode degrade explicite si timeout ou indisponibilite partielle

## Composants

- `cortex/meta_decision/`: implementation de reference locale pour la boucle d'entrainement et les simulations
- `services/cortex-agents`: emission de `agent signals` et consommation des `deep_analysis_requests`
- `services/cortex-sentinel`: bridge MDA local avant action Sentinel
- `services/cortex-orchestrator`: contrat partage, endpoint MDA et enrichissement de `/v1/decision`
- `services/cortex-mcp-server`: propagation du contexte `meta_decision` et relay des `deep_analysis_requests`
- `shared/cortex-core/cortex_core/meta_decision.py`: contrats Pydantic partages
- `proto/meta_decision/v1/meta_decision.proto`: schema proto du flux

## Flux nominal

```text
Agents Layer
  -> cortex.agents.signals
  -> Sentinel Meta Decision Bridge
  -> Meta decision event / audit
  -> Sentinel action selection

Orchestrator
  -> /v1/meta-decision/assess
  -> /v1/decision with meta_decision payload
  -> MCP Server
  -> DecisionAgent / explain_human_decision
```

## Messages standardises

### AgentSignal

Champs clefs:

- `entity_id`
- `agent_id`
- `specialty`
- `risk_signal`
- `runtime_trust`
- `uncertainty`
- `data_quality`
- `reasoning_quality`

### TrustedAgentOutput

Champs clefs:

- `weighted_scores`
- `agent_trust_scores`
- `conflict_score`
- `selected_agents`
- `deep_analysis_triggered`
- `reasoning_summary`

### DeepAnalysisRequest

Champs clefs:

- `event_id`
- `entity_id`
- `agent_id`
- `reasons`
- `deadline_ms`

## Deep analysis

Le `DecisionAgent` produit la forme standard suivante quand le MDA demande une analyse approfondie:

```json
{
  "explanation": "...",
  "hypotheses": ["..."],
  "counterfactuals": ["..."],
  "feature_importance": {
    "risk_level": 0.8,
    "conflict_score": 0.7
  },
  "confidence_interval": [0.55, 0.8]
}
```

## Degradation et fail-closed

- si le MDA est indisponible, sentinel reste operationnel
- si le MDA voit un conflit fort sur une action lourde, sentinel degrade vers `issue_sot`
- si le MCP ne peut pas appeler un agent, l'appel reste borne par Sentinel et Policy Engine
- si une approbation humaine est requise, le resultat reste `prepare`

## Topics et endpoints

### NATS

- `cortex.agents.signals`
- `cortex.meta_decision.events`
- `cortex.agents.tasks.decision`
- `cortex.agents.tasks.remediation`

### HTTP

- `POST /v1/meta-decision/assess` sur `cortex-orchestrator`
- `POST /mcp/meta-decision/deep-analysis` sur `cortex-mcp-server`
- `POST /mcp/tools/call` avec champ optionnel `meta_decision`

## Fichiers clefs

- `cortex/meta_decision/meta_decision_agent.py`
- `services/cortex-agents/cortex_agents/signal_export.py`
- `services/cortex-agents/cortex_agents/agents/decision.py`
- `services/cortex-sentinel/sentinel/meta_decision.py`
- `services/cortex-orchestrator/cortex_orchestrator/main.py`
- `services/cortex-mcp-server/cortex_mcp_server/main.py`

## Validation locale

Suites executees pendant l'integration:

- `python -m pytest tests/test_meta_decision.py tests/test_cortex_reward.py`
- `python -m pytest tests/test_signal_export.py tests/test_decision.py tests/test_remediation.py`
- `python -m pytest tests/test_engine.py tests/test_meta_decision.py`
- `python -m pytest tests/test_main.py`

## Limitations actuelles

- le bridge MDA dans Sentinel est local au service, pas encore un service separe
- le proto est defini mais les stubs ne sont pas encore generes dans les services
- l'orchestrateur fait une evaluation MDA heuristique, pas une federation complete multi-services

## Generation des stubs proto

Commande explicite:

```bash
python scripts/generate_meta_decision_proto_stubs.py
```

Alias Makefile:

```bash
make proto-meta-decision
make proto-meta-decision-go
```

Comportement attendu:

- echec fail-closed si `grpc_tools` est absent
- echec fail-closed si `protoc-gen-go` ou `protoc-gen-go-grpc` sont absents
- generation des stubs Python dans `proto/meta_decision/v1/`
- generation des stubs Go dans `proto/meta_decision/v1/`
