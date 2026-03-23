# Cortex Bible

Document de reference unique de Cortex.

Ce fichier remplace les versions redondantes ou partielles du "BlackEvoPaper" et aligne la vision produit, l'architecture, les invariants de securite, les composants reels du depot, les nouvelles couches de Meta Decision et de reuse d'analyse, ainsi que l'etat actuel d'implementation.

---

## 1. Identite de Cortex

### Definition

Cortex est un control plane Zero Trust multi-agents pour:

- l'observation securite
- la decision assistee
- la gouvernance de confiance
- l'orchestration de remediations
- l'analyse de graphes d'identite
- la validation humaine des actions critiques

Le systeme combine:

- moteurs deterministes
- pipelines ML
- agents specialises
- raisonnement LLM hors chemin critique
- enforcement policy fail-closed

### Principe central

Le LLM ne decide jamais seul d'une action critique.

Le LLM peut:

- proposer
- expliquer
- classer
- enrichir
- comparer
- resumer

Mais la permission finale reste sous controle de:

- Sentinel
- Trust Engine
- Meta Decision Agent
- Policy Engine
- Approval
- Envoy ext_authz

### Objectif produit

Cortex vise a unifier dans une meme boucle:

1. detection
2. correlation
3. evaluation de confiance
4. arbitrage inter-agents
5. enforcement
6. remediation
7. audit

---

## 2. Invariants absolus

Ces regles doivent etre considerees comme non negociables.

1. Gate FAILED = on reste dans la phase.
2. Aucun LLM dans le chemin critique auth/authz.
3. Sentinel valide chaque appel MCP.
4. Dry-run obligatoire avant toute action irreversible.
5. Fail-closed partout.
6. Zero secret en variable d'environnement en cible produit.
7. Audit event sur chaque decision de securite.
8. Versions epinglees, jamais `latest`.
9. Aucune action irreversible sur un signal faible unique.
10. Aucune action irreversible sur un seul signal LLM.
11. Les actions destructives sont bloquees si Approval, NATS ou Sentinel sont indisponibles.
12. Le fast path doit rester rapide et ne pas etre penalise par la profondeur de raisonnement.

---

## 3. Vue d'ensemble d'architecture

### Pipeline macro

```text
Signals / Requests
  -> Model Layer
  -> Agents Layer
  -> Analysis Fingerprint Engine
  -> Case Memory Store
  -> Analysis Reuse Orchestrator
  -> Decision Memory Linker
  -> Meta Decision Agent
  -> Sentinel RL
  -> Trust Engine
  -> Policy Engine
  -> Enforcement
  -> Approval / Audit / Console
```

### Lecture du pipeline

- `Model Layer`
  - calcule des scores locaux ou de support
- `Agents Layer`
  - produit des analyses specialisees
- `Analysis Fingerprint Engine`
  - fabrique une empreinte stable du cas
- `Case Memory Store`
  - conserve les cas precedents, leur TTL, leur validation et leur reusability
- `Analysis Reuse Orchestrator`
  - decide `FULL_REUSE`, `PARTIAL_REUSE` ou `NO_REUSE`
- `Decision Memory Linker`
  - injecte le contexte memoire dans la decision
- `Meta Decision Agent`
  - arbitre entre agents, pondere, detecte les conflits, decide le deep analysis
- `Sentinel RL`
  - choisit l'action en posture conservative
- `Trust Engine`
  - maintient la confiance globale du systeme
- `Policy Engine`
  - applique les regles deterministes
- `Enforcement`
  - execute ou bloque

### Position de la couche Meta Decision

La couche Meta Decision est volontairement placee entre `Agents Layer` et `Sentinel RL`.

Elle ne remplace pas:

- le Trust Engine global
- OPA
- Envoy ext_authz
- les controles d'approval

Elle ajoute une couche d'arbitrage "zero trust entre agents".

---

## 4. Couches fonctionnelles

### A. Model Layer

Responsabilites:

- classification
- detection d'anomalie
- scoring de nouveaute
- scoring graphe
- scoring temporel
- support a la priorisation

Caracteristiques:

- utile pour le volume
- jamais autorite finale
- branche a la couche agents et a la Meta Decision

### B. Agents Layer

Responsabilites:

- analyses de specialite
- reasoning contextualise
- production de `AGENT_MESSAGES`
- participation au `deep analysis`

Agents reels et/ou integres:

- `threat_hunter`
- `trust`
- `graph`
- `anomaly`
- `decision`
- `remediation`
- `ad`
- `observer`

### C. Meta Decision Layer

Responsabilites:

- ne faire confiance a aucun agent par defaut
- calculer la confiance agent par agent
- mesurer les conflits inter-agents
- exploiter la memoire d'analyse
- limiter les recalculs inutiles
- declencher une analyse profonde seulement quand necessaire

### D. Sentinel RL

Responsabilites:

- transformer les signaux arbitres en action
- rester conservatif en cas de doute
- maintenir la boucle d'apprentissage locale
- rester operationnel meme si le MDA est partiellement indisponible

### E. Trust / Policy / Enforcement

Responsabilites:

- confiance globale entite/session/workload
- politiques deterministes
- ext_authz et garde-fous d'execution
- validation d'approbation si le risque l'impose

---

## 5. Meta Decision System

La couche Meta Decision est maintenant une brique majeure de Cortex.

### Objectifs

- valider la fiabilite des analyses agents
- reduire les erreurs de fusion naive
- proteger Cortex contre ses propres erreurs
- conserver le fast path
- reutiliser les analyses precedentes quand c'est sur

### Modules Python introduits

Dans `cortex/meta_decision/`:

- `meta_decision_agent.py`
- `decision_trust_engine.py`
- `case_complexity_engine.py`
- `deep_analysis_protocol.py`
- `agent_trust_registry.py`
- `confidence_calibration.py`
- `analysis_fingerprint_engine.py`
- `case_memory_store.py`
- `analysis_reuse_orchestrator.py`
- `decision_memory_linker.py`

Dans `cortex/learning/`:

- `continuous_learning_engine.py`

### Contrat de sortie MDA

Le MDA produit une sortie structurante du type:

```json
{
  "weighted_scores": {},
  "agent_trust_scores": {},
  "conflict_score": 0.0,
  "selected_agents": [],
  "deep_analysis_triggered": false,
  "reasoning_summary": "",
  "reuse_decision": "NO_REUSE"
}
```

### Invariants MDA

- timeout strict
- mode degrade explicite
- auditabilite de chaque sortie
- fast path preserve
- deep analysis uniquement si seuils atteints
- MDA jamais source unique d'autorisation

---

## 6. Decision Trust Engine

### Role

Le `Decision Trust Engine` calcule la confiance d'un agent pour un cas donne.

Il est independant du `Trust Engine` global.

### Formule

```text
agent_trust = f(
  base_trust,
  runtime_trust,
  case_trust,
  historical_accuracy,
  uncertainty,
  data_quality,
  reasoning_quality
)
```

### Entrees

- profil agent
- specialite
- runtime trust
- uncertainty
- data quality
- reasoning quality
- historique de precision

### Sorties

- `agent_case_trust`
- `trust_matrix`

### Effet systeme

Le DTE permet d'eviter la confiance aveugle entre agents:

- un agent historiquement bon mais actuellement incertain peut etre freine
- un agent specialise peut etre privilegie sur son domaine
- un agent derive peut etre degrade sans casser le systeme complet

---

## 7. Agent Trust Registry

### Role

Le registre de confiance stocke les profils d'agents:

- `base_trust`
- `runtime_trust`
- `capabilities`
- `specialties`
- `historical_accuracy`
- `drift_score`
- `performance_history`

### Utilisation

Il est consomme par:

- `DecisionTrustEngine`
- `ContinuousLearningEngine`

### But

Construire une confiance dynamique, specialisee et corrigeable.

---

## 8. Confidence Calibration Layer

### Role

Corriger les scores de confiance apres calcul brut.

### Objectif

- reduire la sur-confiance
- reduire la sous-confiance systematique
- lisser certains extremes selon la qualite du raisonnement

### Effet

Le MDA s'appuie sur des scores calibres plutot que sur la sortie brute du DTE.

---

## 9. Case Complexity Engine

### Role

Classifier un cas en:

- `FAST_PATH`
- `GUARDED_PATH`
- `DEEP_PATH`

### Variables

- `novelty_score`
- `graph_depth`
- `temporal_span`
- `conflict_score`
- `criticality`

### But

Eviter de sur-analyser les cas simples et reserver la profondeur de raisonnement aux cas:

- conflictuels
- nouveaux
- critiques
- diffus dans le graphe

---

## 10. Deep Analysis Protocol

### Role

Le protocole de deep analysis normalise les requetes aux agents quand le MDA estime qu'un cas le justifie.

### Format attendu

```json
{
  "explanation": "...",
  "hypotheses": ["..."],
  "counterfactuals": ["..."],
  "feature_importance": {},
  "confidence_interval": [0.0, 0.0]
}
```

### Conditions de declenchement

- conflit agent eleve
- confiance agent faible
- nouveaute elevee
- asset critique

### Contraintes

- timeout strict
- pas de deep analysis sur fast path stable
- toutes les demandes restent auditables

---

## 11. Analysis Reuse Layer

La couche de reuse est une extension majeure ajoutee a Cortex.

Elle evite les recalculs inutiles et injecte de la memoire dans la boucle de decision.

### 11.1 Analysis Fingerprint Engine

Responsabilite:

- generer une empreinte stable d'un cas a partir de:
  - `event`
  - `features`
  - `graph_context`
  - `trust_context`

Sorties:

- `fingerprint`
- `version`
- `material`

### 11.2 Case Memory Store

Responsabilite:

- stocker des cas analyses avec:
  - fingerprint
  - scores
  - agents utilises
  - decision finale
  - validation
  - model_version
  - policy_version
  - reusability_score
  - TTL
  - invalidation

### 11.3 Analysis Reuse Orchestrator

Responsabilite:

- decider:
  - `FULL_REUSE`
  - `PARTIAL_REUSE`
  - `NO_REUSE`

Critere de blocage absolu du reuse:

- `zero_day_possible`
- `admin_compromise`
- `insider`
- `crown_jewel`

### 11.4 Decision Memory Linker

Responsabilite:

- connecter memoire et MDA
- injecter un `memory_augmented_context`

### 11.5 Regles de reuse

Le reuse est permis seulement si:

- la similarite est suffisante
- la nouveaute est faible ou moderee
- la criticite reste compatible
- les versions de modeles/policies sont compatibles
- aucun flag de blocage n'est present

Le MDA garde toujours la decision finale.

---

## 12. Continuous Learning Engine

### Role

Le moteur d'apprentissage continu met a jour:

- la performance agent
- le trust agent
- la derive agent
- la memoire de cas
- la boucle `Sentinel RL`

### Fonctions clefs

- `update_agent_performance()`
- `adjust_agent_trust()`
- `detect_agent_drift()`
- `detect_drift()`
- `remember_case()`
- `retrain_models_if_needed()`
- `retrain_models()`

### But

Faire progresser Cortex sans permettre qu'un apprentissage degrade devienne un chemin d'autorisation implicite.

---

## 13. Services reels du depot

### Control plane et gateways

- `services/cortex-auth`
- `services/cortex-gateway`
- `services/cortex-orchestrator`
- `services/cortex-mcp-server`
- `services/cortex-policy-engine`
- `services/cortex-trust-engine`

### Agents et decision

- `services/cortex-agents`
- `services/cortex-sentinel`

### Console et observabilite

- `services/cortex-console`
- `services/cortex-audit`
- `services/cortex-approval`
- `services/cortex-graph`
- `services/cortex-obs-agent`

### Extensions ajoutees dans le depot

- `services/cortex-admin-anomaly`
- `services/cortex-campaign-memory`
- `services/cortex-edge-inference`
- `services/cortex-insider-decay`
- `services/cortex-priority-engine`

Ces briques etendent Cortex sur:

- la memoire campagne
- l'inference edge
- l'analyse admin
- la derive insider
- la priorisation

---

## 14. Integrations de la couche Meta Decision dans les services

### `services/cortex-agents`

Ajouts effectifs:

- export de `agent signals`
- fichier `signal_export.py`
- `DecisionAgent` capable de traiter `meta_decision` et `deep_analysis_request`

### `services/cortex-sentinel`

Ajouts effectifs:

- bridge MDA local avant action
- prise en compte de `conflict_score`
- degradation conservative vers `issue_sot` selon le niveau de risque

### `services/cortex-orchestrator`

Ajouts effectifs:

- contrat MDA partage
- endpoint `/v1/meta-decision/assess`
- enrichissement de `/v1/decision` avec payload `meta_decision`

### `services/cortex-mcp-server`

Ajouts effectifs:

- propagation du champ `meta_decision`
- endpoint `/mcp/meta-decision/deep-analysis`
- relay des demandes de deep analysis aux agents

### `services/cortex-gateway`

Ajouts effectifs:

- integration applicative du proto Go MDA
- endpoint `POST /v1/meta-decision/events`

### `shared/cortex-core`

Ajouts effectifs:

- contrats partages Pydantic pour `meta_decision`

### `proto/meta_decision/v1`

Ajouts effectifs:

- schema proto
- stubs Python generes
- stub Go genere

---

## 15. MCP, LLM et delegation

### Rappel de gouvernance

Le MCP est le point de convergence entre:

- modeles
- tools
- agents
- garde-fous Sentinel

### Ce qui est permis

- classification
- synthese
- explication
- aide a la decision
- deep analysis

### Ce qui est interdit

- autorisation critique directe par LLM seul
- execution irreversible sans dry-run
- escalade de privilege decidee uniquement par une sortie LLM

---

## 16. NATS, messages et contrats

### Flux NATS structurants

- `cortex.agents.tasks.*`
- `cortex.agents.tasks.*.results`
- `cortex.agents.signals`
- `cortex.meta_decision.events`
- `cortex.trust.updates`
- `cortex.trust.decisions`
- `cortex.obs.*`
- `cortex.security.events`
- `cortex.ad.*`

### Messages MDA standardises

- `AgentSignal`
- `DeepAnalysisRequest`
- `TrustedAgentOutput`
- `MetaDecisionAssessmentRequest`
- `MetaDecisionEvent`

---

## 17. Console Cortex

La console `services/cortex-console` est devenue un poste operateur plus proche d'une control room.

### Pages majeures

- `/`
- `/models`
- `/search`
- `/attack-paths`
- `/graph`
- `/machines`
- `/decisions`
- `/schemas`

### Etat actuel

- shell plus robuste
- KPI cards plus lisibles
- home plus "control room"
- meilleure coherence visuelle

### Positionnement

La console n'est pas un simple frontend de dashboards.
Elle est pensee comme poste de pilotage:

- analyse
- validation
- lecture des graphes
- suivi des decisions
- gouvernance des modeles

---

## 18. Zero Trust et enforcement

### Briques d'enforcement

- `Policy Engine (OPA)`
- `Envoy ext_authz`
- `Trust Engine`
- `Sentinel`
- `Approval`
- `Audit`

### Regle de posture

En cas de doute:

- on bloque
- on prepare sans executer
- on demande une approbation
- on degrade vers une action reversible

### Cas typiques

- un conflit fort inter-agents peut faire tomber l'action vers `issue_sot`
- un composant critique indisponible bloque le destructif
- une confiance insuffisante force une verification supplementaire

---

## 19. Modes degrades

### MDA degrade

- le systeme conserve un fallback
- la sortie peut passer en `degraded_mode`
- le deep analysis peut etre court-circuite
- Sentinel reste operationnel

### Sentinel degrade

- les actions destructives restent bloquees ou reduites
- l'isolement local reste prioritaire si possible

### MCP / modeles externes degrades

- on garde uniquement les chemins deterministes et locaux
- les actions fortes exigent approval ou blocage

### BloodHound / graphe degrade

- on reduit la confiance dans l'analyse d'impact
- on peut forcer deny ou approval

---

## 20. Etat d'implementation reel

### Deja implemente

- couche `Meta Decision` dans `cortex/meta_decision/`
- `ContinuousLearningEngine`
- integration du MDA avant `Sentinel RL` dans `cortex/training_pipeline.py`
- audit des sorties MDA
- deep analysis standardise
- `analysis fingerprint`, `case memory`, `reuse orchestrator`, `decision memory linker`
- contrats MDA partages dans `shared/cortex-core`
- proto `meta_decision`
- stubs Python et Go generes
- integrtions service-level dans agents, sentinel, orchestrator, MCP et gateway
- tests cibles MDA, proto et services
- mise a niveau visuelle du frontend principal

### Partiellement operationnel

- bridge MDA local dans Sentinel plutot que service MDA separe
- certaines integrations runtime complet K8s restent a rejouer selon environnement
- certaines actions AD sensibles ou ecritures restent encore bornees/stubbees

### Conceptuel / roadmap

- federation MDA multi-services complete
- worker MDA dedie en production
- strategie d'invalidation memoire distribuee
- calibration statistique plus riche par detecteur

---

## 21. Verification et tests

Suites qui ont ete executees pendant les integrations recentes:

- `python -m pytest tests/test_meta_decision.py tests/test_cortex_reward.py`
- `python -m pytest tests/test_meta_decision_proto_contract.py`
- `python -m pytest tests/test_decision.py tests/test_signal_export.py tests/test_remediation.py`
- `python -m pytest tests/test_engine.py tests/test_meta_decision.py`
- `python -m pytest tests/test_main.py`
- `go test ./internal/httpapi` sur `services/cortex-gateway`

Smoke checks confirmes:

- `run_training(episodes=1, num_events=6..8)` avec MDA actif
- frontend Cortex construit et servi en mode standalone

---

## 22. Fichiers pivots a connaitre

### Architecture et reference

- `README.md`
- `AGENTS.md`
- `docs/CORTEX_V2_ARCHITECTURE.md`
- `docs/META_DECISION_FLOW.md`
- `docs/PHASE_STATUS.md`

### Meta Decision local

- `cortex/meta_decision/meta_decision_agent.py`
- `cortex/meta_decision/decision_trust_engine.py`
- `cortex/meta_decision/case_complexity_engine.py`
- `cortex/meta_decision/deep_analysis_protocol.py`
- `cortex/meta_decision/agent_trust_registry.py`
- `cortex/meta_decision/confidence_calibration.py`
- `cortex/meta_decision/analysis_fingerprint_engine.py`
- `cortex/meta_decision/case_memory_store.py`
- `cortex/meta_decision/analysis_reuse_orchestrator.py`
- `cortex/meta_decision/decision_memory_linker.py`
- `cortex/learning/continuous_learning_engine.py`
- `cortex/training_pipeline.py`

### Contrats partages

- `shared/cortex-core/cortex_core/meta_decision.py`
- `proto/meta_decision/v1/meta_decision.proto`
- `proto/meta_decision/v1/meta_decision_pb2.py`
- `proto/meta_decision/v1/meta_decision.pb.go`

### Integrations services

- `services/cortex-agents/cortex_agents/runner.py`
- `services/cortex-agents/cortex_agents/signal_export.py`
- `services/cortex-agents/cortex_agents/agents/decision.py`
- `services/cortex-sentinel/sentinel/meta_decision.py`
- `services/cortex-sentinel/sentinel/engine.py`
- `services/cortex-orchestrator/cortex_orchestrator/main.py`
- `services/cortex-mcp-server/cortex_mcp_server/main.py`
- `services/cortex-mcp-server/cortex_mcp_server/executor.py`
- `services/cortex-gateway/internal/httpapi/handler.go`

### Frontend

- `services/cortex-console/app/page.tsx`
- `services/cortex-console/components/console-shell.tsx`
- `services/cortex-console/components/kpi-card.tsx`
- `services/cortex-console/app/globals.css`

---

## 23. Doctrine finale

Cortex doit etre compris comme un systeme immunitaire de decision securite.

Sa doctrine est simple:

- ne jamais faire confiance par defaut
- confronter les analyses
- garder des preuves
- reutiliser intelligemment ce qui est deja appris
- proteger le fast path
- faire intervenir l'humain quand le risque l'exige
- rester deterministe au moment critique

La couche Meta Decision et la couche Analysis Reuse ne changent pas cette doctrine.
Elles la rendent plus robuste, plus rapide sur les cas repetitifs, et plus difficile a tromper.
