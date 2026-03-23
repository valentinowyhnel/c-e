# Meta Decision Proto

Le contrat proto `meta_decision.proto` definit les messages MDA partages.

## Generation Python

Generation explicite et fail-closed:

```bash
python scripts/generate_meta_decision_proto_stubs.py
```

Si `grpc_tools` n'est pas installe, la generation echoue volontairement sans produire de stub partiel.

## Generation Go

Generation explicite et fail-closed:

```bash
python scripts/generate_meta_decision_go_stubs.py
```

Alias Makefile:

```bash
make proto-meta-decision-go
```

Pre-requis:

- `grpc_tools`
- `protoc-gen-go`
- `protoc-gen-go-grpc`

## Messages

- `AgentSignal`
- `DeepAnalysisRequest`
- `TrustedAgentOutput`
- `MetaDecisionAssessmentRequest`
- `MetaDecisionEvent`
