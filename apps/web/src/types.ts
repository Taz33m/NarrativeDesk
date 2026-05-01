export type Direction = 'bullish' | 'bearish' | 'neutral' | 'mixed';

export interface EventRecord {
  event_id: string;
  ticker: string;
  company_name: string;
  event_date: string;
  event_timestamp: string;
  event_type: string;
  daily_return: number;
  abnormal_return: number;
  volume_ratio: number;
  sector_etf_return: number;
  peer_median_return: number;
  event_summary: string;
}

export interface EvidenceItem {
  source_id: string;
  claim: string;
  published_at: string;
  source_type: string;
  relation: 'support' | 'contradict';
  publisher: string;
  url: string;
  support_strength: number;
  evidence_quality: number;
  independence: number;
  incentive_conflict: number;
  replay_status?: string;
  narrative_id?: string;
}

export interface ScoreInputs {
  evidence_strength: number;
  mechanism_specificity: number;
  source_independence: number;
  cross_sectional_fit: number;
  contradiction_resistance: number;
  timestamp_advantage: number;
  forward_observable_quality: number;
  crowding_risk: number;
  unsupported_claim_penalty: number;
}

export interface Narrative {
  narrative_id: string;
  event_id: string;
  ticker: string;
  timestamp_created: string;
  title: string;
  narrative: string;
  mechanism: string;
  directional_implication: Direction;
  time_horizon: string;
  supporting_evidence: EvidenceItem[];
  contradicting_evidence: EvidenceItem[];
  expected_observables: string[];
  scoring_inputs: ScoreInputs;
  scores: Record<string, number>;
  overall_narrative_score: number;
  rank: number;
  confidence: number | null;
  validation_status: string;
}

export interface ReplayAudit {
  replay_timestamp: string;
  allowed_source_ids: string[];
  blocked_source_ids: string[];
  removed_evidence_by_narrative: Record<string, string[]>;
  blocked_evidence: EvidenceItem[];
}

export interface Ledger {
  event: EventRecord;
  replay_audit: ReplayAudit;
  narratives: Narrative[];
}

export interface ValidationRow {
  window: string;
  label: string;
  narrative_id: string;
  expected_observable: string;
  what_happened: string;
}

export interface ValidationFixture {
  event_id: string;
  status: string;
  note: string;
  rows: ValidationRow[];
}
