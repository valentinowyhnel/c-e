# CORTEX v2

## Architecture Multi-Agents Pilotee par LLM

## Statut

Document de reference d'architecture v2, derive du prompt maitre fourni par l'utilisateur le 15 mars 2026.

Ce document definit la cible technique a implementer. Le workspace etant vide au moment de la redaction, il sert de base de conception initiale et complete `STACK.md` lorsqu'il existera.

## Objectif

Cortex v2 est une architecture multi-agents Zero Trust pour la gestion d'identite, l'investigation securite, la gouvernance d'acces, la remediaton controlee et la surveillance d'agents IA.

Le systeme repose sur trois couches de raisonnement separees :

1. Raisonnement complexe par LLM principal pour la planification et l'explication.
2. Raisonnement specialise rapide par vLLM local pour les traitements frequents.
3. Decisions deterministes par Sentinel, OPA et moteurs de confiance pour toute validation critique.

Principe central : le LLM ne prend jamais une decision d'autorisation directe. Il propose, structure, explique et planifie. Les decisions d'acces, de securite et d'execution a risque restent deterministes et soumises a validation humaine selon le niveau de risque.

## Principes Fondateurs

### Trois niveaux de raisonnement

### Niveau 1

- Moteur : Claude Sonnet 4 via API
- Usage : planification, decomposition, arbitrage, explication
- Volume cible : environ 20 pour cent des demandes
- Latence cible : 2 a 5 secondes
- Cout : eleve

### Niveau 2

- Moteur : vLLM local
- Usage : classification, parsing, generation structuree, extraction
- Volume cible : environ 80 pour cent des demandes
- Latence cible : moins de 200 ms pour les cas simples
- Cout : nul en execution locale

### Niveau 3

- Moteurs : Sentinel, OPA, Trust Engine
- Usage : autorisation, validation, scoring, garde-fous
- Latence cible : moins de 50 ms
- Exigence : deterministe, auditable, sans LLM dans le chemin critique

### Human-in-the-loop

Les actions sont classees de 1 a 5.

- Risque 1-2 : execution autonome avec audit
- Risque 3 : execution avec notification humaine post-action
- Risque 4 : plan prepare par l'agent, approbation humaine obligatoire avant execution
- Risque 5 : plan prepare par l'agent, deux approbations humaines, dry-run obligatoire avant execution

Regle absolue : toute modification de l'Active Directory, toute revocation d'acces ou tout deploiement de politique est au minimum de risque 4.

## Vue d'Ensemble

### Composants principaux

- `cortex-orchestrator` : point d'entree pour les demandes complexes
- `cortex-vllm` : routeur et facades vers les modeles locaux
- `cortex-agents` : services Python specialises, un agent par domaine
- `cortex-sentinel` : gardien deterministe et blocage temps reel
- `cortex-approval` : workflow d'approbation humaine
- `NATS JetStream` : bus evenementiel inter-agents
- `MCP Gateway` : acces aux outils et donnees externes
- `Audit Log` : journal immuable des plans, actions et veredicts

### Agents specialises cibles

- `soc`
- `governance`
- `remediation`
- `simulation`
- `migration`
- `observer`

## Structure Cible du Depot

Le prompt impose une organisation stricte.

```text
services/
  cortex-orchestrator/
    cortex_orchestrator/
      orchestrator.py
  cortex-vllm/
    cortex_vllm/
      router.py
  cortex-agents/
    cortex_agents/
      base.py
    agents/
      soc/
      governance/
      remediation/
      simulation/
      migration/
      observer/
  cortex-sentinel/
    cortex_sentinel/
      sentinel.py
  cortex-approval/
    cortex_approval/
      gateway.py
helm/
  cortex-agents/
  cortex-vllm/
docs/
  CORTEX_V2_ARCHITECTURE.md
```

Contrainte d'implementation : chaque agent doit etre un service Python independant dans son propre dossier sous `services/cortex-agents/agents/{nom}/`.

## Composant 1 : LLM Orchestrator

### Role

L'orchestrateur recoit une intention depuis la console SOC, un evenement automatique ou un autre agent, puis produit un plan d'execution multi-agents.

### Responsabilites

- Pre-classifier l'intention via vLLM
- Router directement les cas simples sans mobiliser le LLM principal
- Decomposer les cas complexes via Claude
- Demander une validation deterministe au Sentinel
- Demander une approbation humaine si necessaire
- Journaliser le plan
- Piloter l'execution des taches selon les dependances et groupes paralleles

### Objets metier attendus

- `TaskStatus`
- `RiskLevel`
- `AgentTask`
- `ExecutionPlan`

### Invariants

- Toute tache destructive ou de modification AD doit porter un risque de 4 minimum
- Toute action irreversible doit etre de risque 5 et imposer un dry-run
- Les analyses peuvent etre paralllelisees
- Les modifications doivent toujours dependre d'une analyse prealable
- Le raisonnement du plan doit etre lisible par un humain

### Flux nominal

1. Reception de l'intention et du contexte.
2. Pre-classification par `vllm.classify_intent`.
3. Si la tache est simple, routage local.
4. Sinon, appel Claude pour produire `ExecutionPlan`.
5. Validation deterministe par `sentinel.validate_plan`.
6. Si le plan exige une approbation humaine, creation d'une demande via `approval.request`.
7. Journalisation du plan.
8. Execution ulterieure apres approbation si necessaire.

## Composant 2 : vLLM Router

### Role

Le routeur vLLM distribue les taches frequentes vers des modeles locaux specialises. Il decide egalement si l'intention reste dans le domaine local ou si elle doit etre transmise au LLM principal.

### Roles de modeles

- `THREAT_CLASSIFIER`
- `LOG_ANALYZER`
- `POLICY_WRITER`
- `INTENT_CLASSIFIER`
- `AD_ANALYZER`

### Regles de routage

- Pre-classification toujours par vLLM
- Taches simples a fort volume : vLLM local
- Taches complexes ou a forte exigence de raisonnement : Claude
- Toute generation de politique reste soumise a une validation OPA ensuite

### Taches simples prevues

- `classify_threat_event`
- `parse_log_batch`
- `generate_rego_snippet`
- `summarize_ad_group`
- `classify_intent`

### Taches complexes prevues

- `plan_migration`
- `investigate_incident`
- `audit_privilege_drift`
- `design_policy`
- `explain_blast_radius`
- `compare_agent_reasoning`

### Contraintes

- Le `policy_writer` est desactive en phase 1 pour contrainte memoire
- Le code Rego genere n'est jamais deploye sans validation ulterieure
- Les endpoints vLLM sont des services internes exposes en HTTP

## Composant 3 : Agents Specialises

### Contrat commun

Tous les agents doivent heriter de `CortexBaseAgent`.

### Capacites communes obligatoires

- Identite SPIFFE propre
- Communication via NATS JetStream
- Publication sur `cortex.agents.results`
- Publication de l'audit d'actions sur `cortex.agents.actions`
- Telemetrie OpenTelemetry
- Appels MCP sous controle Sentinel

### Contrat de resultat

Le resultat standard doit inclure :

- `task_id`
- `agent_id`
- `success`
- `output`
- `reasoning`
- `actions_taken`
- `requires_approval`
- `approval_payload`
- `duration_ms`
- `tokens_used`

### Regle cruciale

Tout appel MCP doit passer par le Sentinel avant execution. L'appel direct a `mcp.call_tool()` sans validation prealable devra etre interdit dans l'implementation concrete, par exemple via un wrapper unique.

## Agent SOC

### Mission

Investigation en lecture seule d'incidents securite et construction d'une analyse exploitable par l'operateur.

### Capacites

- Reconstituer une timeline d'incident
- Correlater des evenements multi-sources
- Identifier les comptes, groupes, devices et ressources impliques
- Evaluer le blast radius
- Produire un rapport lisible
- Proposer des actions de remediaton sans les executer

### Niveau de risque

- Risque 1 a 2
- Pas d'approbation humaine pour l'analyse seule

### Pipeline d'analyse

1. Recuperation de donnees via MCP en lecture seule
2. Pre-classification locale de chaque evenement via vLLM
3. Analyse approfondie via Claude
4. Extraction structuree des actions proposees
5. Retour d'un `AgentResult` sans action executee

## Agent Observer

### Mission

Surveiller tous les agents IA, internes et tiers, y compris les agents Cortex eux-memes.

### Perimetre surveille

- Agents IA tiers
- Agents Cortex
- Bots RPA
- Tout workload dote d'une identite SPIFFE dans le namespace `spiffe://cortex.local/agents/`

### Ce qui est collecte

- Actions executees
- Patterns comportementaux
- Ecarts a la baseline
- Trust score
- Logs bruts et structures

### Capacites de detection

- Acces hors perimetre
- Volume d'actions anormal
- Tentatives d'escalade
- Patterns suspects
- Agent compromis ou mal configure

### Taches supportees

- `collect_agent_logs`
- `compute_agent_baseline`
- `detect_deviation`
- `generate_agent_report`
- `watch_all`

### Regles de sortie

- Si `deviation_score > 0.7`, produire une analyse approfondie
- Si `deviation_score > 0.9`, demander une approbation pour isolement potentiel
- Toute deviation critique doit mettre a jour le Trust Score

## Composant 4 : Sentinel

### Role

Sentinel est le gardien deterministe du systeme. Il ne doit jamais utiliser de LLM.

### Ce qu'il surveille

- Chaque plan avant approbation humaine
- Chaque appel MCP outil en temps reel
- Le comportement des agents
- Les tentatives d'escalade de scopes
- Les comportements coordonnes suspects

### Regles deterministes cibles

- Limitation d'appels outillage par minute
- Blocage des revocations de masse
- Blocage des escalades de scopes
- Blocage des deploiements de politiques sans dry-run
- Rejet des actions d'un agent deja bloque
- Pause et alerte en cas de collusion suspecte

### Verifications minimales du plan

- Refuser tout plan impliquant un agent bloque
- Refuser toute tache de risque 4 ou plus sans dry-run
- Refuser les plans avec trop d'actions critiques
- Journaliser toute decision Sentinel

### Verifications minimales des appels outils

- Refuser les appels d'agents bloques
- Appliquer le rate limiting
- Detecter les revocations de masse
- Bloquer et auditer les comportements critiques

## Composant 5 : Approval Gateway

### Role

Gerer les workflows d'approbation humaine et publier les transitions de statut.

### Regles de gouvernance

- Risque 4 : 1 approbateur, timeout 30 minutes
- Risque 5 : 2 approbateurs, timeout 15 minutes, dry-run obligatoire avant execution reelle
- A expiration du delai, le plan est annule automatiquement
- Aucun plan critique ne doit etre execute en silence

### Canaux de notification prevus

- Console SOC via NATS ou WebSocket
- Email
- Slack ou Teams optionnels

### Donnees a persister

- Identifiant de demande
- Plan associe
- Demandeur
- Actions soumises a approbation
- Niveau de risque
- Nombre d'approbateurs requis
- Echeance
- Statut
- Journal des approbations

## Bus Evenementiel NATS

### Topics cibles

- `cortex.agents.tasks.{agent_type}`
- `cortex.agents.results`
- `cortex.agents.actions`
- `cortex.agents.heartbeat`
- `cortex.approvals.pending`
- `cortex.approvals.granted`
- `cortex.approvals.rejected`
- `cortex.approvals.expired`
- `cortex.sentinel.alerts`
- `cortex.sentinel.blocks`
- `cortex.vllm.requests`
- `cortex.vllm.responses`
- `cortex.observer.agent_profiles`
- `cortex.observer.deviations`
- `cortex.ad.sync.events`
- `cortex.ad.mutations`
- `cortex.audit.stream`
- `cortex.security.events`
- `cortex.trust.updates`

### Convention

Tous les agents publient leurs resultats et leurs actions de facon standardisee. L'audit global doit pouvoir reconstruire une timeline complete par `task_id`, `plan_id`, `agent_id` et horodatage.

## Identite et Securite

### SPIFFE

Chaque service et chaque agent a sa propre identite SPIFFE.

Exemples imposes :

- Orchestrateur : `spiffe://cortex.local/ns/cortex-system/sa/cortex-orchestrator`
- Routeur vLLM : `spiffe://cortex.local/ns/cortex-system/sa/cortex-vllm`

### Regles

- Les agents Cortex ont chacun une identite separee
- Les agents IA tiers doivent se trouver dans `spiffe://cortex.local/agents/`
- L'Observer doit surveiller aussi les agents Cortex
- Aucune confiance implicite ne doit exister entre agents

## Deploiement

### Helm

Le prompt vise :

- 1 replica pour chaque agent majeur
- Sentinel singleton
- vLLM dimensionne par modele
- `policy_writer` desactive en phase 1

### Hypotheses de ressources

- Agents standard : 256 a 512 Mi memoire
- Sentinel : 128 a 256 Mi
- vLLM threat classifier : 4 a 6 Gi
- vLLM log analyzer : 2 a 3 Gi
- vLLM policy writer : 8 a 10 Gi, desactive en phase 1

## Regles d'Implementation pour Codex

Ces regles doivent etre traitees comme invariants de code.

1. Chaque agent est un service Python independant sous `services/cortex-agents/agents/{nom}/`.
2. Chaque agent herite de `CortexBaseAgent`.
3. Sentinel n'utilise jamais de LLM.
4. vLLM traite le volume, Claude traite la complexite.
5. Tout appel MCP passe par `check_tool_call()` avant execution.
6. Observer surveille les agents Cortex et les agents tiers.
7. Les identites SPIFFE des agents tiers sont dans `spiffe://cortex.local/agents/`.
8. Dry-run obligatoire pour Remediation et Migration avant toute execution reelle.
9. Tout timeout d'approbation annule le plan.
10. `policy_writer` reste desactive en phase 1.

## Ecarts et Points d'Attention a l'Implementation

Le prompt decrit l'architecture cible, mais plusieurs points devront etre precises ou cadres au moment du code.

### Ecarts fonctionnels a combler

- Definir formellement les schemas JSON d'entree et de sortie des plans et resultats
- Definir le wrapper Sentinel obligatoire autour des appels MCP
- Definir le protocole de reprise d'execution apres approbation humaine
- Definir la persistance des plans et de leur etat d'execution
- Definir la gestion du retry, des timeouts et des nack sur NATS
- Definir l'integration OPA pour les politiques generees
- Definir les agents `governance`, `remediation`, `simulation` et `migration`, non detailles ici

### Risques techniques

- Sorties JSON de LLM potentiellement invalides sans schema strict
- Races possibles entre approbation, expiration et reprise d'execution
- Latence cumulative si un agent boucle sur Claude apres une forte pre-analyse locale
- Besoin d'un audit idempotent pour eviter les doublons sur reprise ou redelivery NATS
- Surveillance croisee des agents pouvant creer une charge importante si la baseline n'est pas incrementalisee

### Recommandations de conception

- Introduire des schemas Pydantic pour tous les messages
- Encapsuler MCP dans un client `guarded_mcp` qui appelle Sentinel avant tout
- Rendre les actions critiques idempotentes et journalisees par identifiant
- Ajouter un etat explicite `awaiting_approval` et `approved_for_execution` pour les plans
- Separer clairement les messages de raisonnement humain et les messages machine

## Flux End-to-End de Reference

### Cas simple

1. L'operateur soumet une intention.
2. vLLM classe l'intention comme simple.
3. Le systeme route vers un agent specialise.
4. L'agent execute une analyse locale ou une lecture outillage.
5. Le resultat est publie sur NATS et audite.

### Cas complexe avec approbation

1. L'operateur soumet une intention.
2. vLLM classe l'intention comme complexe.
3. L'orchestrateur demande a Claude de produire un plan.
4. Sentinel valide ou bloque le plan.
5. Si le risque l'impose, `ApprovalGateway` cree une demande.
6. L'humain approuve ou rejette.
7. En cas d'approbation, les taches sont executees selon dependances et groupes paralleles.
8. Tous les resultats et toutes les actions sont publies et audites.

## Roadmap d'Implementation Minimale

### Phase 1

- Creer les packages Python de base
- Implementer `CortexBaseAgent`
- Implementer `CortexSentinel`
- Implementer `ApprovalGateway`
- Implementer `VLLMRouter` avec `intent_classifier`, `threat_classifier`, `log_analyzer`
- Implementer `SOCAgent`
- Implementer `ObserverAgent`
- Deployer `policy_writer` desactive

### Phase 2

- Ajouter `governance`, `remediation`, `simulation`, `migration`
- Ajouter reprise d'execution apres approbation
- Ajouter OPA et moteur de politiques
- Ajouter graph d'identite et Trust Engine complets

### Phase 3

- Activer `policy_writer`
- Ajouter analyses avancees de collusion et baselines comportementales incrementales
- Industrialiser le monitoring, la resilience et les tests de charge

## Resume

Cortex v2 doit etre implemente comme un systeme multi-agents strictement separe, pilote par un orchestrateur LLM mais garde par des mecanismes deterministes. La decision d'autorisation n'appartient jamais au LLM. Toute action critique reste controlee par Sentinel, audit complet et approbation humaine selon le niveau de risque.

La priorite de mise en oeuvre doit rester :

1. Securite deterministe
2. Auditabilite
3. Separation claire des responsabilites
4. Human-in-the-loop sur toute action critique
5. vLLM pour le volume, Claude pour la complexite
