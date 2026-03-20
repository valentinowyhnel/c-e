# Cortex BlackEvoPaper

Document unique de reference Cortex, fusionnant:

- la vision executive
- la vue engineering
- l'etat operationnel actuel

---

## Partie 1. Executive

### Cortex en une phrase

Cortex est un control plane Zero Trust natif pour identites, workloads, decisions et remediations, combine a un moteur agentique et a une couche de raisonnement LLM specialisee.

### Probleme adresse

Les architectures classiques separant IAM, supervision, detection, approbation et execution produisent:

- trop de silos
- trop de temps de reaction
- trop de dependance a l'humain pour corriger vite
- trop peu de liens entre privilege, risque, telemetrie et action

Cortex unifie ces dimensions dans une meme boucle de controle.

### Proposition de valeur

Cortex apporte:

- une gouvernance temps reel des identites et privileges
- une chaine de decision liee au contexte et au risque
- une capacite de remediation assistee puis approuvee
- une observabilite operateur native
- une architecture orientee pre-prod puis production Kubernetes

### Ce qui rend Cortex different

#### 1. Le LLM n'est pas un gadget

Dans Cortex, les modeles sont assignes a des disciplines:

- Phi-3 pour classer et router
- Mistral pour menace et anomalie
- Llama 3 pour investigation et graphes
- CodeLlama pour scripts et generation structuree
- Claude / GPT pour les decisions a forte consequence

#### 2. Le systeme immunitaire agit avant l'escalade

Le Sentinel local:

- observe
- corrigele
- emet un score
- propose SOT, quarantaine ou apoptose

#### 3. Le privilege devient un objet calculable

Avec l'agent AD, BloodHound et le graphe:

- les chemins vers Tier 0 deviennent visibles
- les changements sensibles sont pre-valides
- les derives sont detectees dans le temps

#### 4. L'humain reste dans la boucle quand il le faut

Les risques eleves:

- passent par un agent decisionnel
- sont expliques clairement
- peuvent exiger approbation explicite
- laissent une trace auditable

### Blocs du produit

- `cortex-console`
- `cortex-mcp-server`
- `cortex-trust-engine`
- `cortex-sentinel`
- `cortex-agents`
- `cortex-approval`
- `cortex-audit`

### Cas d'usage cibles

- reduction du blast radius
- controle des privileges AD
- decisions de quarantaine expliquees
- supervision de derive et de groupes sensibles
- validation des changements a risque avant application
- pilotage operateur via une console unifiee

### Mecanique business

Cortex remplace l'empilement de plusieurs categories d'outils par une boucle integree:

- detection
- evaluation
- decision
- action
- approbation
- audit

### Etat actuel

Le systeme couvre deja:

- MCP v2
- agents AD / remediation / decision
- trust engine
- sentinel
- console temps reel
- BloodHound integre
- gouvernance des modeles et des taches

### Separation de maturite

Le document distingue maintenant explicitement trois niveaux:

- `deja implemente`
- `partiellement operationnel`
- `conceptuel / roadmap`

#### Deja implemente

- policy engine central avec decisions `allowed`, `denied`, `approval_required`, `prepare_only`, `blocked_due_to_degraded_mode`
- state machine d'isolation partagee entre Sentinel, Trust et remediations
- response graduee `monitor -> suspected -> observation -> restricted -> quarantined -> irreversible`
- separation `prepare_*` / `execute_*` sur les reponses sensibles
- SOT structure via token explicite, restrictions associees et lifecycle `issue / expire / revoke / impact`
- blocage policy des actions irreversibles en mode degrade critique
- blocage par maturite selon l'environnement
- enrichissement audit/approval avec correlation, execution mode et maturity
- contrats de messages versionnes pour les taches et resultats agents

#### Partiellement operationnel

- execution physique de quarantaine et de containment irreversible
- persistence complete des enrichissements dans tous les backends de stockage existants
- comite decisionnel multi-modeles avec fournisseurs externes reels
- forensic preserve branche a de vrais collecteurs specialises
- evaluation blast radius exhaustive quand le graphe est degrade

#### Conceptuel / roadmap

- containment irreversible production-ready
- anti-tamper avance et anti-rootkit
- orchestration de rollback multi-systeme
- preuves forensiques et chaine de custody etendue

### Garde-fous de surete

- aucun LLM n'est une autorite finale d'execution
- une action irreversible ne peut pas partir d'un signal faible unique
- une action irreversible ne peut pas partir d'un signal LLM unique
- les actions destructives sont bloquees si `approval`, `nats` ou `sentinel` sont indisponibles
- `dry_run` force un chemin `prepare_only` hors lecture seule
- les capacites `experimental` ou `stubbed` sont refusées en environnement `prod`
- les operations sensibles exigent des scopes explicites comme `admin:write`

### Modes degrades explicites

- `approval down` : aucune action irreversible, uniquement reversible ou prepare-only
- `vault down` : rotation de secrets bloquee
- `neo4j/bloodhound down` : analyse de blast radius partielle, execution autonome reduite
- `external llm down` : enrichissement advisory degrade, jamais d'ouverture de droits supplementaires
- `nats down` : pas d'execution distribuee fiable, restriction aux actions locales reversibles
- `sentinel down` : blocage des reponses destructives autonomes

### Couverture de tests de safety

Le repository contient des tests cibles sur les invariants de surete:

- invalid transition rejected par la state machine
- no irreversible action on weak evidence
- policy blocks experimental in prod
- degraded mode blocks destructive actions
- prepare versus execute sur la remediation
- cycle de vie SOT
- MCP blocking and prepare-only semantics
- audit enrichi avec correlation, maturity et degraded snapshot

### Ce que cela ouvre

- pre-production securisee
- industrialisation des workflows Zero Trust
- pilotage multi-agents
- extension vers production enterprise

---

## Partie 2. Engineering

### Architecture logique

```text
Signals / Requests
  -> Sentinel / Console / Orchestrator / Agents
  -> NATS / HTTP
  -> Trust Engine / MCP
  -> Agents
  -> Approval / Audit / Console
```

### Services

#### Core services

- `cortex-mcp-server`
- `cortex-trust-engine`
- `cortex-orchestrator`
- `cortex-gateway`
- `cortex-auth`

#### Agents

- `cortex-agent-ad`
- `cortex-agent-decision`
- `cortex-agent-remediation`
- `cortex-obs-agent`
- `cortex-sentinel`

#### Supporting services

- `cortex-approval`
- `cortex-audit`
- `cortex-console`
- `cortex-vllm`
- `cortex-nats-bridge`

#### Infra dependencies

- NATS JetStream
- Neo4j
- BloodHound
- Vault
- SPIRE
- Envoy
- OPA
- Postgres
- Valkey
- Falco
- OTEL Collector
- VictoriaMetrics
- LLDAP
- Keycloak

### Communications

#### HTTP

- `cortex-orchestrator -> cortex-mcp-server`
- `cortex-orchestrator -> cortex-vllm`
- `cortex-orchestrator -> cortex-sentinel`
- `cortex-mcp-server -> vLLM endpoints`
- `cortex-mcp-server -> Anthropic/OpenAI`
- `cortex-mcp-server -> cortex-trust-engine`
- `agents -> cortex-mcp-server`
- `console -> api/*`
- `console -> Vault`

#### NATS subjects

##### Agent work queues

- `cortex.agents.tasks.ad`
- `cortex.agents.tasks.decision`
- `cortex.agents.tasks.remediation`
- `cortex.agents.tasks.ad.results`
- `cortex.agents.tasks.decision.results`
- `cortex.agents.tasks.remediation.results`

##### Trust and immunity

- `cortex.trust.updates`
- `cortex.trust.decisions`
- `cortex.obs.stream`
- `cortex.obs.sot.issued`
- `cortex.security.events`

##### Observability

- `cortex.obs.actions`
- `cortex.obs.health`
- `cortex.obs.forecasts`
- `cortex.obs.anomalies`
- `cortex.obs.patterns`

##### AD domain stream

- `cortex.ad.drifts`
- `cortex.ad.actions`
- `cortex.ad.verifications`
- `cortex.ad.snapshots`
- `cortex.ad.kerberos.alerts`
- `cortex.ad.bloodhound.paths`

### MCP layer

#### Endpoints

- `GET /health`
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `POST /mcp/complete`
- `POST /mcp/tools/call`
- `POST /mcp/debug/route`

#### Pipeline

- input filter
- routing
- batch support
- multi-turn support
- dry-run support
- execution with fallback
- output filter
- metrics pipeline

#### Routed models

- `phi3-mini`
- `mistral-7b`
- `llama3-8b`
- `codellama-13b`
- `claude`
- `openai-gpt5`
- `openai-gpt45`

#### Tool dispatch

##### AD tools

- `ad_validate_group_membership`
- `ad_validate_service_account`
- `ad_run_drift_scan`
- `ad_restore_deleted`
- `ad_get_object_acl`
- `ad_get_deleted_objects`
- `ad_dirsync_changes`

##### BloodHound tools

- `bh_get_attack_path`
- `bh_get_blast_radius`
- `bh_answer_privilege_question`
- `bh_visualize_exposure`
- `bh_get_tier0_assets`

##### Decision tools

- `decision_assess_privilege_change`
- `decision_analyze_response`
- `decision_explain_human`

##### Response tools

- `issue_sot`
- `forensic_preserve`
- `get_blast_radius`

### Agent responsibilities

#### ADAgent

- LDAP client enrichi
- BloodHound guard
- Kerberos validator
- action verifier
- drift detector

Implemented task handlers:

- `add_to_group`
- `create_service_account`
- `run_drift_scan`
- `restore_deleted`
- `get_attack_path`
- `get_blast_radius`
- `answer_privilege_question`
- `visualize_exposure`
- `get_tier0_assets`
- `validate_group_membership`
- `validate_service_account`
- `get_object_acl`
- `get_deleted_objects`
- `dirsync_changes`

Stubbed / not yet implemented:

- `create_user`
- `disable_account`
- `remove_from_group`
- `reset_password`
- `move_to_ou`

#### DecisionAgent

Committee workflow:

1. `claude`
2. `openai-gpt5`
3. `openai-gpt45`
4. Claude synthesis

Supported tasks:

- `assess_privilege_change`
- `analyze_response_decision`
- `explain_human_decision`

#### RemediationAgent

Supported tasks:

- `issue_sot`
- `quarantine`
- `trigger_apoptosis`

Dependencies:

- MCP tools
- BloodHound data for AD-like entities
- decision committee for high-risk actions

#### ObsAgent

Loops:

- telemetry
- correlation
- baseline
- health
- forecast
- sentinel stream
- ad drift scan

#### Sentinel

Collectors:

- Falco
- Auditd
- psutil

Actions:

- `monitor`
- `issue_sot`
- `immediate_quarantine`
- `trigger_apoptosis`

### Trust flow

1. Sentinel emits `cortex.trust.updates`
2. Trust engine recomputes profile score
3. Trust engine emits `cortex.trust.decisions`
4. If score is low, trust engine emits remediation task or SOT

### Approval and audit

#### Approval

- HTTP workflow
- statuses:
  - `pending`
  - `approved`
  - `rejected`
  - `expired`

#### Audit

- immutable event log
- SHA-256 event signature
- filterable read APIs

### Security mechanisms

- Sentinel local scope gate in MCP
- `admin:write` guard for sensitive tools
- Vault sidecar secret injection
- SPIRE workload identity
- Envoy ext_authz
- OPA policy enforcement
- iptables local isolation in Sentinel
- multi-source requirement before apoptosis

### Console

#### Pages

- `/`
- `/models`
- `/search`
- `/attack-paths`
- `/graph`
- `/machines`
- `/decisions`
- `/schemas`

#### Features

- deep search
- graph exploration
- attack path reading
- operator presets
- local and server persistence
- model governance UI

### Helm packaging

Charts present:

- `helm/cortex-agents`
- `helm/cortex-console`
- `helm/cortex-enforcement`
- `helm/cortex-identity`
- `helm/cortex-infra`
- `helm/cortex-mcp-server`
- `helm/cortex-observability`
- `helm/cortex-sentinel`
- `helm/cortex-spire`
- `helm/cortex-trust-engine`
- `helm/cortex-vllm`

### Known constraints

- some AD write actions remain stubbed
- Claude/OpenAI need live keys
- Vault write mode in console needs `CORTEX_VAULT_TOKEN`
- some BloodHound behavior may rely on API compatibility layer depending on environment

### Formalisation d'etat

#### A. Deja implemente

- MCP v2 avec routage, tools, batch, dry-run, multi-turn
- Trust Engine v2 avec profils et emission de SOT
- Sentinel avec score 4D, collectors Falco/Auditd/psutil et isolement local
- agents `ad`, `decision`, `remediation` branches dans le runner
- console operateur avec recherche, graphes, attack paths, decisions, models
- dispatch NATS des tools AD / BloodHound / decision
- workflow approval et audit

#### B. Partiellement operationnel

- ADAgent CRUD complet
  - plusieurs handlers existent
  - plusieurs ecritures restent en stub
- dependance BloodHound
  - les integrations sont branchees
  - selon l'environnement, l'implementation peut reposer sur une API compatible
- gouvernance des modeles
  - la page et l'API existent
  - l'ecriture Vault depend encore du token et du secret reellement montes
- comite de decision externe
  - le workflow existe
  - la pleine puissance depend des cles Anthropic/OpenAI

#### C. Conceptuel / roadmap

- autonomie complete sur toutes les ecritures AD sensibles
- elimination totale des fallbacks heuristiques sur certains chemins
- mode production avec policies de rejet formalisees par service critique
- preuves cryptographiques plus fortes sur certaines decisions inter-services

### Risque de faux positifs

#### Sources principales

- Sentinel
  - Falco trop sensible
  - Auditd trop verbeux
  - psutil detecte des outils legitimes interpretes comme suspects
- AD drift
  - deltas LDAP transitoires
  - replication AD retardee
  - baseline incomplete ou stale
- BloodHound
  - graphe incomplet
  - exposition sur-estimee
- LLM
  - sur-classification d'un signal
  - explication convaincante mais incorrecte

#### Garde-fous deja en place

- multi-source check avant apoptose
- SOT avant action plus dure si les signaux sont insuffisants
- verification post-action pour certaines operations AD
- approval humaine pour risques 4-5
- separation detection / decision / execution
- OPA et scopes deterministes autour des ecritures

#### Garde-fous encore insuffisants

- calibration documentee par detecteur absente
- budget de faux positifs par type de signal non formalise
- politique de rollback standardisee encore incomplete pour tout l'AD
- quorum de preuves pas encore impose a toutes les decisions fortes

#### Politique recommandee

- aucune action irreversible sur un seul signal LLM
- aucune suppression ou apoptose sans:
  - au moins deux sources techniques independantes
  - validation deterministic policy
  - approval humaine si risque >= 4
- toute derive AD critique doit etre re-verifiee apres delai de replication

### Modes degrades

#### MCP degrade

- Phi-3 indisponible
  - fallback heuristique
  - puis routage de secours vers modele plus generaliste
- vLLM GPU indisponible
  - bascule sur CPU si possible
  - sinon Claude/OpenAI selon criticite
- tous modeles externes indisponibles
  - seules les decisions deterministes et tools locaux restent autorises
  - les actions fortes passent en attente ou sont deny

#### Trust degrade

- NATS/JetStream indisponible
  - publication core NATS quand possible
  - perte de certaines garanties de stream durable
- Trust Engine indisponible
  - pas de recalcul fin
  - les composants doivent conserver une posture conservative

#### Sentinel degrade

- Falco absent
  - bascule Auditd + psutil
- Auditd absent
  - bascule psutil seul
- isolement local non applicable
  - escalade vers remediation / approval sans pretendue execution locale

#### AD degrade

- LDAP indisponible
  - lecture / ecriture AD bloquees
  - seules analyses contextuelles non destructives restent autorisees
- BloodHound indisponible
  - les pre-checks privilege path doivent passer en mode deny ou approval obligatoire
- replication AD lente
  - verification differee
  - pas de declaration prematuree de succes definitif

#### Console degrade

- Vault indisponible
  - lecture seule ou absence de cles
- store operateur indisponible
  - perte de persistance serveur
  - maintien local-first si le navigateur a deja l'etat

### Dependance aux modeles externes

#### Risque

Les modeles externes sont utiles pour:

- synthese complexe
- analyse decisionnelle
- explication humaine

Mais ils sont dangereux s'ils deviennent:

- source unique de verite
- precondition obligatoire a une decision critique
- autorite d'execution sans garde-fou deterministe

#### Regle stricte a appliquer

- un modele externe ne doit jamais etre l'unique condition d'une action irreversible
- un modele externe peut proposer, expliquer, prioriser
- la permission finale doit rester contrainte par:
  - policy
  - scopes
  - etat trust
  - approval si criticite elevee

#### Ce qui est acceptable aujourd'hui

- Claude / GPT pour enrichir une decision
- Claude / GPT pour produire un memo d'approbation
- Claude / GPT pour arbitrer entre analyses

#### Ce qui ne doit pas etre considere comme acquis

- Claude / GPT comme seul moteur d'autorisation
- Claude / GPT comme seul critere de quarantaine ou d'apoptose
- Claude / GPT comme preuve suffisante de derive AD critique

---

## Partie 3. Reference operationnelle actuelle

### Snapshot de verification

- Derniere verification code locale: `2026-03-19`
  - `44` tests Python passes
  - compilation Python des services critiques OK
  - gate de maturite production executee et bloquante, comme attendu
- Derniere verification runtime reussie sur cluster local: `2026-03-19`
  - health checks verifies sur trust, mcp, obs-agent, audit, approval, console, auth, graph, orchestrator, gateway, vllm, bloodhound
  - hardening HTTP interne verifie sur trust, approval, audit, obs-agent
  - Sentinel v2 daemonset repare et valide sur le cluster local
- Limite de la session actuelle:
  - le contexte Kubernetes shell etait vide, mais la verification a ete restauree via `tmp-kind-kubeconfig.yaml`
  - la verification reste locale Kind, pas cloud pre-prod

### Etat de verification par composant

#### Verifie aujourd'hui en code local

- `cortex-policy-engine`
- `cortex-trust-engine`
- `cortex-mcp-server`
- `cortex-agent-remediation`
- `cortex-audit`
- `cortex-approval`
- `cortex-obs-agent`
- `shared/cortex-core`

#### Verifie precedemment en runtime local

- `cortex-trust-engine`
- `cortex-mcp-server`
- `cortex-audit`
- `cortex-approval`
- `cortex-obs-agent`
- `cortex-console`

#### Verifie aujourd'hui en runtime local

- `cortex-trust-engine`
- `cortex-mcp-server`
- `cortex-obs-agent`
- `cortex-audit`
- `cortex-approval`
- `cortex-console`
- `cortex-auth`
- `cortex-graph`
- `cortex-orchestrator`
- `cortex-gateway`
- `cortex-vllm`
- `bloodhound-ce`

#### Non reverifie en runtime dans cette session

- `cortex-auth`
- `cortex-gateway`
- `cortex-graph`
- `cortex-orchestrator`
- `cortex-vllm`
- `cortex-nats-bridge`
- `cortex-sentinel`
- infrastructure K8s associee

#### Correction appliquee sur Sentinel

- le `Deployment` legacy `cortex-sentinel` a ete retire
- le service `cortex-sentinel` est maintenant aligne sur le `DaemonSet` v2
- le runtime Sentinel v2 expose des endpoints de compatibilite:
  - `GET /health`
  - `POST /v1/validate-plan`
- le `DaemonSet` v2 a ete reconcilie apres:
  - suppression du demarrage `uv run` reseau-dependant
  - correction du packaging Python runtime
  - correction du bootstrap des imports partages
  - correction d'un blocage Calico sur un noeud

### Vision

Cortex est un control plane Zero Trust pilote par politiques, scores de confiance, LLM specialises et agents operatoires. L'architecture combine:

- controle d'identite et de confiance
- routage LLM via MCP
- surveillance immunitaire en temps reel
- execution agentique orientee remediation et decision
- audit immuable et approbation humaine
- console operateur temps reel

### Composants principaux

#### Control plane et logique centrale

- `cortex-mcp-server`
  - point d'entree LLM et tools
  - routage de modeles
  - filtrage entree/sortie
  - batch, dry-run, multi-turn
  - dispatch de tools vers agents via NATS

- `cortex-trust-engine`
  - evaluation des scores de confiance
  - profils de confiance par entite
  - emission de decisions Trust
  - emission de SOT et taches de remediation

- `cortex-orchestrator`
  - point d'orchestration de plans et de decisions
  - delegation des analyses de decision au MCP

- `cortex-gateway`
  - passerelle d'autorisation
  - integree a Envoy ext_authz

- `cortex-auth`
  - emission et validation de CAP tokens
  - prise en compte du trust score, scopes, session, device, DPoP

#### Agents

- `cortex-agent-ad`
  - operations et analyses Active Directory
  - BloodHound pre-check
  - validation Kerberos
  - drift detection
  - lecture ACL / recycle bin / DIRSYNC

- `cortex-agent-remediation`
  - emission de SOT
  - preparation quarantaine
  - preparation apoptosis
  - enrichissement blast radius / privilege context / decision committee

- `cortex-agent-decision`
  - comite de decision Claude + GPT-5 + GPT-4.5
  - synthese finale pour arbitrage
  - explication humaine

- `cortex-obs-agent`
  - boucle telemetrie
  - health monitoring
  - correlation
  - forecasts
  - consommation des flux Sentinel
  - planification des scans AD

- `cortex-sentinel`
  - systeme immunitaire local
  - collecte Falco + Auditd + psutil
  - score 4D
  - machine a etats d'isolation
  - emission d'events, trust updates, SOT et taches de remediation

#### Services operatoires

- `cortex-approval`
  - workflow d'approbation humaine
  - gestion des demandes pending / approved / rejected / expired

- `cortex-audit`
  - journal immuable signe
  - lecture par filtres

- `cortex-console`
  - console operateur Next.js
  - cockpit, recherche profonde, graphes, attack paths, schemas, machines, decisions
  - persistance locale et serveur
  - page `/models` pour gouvernance des modeles et des taches

#### Infrastructure et data plane

- `cortex-vllm`
  - execution locale/cloud des modeles open-weight

- `cortex-nats-bridge`
  - bridge HTTP vers NATS / JetStream

- NATS JetStream
  - bus de messages et de taches

- Neo4j
  - graphe d'identite, de relations et de risque

- BloodHound CE / API compatible
  - analyse de chemins de privilege
  - tier 0
  - blast radius
  - exposition de ressources

- Vault
  - secrets et injection sidecar

- SPIRE
  - identites workload

- Envoy + OPA
  - enforcement fail-closed

- VictoriaMetrics + OTEL Collector
  - observabilite et ingestion telemetrie

- Falco
  - detection runtime Kubernetes / Linux

- LLDAP + Keycloak + Valkey + Postgres
  - socle identite, federation, cache et stockage applicatif

### Modeles et moteur LLM

#### Modeles actuellement integres

- `phi3-mini`
  - routage
  - classification
  - validation de schema
  - resume court

- `mistral-7b`
  - menaces
  - anomalies
  - correlation

- `llama3-8b`
  - investigation
  - analyse de graphes
  - blast radius
  - remediation plan

- `codellama-13b`
  - generation de scripts
  - code / Rego
  - operations AD structurees

- `claude`
  - high-risk decision
  - explication humaine

- `openai-gpt5`
  - complex reasoning
  - decision analysis

- `openai-gpt45`
  - explication et synthese

#### Routage MCP

Le MCP route une requete selon:

- fast path par mots-cles
- classification Phi-3 si pas de fast path
- fallback heuristique si besoin
- fallback modele si indisponibilite
- forcage explicite possible par `force_model`

Le MCP expose:

- `/mcp/complete`
- `/mcp/tools/call`
- `/mcp/debug/route`
- `/health`
- `/healthz`
- `/readyz`
- `/metrics`

### Taches et outils relies

#### Outils AD et BloodHound dispatches via MCP

- `ad_validate_group_membership`
- `ad_validate_service_account`
- `ad_run_drift_scan`
- `ad_restore_deleted`
- `ad_get_object_acl`
- `ad_get_deleted_objects`
- `ad_dirsync_changes`
- `bh_get_attack_path`
- `bh_get_blast_radius`
- `bh_answer_privilege_question`
- `bh_visualize_exposure`
- `bh_get_tier0_assets`

#### Outils decisionnels

- `decision_assess_privilege_change`
- `decision_analyze_response`
- `decision_explain_human`

#### Outils de reponse supportes

- `issue_sot`
- `forensic_preserve`
- `get_blast_radius`

### Communications operationnelles

#### HTTP / API internes

- console -> APIs Next internes
- orchestrator -> MCP
- orchestrator -> vLLM / Sentinel
- MCP -> vLLM
- MCP -> Anthropic / OpenAI
- MCP -> trust-engine
- MCP -> sentinel
- agents -> MCP
- trust-engine -> clients HTTP
- console -> MCP health logique via backend
- console -> Vault pour gouvernance modeles si token disponible

#### NATS / JetStream

Les flux structurants du systeme passent par NATS. Exemples actuellement utilises:

- `cortex.agents.tasks.ad`
- `cortex.agents.tasks.decision`
- `cortex.agents.tasks.remediation`
- `cortex.agents.tasks.*.results`
- `cortex.trust.updates`
- `cortex.trust.decisions`
- `cortex.obs.stream`
- `cortex.obs.sot.issued`
- `cortex.obs.anomalies`
- `cortex.obs.actions`
- `cortex.obs.health`
- `cortex.obs.forecasts`
- `cortex.security.events`

Flux AD dedies:

- `cortex.ad.drifts`
- `cortex.ad.actions`
- `cortex.ad.verifications`
- `cortex.ad.snapshots`
- `cortex.ad.kerberos.alerts`
- `cortex.ad.bloodhound.paths`

#### Runtime local / host

- Sentinel applique aussi des mecanismes locaux:
  - `iptables` pour isolation
  - `psutil` pour processus et connexions
  - `ausearch` / `auditctl`
  - lecture des logs Falco

### Mecanismes de securite

- verification de scopes par Sentinel fallback dans MCP
- `admin:write` requis pour certaines ecritures sensibles
- audit signe par hash SHA-256
- approbation obligatoire pour risques eleves
- SOT pour observation coercitive
- machine a etats d'isolation cote Sentinel
- multi-source check avant apoptose
- pre-check BloodHound avant changements privilegies AD
- validation Kerberos avant comptes de service
- ACL / recycle bin / DIRSYNC pour robustesse AD
- Vault pour secrets
- SPIRE pour identite workload
- OPA + Envoy pour enforcement

### Mecanismes de decision

#### Trust

Le trust-engine:

- maintient un score par entite
- recalcule sur evidences
- publie les decisions
- emet des demandes de SOT si le score passe sous seuil

#### Immunitaire

Le Sentinel:

- collecte les signaux
- calcule un score 4D
- emet `monitor`, `issue_sot`, `immediate_quarantine`, `trigger_apoptosis`
- fait de l'isolement local
- notifie les agents de remediation

#### Decision committee

Le `DecisionAgent`:

- consulte le MCP avec `force_model=claude`
- consulte le MCP avec `force_model=openai-gpt5`
- consulte le MCP avec `force_model=openai-gpt45`
- synthese finale par Claude
- produit une sortie lisible pour l'humain

### Active Directory

Le pipeline AD v2 actuellement branche:

- BloodHound guard avant action sensible
- validation Kerberos
- verification post-action
- scans de derive
- ACL read
- deleted objects read/restore
- dirsync changes

Usages AD enrichis:

- groupe sensible
- service account
- GPO drift
- stale / orphan objects
- privilege path
- blast radius
- tier 0 exposure

### Console operateur

La console expose actuellement:

- cockpit principal
- recherche profonde
- attack paths
- graph
- machines
- decisions
- schemas
- modeles

Capacites:

- visualisation graphe identite et exposition
- recherche profonde multi-criteres
- favoris, tags, notes, incident rooms
- comparaison de noeuds
- timeline locale
- presets et persistence locale / serveur
- gouvernance des modeles par agent et par tache

### Mecanique globale

Sequence type:

1. un signal arrive via telemetrie, Sentinel, console ou orchestrator
2. Sentinel ou un composant publie sur NATS
3. trust-engine ajuste le score si besoin
4. obs-agent corrigele, observe et peut pousser une tache decisionnelle
5. remediation ou decision agent consomme la tache
6. l'agent appelle le MCP
7. le MCP route vers le bon modele ou vers un tool agentique
8. en cas de risque eleve, approval et audit sont engages
9. la console expose l'etat temps reel

### Etat reel a retenir

- les agents reels branches dans le runner sont `ad`, `decision`, `remediation`
- l'observabilite et le Sentinel utilisent NATS en flux temps reel
- le MCP est le point de convergence LLM + tools
- le Trust Engine pilote la logique de score et de SOT
- la console est maintenant un poste operateur pre-prod avec persistence et gouvernance des modeles

### Separation stricte de maturite

#### Deja implemente

- endpoints MCP, Trust, Approval, Audit, Console, Orchestrator
- flux NATS structurants
- score Sentinel et emission SOT / remediation
- comite decisionnel branche au MCP
- interfaces console de recherche, graph, attack paths, models

#### Partiellement operationnel

- ecritures AD completes
- ecriture Vault depuis la console
- execution pleine puissance Claude/OpenAI sans fallback local
- standardisation du rollback sur tous les workflows AD

#### Conceptuel / roadmap

- couverture exhaustive de tous les cas AD et IAM sans stub
- reduction formelle du risque de faux positifs par budgets mesurables
- mode production sans dependance ambigue a des API externes pour les decisions critiques

### Limites actuelles

- certaines actions AD CRUD restent marquees `not yet implemented`
- les appels Claude/OpenAI dependent des cles Vault effectives
- la page `/models` est live mais l'ecriture Vault depend de `CORTEX_VAULT_TOKEN`
- selon l'environnement, certains composants BloodHound peuvent etre exposes via une API compatible plutot que le produit CE complet

### Fichiers de reference

- `services/cortex-mcp-server/cortex_mcp_server/main.py`
- `services/cortex-mcp-server/cortex_mcp_server/router.py`
- `services/cortex-mcp-server/cortex_mcp_server/executor.py`
- `services/cortex-trust-engine/cortex_trust_engine/main.py`
- `services/cortex-sentinel/sentinel/engine.py`
- `services/cortex-obs-agent/cortex_obs_agent/main.py`
- `services/cortex-agents/cortex_agents/runner.py`
- `services/cortex-agents/cortex_agents/agents/ad.py`
- `services/cortex-agents/cortex_agents/agents/decision.py`
- `services/cortex-agents/cortex_agents/agents/remediation.py`
- `services/cortex-console/lib/model-governance.ts`
- `services/cortex-console/app/models/page.tsx`
