# Cortex Stack Reference

Ce fichier fige la stack autorisee pour Cortex v2. Toute deviation doit etre documentee avant introduction.

## Langages

- Go 1.22+
- Python 3.12+
- TypeScript 5.4+

## Infrastructure

- Kubernetes 1.29+
- Helm 3.14+
- Terraform 1.7+
- Calico
- Traefik v3
- cert-manager 1.14+

## Secrets et identite

- HashiCorp Vault 1.16+
- SPIFFE / SPIRE 1.9+
- Keycloak 24+
- Lldap 0.5+

## Enforcement

- Envoy Proxy 1.29+
- OPA 0.63+
- Falco 0.37+

## Donnees

- Neo4j Community 5.18+
- PostgreSQL 16+
- Valkey 7.2+
- VictoriaMetrics 1.99+

## Messaging

- NATS JetStream 2.10+
- gRPC + protobuf 3
- NATS Bridge (Go)

## LLM et agents

- Claude Sonnet 4 via API Anthropic
- vLLM / llama.cpp server
- Anthropic Python SDK 0.25+
- MCP server FastAPI
- Agent Observabilite (Python)

## Observabilite

- OpenTelemetry Collector
- VictoriaMetrics 1.99+
- Agent Observabilite

## Frontend

- Next.js 14.2+
- TypeScript 5.4+ strict
- shadcn/ui
- Tailwind CSS 3.4+
- Zustand 4.5+
- TanStack Query 5.28+
- Sigma.js 3
- Graphology 0.25
- Monaco Editor
- next-auth v5

## Regles

- Jamais de `latest`
- Jamais de `^` sur les dependances critiques
- Aucun package hors stack sans decision documentee
