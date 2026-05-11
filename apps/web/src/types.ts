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
  data_provenance_mode: string;
  case_id?: string;
}


export interface EvidenceItem {
  source_id: string;
  claim?: string;
  published_at: string;
  source_type: string;
  relation: 'support' | 'contradict';
  publisher?: string;
  url?: string;
  support_strength: number;
  evidence_quality: number;
  independence: number;
  originality_score: number;
  incentive_conflict: number;
  content_hash?: string;
  replay_status?: string;
  narrative_id?: string;
  blocked_reason?: string;
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

export interface CitationQa {
  allowed_source_count: number;
  blocked_future_source_count: number;
  returned_blocked_source_count: number;
  narrative_count: number;
  narratives_with_support_count: number;
  missing_url_count: number;
  missing_content_hash_count: number;
  missing_publisher_count: number;
  low_quality_evidence_count: number;
  replay_filter_pass: boolean;
  support_coverage_pass: boolean;
  event_time_integrity_pass: boolean;
  provenance_ready: boolean;
  citation_qa_pass: boolean;
}

export interface SourceReliabilityBucket {
  group: 'overall' | 'publisher' | 'source_type';
  key: string;
  allowed_source_count: number;
  blocked_future_count: number;
  average_evidence_quality: number | null;
  average_independence: number | null;
  average_originality_score: number | null;
  low_quality_source_count: number;
  source_ids: string[];
  blocked_future_source_ids: string[];
}

export interface SourceReliability {
  overall: SourceReliabilityBucket;
  by_publisher: SourceReliabilityBucket[];
  by_source_type: SourceReliabilityBucket[];
}

export interface SourceCluster {
  cluster_id: string;
  cluster_basis: 'independence_cluster_id' | 'claim_text_fingerprint';
  source_count: number;
  source_ids: string[];
  narrative_ids: string[];
  publishers: string[];
  source_types: string[];
  relation_counts: Record<string, number>;
  average_fixture_originality_score: number | null;
  derived_originality_score: number;
  representative_claim: string;
}

export interface SourceClustering {
  allowed_source_count: number;
  blocked_future_source_count: number;
  cluster_count: number;
  duplicate_cluster_count: number;
  average_cluster_size: number | null;
  average_derived_originality_score: number | null;
  blocked_future_source_ids: string[];
  clusters: SourceCluster[];
}

export interface ModelComparison {
  system_id: string;
  selected_narrative_id: string | null;
  selected_rank: number | null;
  validated: boolean | null;
  selection_reason: string;
}

export interface EvaluationSummary {
  validated_narrative_ids: string[];
  missing_validated_narrative_ids?: string[];
  validated_rank: number | null;
  narrative_recall_at_3: boolean | null;
  top_ranked_validated: boolean | null;
  unsupported_claim_penalty_avg: number;
  unsupported_claim_penalty_max: number;
  high_unsupported_claim_count: number;
  blocked_future_source_count: number;
  allowed_source_count: number;
  model_comparisons: ModelComparison[];
}

export interface BenchmarkAggregate {
  case_count: number;
  evaluated_case_count: number;
  narrative_recall_at_3_rate: number | null;
  top_ranked_validated_rate: number | null;
  headline_baseline_validated_rate?: number | null;
  evidence_only_validated_rate?: number | null;
  narrativedesk_tournament_validated_rate?: number | null;
  no_contradiction_penalty_validated_rate?: number | null;
  quality_weighted_validated_rate?: number | null;
  blocked_future_source_count: number;
  unsupported_claim_penalty_avg: number;
  citation_qa_pass_rate?: number | null;
  provenance_ready_rate?: number | null;
  replay_filter_pass_rate?: number | null;
  support_coverage_pass_rate?: number | null;
  missing_url_count?: number;
  missing_content_hash_count?: number;
  low_quality_evidence_count?: number;
  source_reliability_avg_evidence_quality?: number | null;
  source_reliability_avg_independence?: number | null;
  source_reliability_avg_originality?: number | null;
  source_cluster_count?: number;
  source_duplicate_cluster_count?: number;
  source_clustering_avg_derived_originality?: number | null;
}

export interface Ledger {
  event: EventRecord;
  replay_audit: ReplayAudit;
  citation_qa: CitationQa;
  source_reliability: SourceReliability;
  source_clustering: SourceClustering;
  narratives: Narrative[];
}

export interface ValidationRow {
  window: string;
  label: string;
  narrative_id: string;
  expected_observable: string;
  future_source_ids?: string[];
  what_happened: string;
}

export interface ValidationFixture {
  event_id: string;
  status: string;
  note: string;
  future_source_ids?: string[];
  future_source_count?: number;
  rows: ValidationRow[];
}

export interface BundleIntegritySummary {
  verified_by_bundle_verify: boolean;
  artifact_hashes_ok: boolean | null;
  replay_integrity_ok: boolean;
  readiness_status: string;
  blocked_future_source_count: number;
  validation_future_source_count: number;
  note: string;
}

export interface CaseBundle {
  case_id: string;
  label: string;
  ledger: Ledger;
  report: string;
  bundle_integrity?: BundleIntegritySummary;
}

export interface CasesPayload {
  default_case_id: string;
  cases: CaseBundle[];
}

export interface ValidationCaseBundle {
  case_id: string;
  label: string;
  validation: ValidationFixture;
  evaluation: EvaluationSummary;
}

export interface ValidationCasesPayload {
  default_case_id: string;
  aggregate?: BenchmarkAggregate;
  cases: ValidationCaseBundle[];
}
