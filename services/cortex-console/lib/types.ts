export interface DashboardState {
  criticalAlerts: number;
  pendingApprovals: number;
  sentinelBlocked: number;
  activeSessionsCount: number;
  usersWithLowTrust: number;
  devicesNonCompliant: number;
  aiAgentsMonitored: number;
  agentTasksLast1h: number;
  mcpCallsLast1h: number;
  approvalsPendingOldest: number;
  trustEngineLatencyP99: number;
  extAuthzLatencyP99: number;
  policyDecisionsPerSec: number;
  graphNodesTotal: number;
  adSyncLastSuccess: string;
  adSyncDeltaPending: number;
  degradedWarnings?: string[];
  capabilityMaturitySummary?: Record<string, number>;
  executionModeSummary?: Record<string, number>;
}

export interface ApprovalRequest {
  requestId: string;
  planId: string;
  requestorId: string;
  riskLevel: 4 | 5;
  reasoning: string;
  actions: Array<{
    taskId: string;
    intent: string;
    riskLevel: number;
    dryRunRequired: boolean;
  }>;
  deadlineTs: number;
  approversRequired: number;
  approvalsReceived: number;
  status?: "pending" | "approved" | "rejected" | "expired";
  correlationId?: string;
  executionMode?: string;
  capabilityMaturity?: string;
  degradedMode?: boolean;
  riskEnvelope?: Record<string, unknown>;
}

export interface EventStreamItem {
  id: string;
  level: "critical" | "warning" | "info";
  title: string;
  timestamp: string;
  detail: string;
}
