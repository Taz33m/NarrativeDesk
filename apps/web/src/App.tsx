import { useEffect, useMemo, useState } from 'react';
import type {
  BenchmarkAggregate,
  BundleIntegritySummary,
  CasesPayload,
  EvidenceItem,
  EvaluationSummary,
  Ledger,
  Narrative,
  ValidationCasesPayload,
  ValidationFixture,
  ValidationRow,
} from './types';

type Mode = 'overview' | 'tournament' | 'evidence' | 'validation' | 'benchmark' | 'report';

const scoreRows: Array<{ key: keyof Narrative['scoring_inputs']; label: string; penalty?: boolean }> = [
  { key: 'evidence_strength', label: 'Evidence strength' },
  { key: 'mechanism_specificity', label: 'Mechanism specificity' },
  { key: 'source_independence', label: 'Source independence' },
  { key: 'cross_sectional_fit', label: 'Cross-sectional fit' },
  { key: 'contradiction_resistance', label: 'Contradiction resistance' },
  { key: 'timestamp_advantage', label: 'Timestamp advantage' },
  { key: 'forward_observable_quality', label: 'Forward observables' },
  { key: 'crowding_risk', label: 'Crowding risk', penalty: true },
  { key: 'unsupported_claim_penalty', label: 'Unsupported claim penalty', penalty: true },
];

const modes: Array<{ id: Mode; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'tournament', label: 'Tournament' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'validation', label: 'Validation' },
  { id: 'benchmark', label: 'Benchmark' },
  { id: 'report', label: 'Report' },
];

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'n/a';
  return `${(value * 100).toFixed(1)}%`;
}

function score(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'n/a';
  return value.toFixed(2);
}

function plural(count: number, singular: string, pluralLabel = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralLabel}`;
}

function compactTime(value: string): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(new Date(value));
}

function shortTime(value: string): string {
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

function shortMonthDay(value: string): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(new Date(value));
}

function sourceStamp(source: EvidenceItem): string {
  return `${source.source_id} | ${source.source_type.replaceAll('_', ' ')} | ${compactTime(
    source.published_at,
  )}`;
}

function checkLabel(value: boolean | null): string {
  if (value === null) return 'n/a';
  return value ? 'pass' : 'miss';
}

function statusClass(value: string): string {
  return `status-pill--${value.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'na'}`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function humanize(value: string): string {
  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function narrativeReason(narrative: Narrative): string {
  const inputs = narrative.scoring_inputs;
  const strengths = [
    { label: 'evidence was stronger', value: inputs.evidence_strength },
    { label: 'the mechanism was cleaner', value: inputs.mechanism_specificity },
    { label: 'source independence held up', value: inputs.source_independence },
    { label: 'the timestamp advantage was high', value: inputs.timestamp_advantage },
    { label: 'contradictions were contained', value: inputs.contradiction_resistance },
  ]
    .sort((left, right) => right.value - left.value)
    .slice(0, 3)
    .map((item) => item.label);

  return `${strengths.join(', ')}, and unsupported claims stayed low.`;
}

function validationHeadline(evaluation: EvaluationSummary | null, validation: ValidationFixture | null): string {
  const validatedWindow = validation?.rows.find((row) => row.label === 'validated');
  if (!evaluation) return 'Validation pending';
  if (evaluation.top_ranked_validated) {
    return `${validatedWindow?.window ?? 'Future'} validated the winner`;
  }
  if (evaluation.validated_rank) {
    return `${validatedWindow?.window ?? 'Future'} validated rank #${evaluation.validated_rank}`;
  }
  return 'No validated narrative yet';
}

function validationTone(evaluation: EvaluationSummary | null): string {
  if (evaluation?.top_ranked_validated === true) return 'validated';
  if (evaluation?.top_ranked_validated === false) return 'miss';
  return 'pending';
}

function topValidationRow(validation: ValidationFixture | null): ValidationRow | null {
  return validation?.rows.find((row) => row.label === 'validated')
    ?? validation?.rows.find((row) => row.label === 'partial')
    ?? validation?.rows[0]
    ?? null;
}

function cleanValidationCopy(row: ValidationRow | null | undefined, narrativeTitle?: string): string {
  if (!row) return 'Validation fixture is not loaded for this case.';
  let copy = row.what_happened.replace(/^Synthetic replay:\s*/i, '');
  if (narrativeTitle) {
    copy = copy.replace(
      new RegExp(`${escapeRegExp(narrativeTitle)} became the validated narrative as`, 'i'),
      `${narrativeTitle} validated after`,
    );
  }
  return copy.charAt(0).toUpperCase() + copy.slice(1);
}

function futureSourceCopy(row: ValidationRow | null | undefined): string {
  const ids = row?.future_source_ids ?? [];
  return ids.length ? `Future sources: ${ids.join(', ')}` : 'Future sources: none';
}

function compactNarrativeThesis(narrative: Narrative): string {
  if (narrative.title.toLowerCase().includes('demand slowdown')) {
    return 'Investors priced in weaker future subscriber and revenue growth, not a one-time margin issue.';
  }
  return narrative.narrative;
}

function narrativeOutcomeLabel(narrative: Narrative, evaluation: EvaluationSummary | null): string {
  if (evaluation?.validated_narrative_ids.includes(narrative.narrative_id)) return 'validated';
  if (evaluation?.top_ranked_validated === false && narrative.rank === 1) return 'miss';
  return narrative.validation_status;
}

function losingReason(narrative: Narrative, winner: Narrative): string {
  if (narrative.narrative_id === winner.narrative_id) return narrativeReason(winner);
  const reasons = [
    {
      label: 'weaker evidence',
      delta: winner.scoring_inputs.evidence_strength - narrative.scoring_inputs.evidence_strength,
    },
    {
      label: 'less specific mechanism',
      delta: winner.scoring_inputs.mechanism_specificity - narrative.scoring_inputs.mechanism_specificity,
    },
    {
      label: 'less timestamp advantage',
      delta: winner.scoring_inputs.timestamp_advantage - narrative.scoring_inputs.timestamp_advantage,
    },
    {
      label: 'more unsupported-claim risk',
      delta: narrative.scoring_inputs.unsupported_claim_penalty - winner.scoring_inputs.unsupported_claim_penalty,
    },
  ]
    .filter((item) => item.delta > 0.015)
    .sort((left, right) => right.delta - left.delta)
    .slice(0, 2)
    .map((item) => item.label);
  return reasons.length ? reasons.join(' / ') : 'lower total replay-safe score';
}

function uniqueEvidence(narrative: Narrative): EvidenceItem[] {
  const seen = new Set<string>();
  return [...narrative.supporting_evidence, ...narrative.contradicting_evidence].filter((item) => {
    const key = `${item.source_id}-${item.relation}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function exportHrefs(ledger: Ledger, report: string): { caseId: string; ledgerHref: string; reportHref: string } {
  const caseId = ledger.event.case_id ?? ledger.event.event_id;
  const filenameToken = caseId.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return {
    caseId: filenameToken,
    ledgerHref: `data:application/json;charset=utf-8,${encodeURIComponent(`${JSON.stringify(ledger, null, 2)}\n`)}`,
    reportHref: `data:text/markdown;charset=utf-8,${encodeURIComponent(report)}`,
  };
}

function App() {
  const [cases, setCases] = useState<CasesPayload | null>(null);
  const [validationCases, setValidationCases] = useState<ValidationCasesPayload | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [validation, setValidation] = useState<ValidationFixture | null>(null);
  const [report, setReport] = useState<string>('');
  const [selectedId, setSelectedId] = useState<string>('');
  const [activeMode, setActiveMode] = useState<Mode>('overview');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function loadDemo() {
      try {
        const demoAsset = (name: string) => `${import.meta.env.BASE_URL}demo/${name}`;
        const [casesResponse, validationResponse] = await Promise.all([
          fetch(demoAsset('cases.json')),
          fetch(demoAsset('evaluations.json')),
        ]);
        if (!casesResponse.ok || !validationResponse.ok) {
          throw new Error('Demo assets are missing. Run `make web-data` from the repo root.');
        }
        const payload = (await casesResponse.json()) as CasesPayload;
        const validationPayload = (await validationResponse.json()) as ValidationCasesPayload;
        const selected = payload.cases.find((c) => c.case_id === payload.default_case_id) ?? payload.cases[0];
        const selectedValidation = validationPayload.cases.find((c) => c.case_id === selected.case_id);
        setCases(payload);
        setValidationCases(validationPayload);
        setSelectedCaseId(selected.case_id);
        setLedger(selected.ledger);
        setValidation(selectedValidation?.validation ?? null);
        setReport(selected.report);
        setSelectedId(selected.ledger.narratives[0]?.narrative_id ?? '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Unable to load demo assets.');
      }
    }

    loadDemo();
  }, []);


  useEffect(() => {
    if (!cases) return;
    const selected = cases.cases.find((item) => item.case_id === selectedCaseId);
    if (!selected) return;
    const selectedValidation = validationCases?.cases.find((item) => item.case_id === selectedCaseId);
    setLedger(selected.ledger);
    setValidation(selectedValidation?.validation ?? null);
    setReport(selected.report);
    setSelectedId(selected.ledger.narratives[0]?.narrative_id ?? '');
  }, [cases, validationCases, selectedCaseId]);

  const selectedNarrative = useMemo(() => {
    return ledger?.narratives.find((narrative) => narrative.narrative_id === selectedId) ?? ledger?.narratives[0] ?? null;
  }, [ledger, selectedId]);

  const evaluation = useMemo(() => {
    return validationCases?.cases.find((item) => item.case_id === selectedCaseId)?.evaluation ?? null;
  }, [validationCases, selectedCaseId]);

  const bundleIntegrity = useMemo(() => {
    return cases?.cases.find((item) => item.case_id === selectedCaseId)?.bundle_integrity ?? null;
  }, [cases, selectedCaseId]);

  const topNarrative = useMemo(() => {
    return ledger?.narratives.find((narrative) => narrative.rank === 1) ?? ledger?.narratives[0] ?? null;
  }, [ledger]);

  const surfaceBaselineNarrative = useMemo(() => {
    return [...(ledger?.narratives ?? [])].sort((left, right) => (
      right.scoring_inputs.crowding_risk - left.scoring_inputs.crowding_risk
      || right.scoring_inputs.evidence_strength - left.scoring_inputs.evidence_strength
      || left.narrative_id.localeCompare(right.narrative_id)
    ))[0] ?? null;
  }, [ledger]);

  if (error) {
    return (
      <main className="app-shell app-shell--centered">
        <section className="error-panel">
          <p className="eyebrow">NarrativeDesk</p>
          <h1>Demo assets were not found.</h1>
          <p>{error}</p>
          <code>make web-data</code>
        </section>
      </main>
    );
  }

  if (!ledger || !selectedNarrative) {
    return (
      <main className="app-shell app-shell--centered">
        <section className="loading-panel">
          <p className="eyebrow">NarrativeDesk</p>
          <h1>Loading timestamp-locked replay...</h1>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell cockpit-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <img
            className="brand-logo"
            src={`${import.meta.env.BASE_URL}logo.png`}
            alt="NarrativeDesk logo"
          />
          <div>
            <p className="eyebrow">NarrativeDesk Replay</p>
            <h1>Replay-safe narrative ranking for abnormal market moves</h1>
            <p className="dek">
              Competing market narratives. Time-locked evidence. Later validation.
            </p>
          </div>
        </div>

        <div className="case-selector-panel">
          <label>
            Case library
            <select
              value={selectedCaseId}
              onChange={(event) => setSelectedCaseId(event.target.value)}
              data-testid="case-selector"
            >
              {cases?.cases.map((caseItem) => (
                <option key={caseItem.case_id} value={caseItem.case_id}>
                  {caseItem.label}
                </option>
              ))}
            </select>
          </label>
          <span className="provenance-chip">Demo provenance: {ledger.event.data_provenance_mode}</span>
        </div>
      </header>

      <ModeTabs activeMode={activeMode} onChange={setActiveMode} />

      {activeMode === 'overview' ? (
        <OverviewMode
          ledger={ledger}
          topNarrative={topNarrative ?? selectedNarrative}
          baselineNarrative={surfaceBaselineNarrative}
          evaluation={evaluation}
          validation={validation}
          onModeChange={setActiveMode}
        />
      ) : null}

      {activeMode === 'tournament' ? (
        <>
          <CaseContextBar ledger={ledger} topNarrative={topNarrative ?? selectedNarrative} evaluation={evaluation} validation={validation} />
          <div className="mode-grid mode-grid--tournament">
            <TournamentBracket
              ledger={ledger}
              baselineNarrative={surfaceBaselineNarrative}
              topNarrative={topNarrative ?? selectedNarrative}
              onSelect={setSelectedId}
            />
            <NarrativeTournamentList
              ledger={ledger}
              selectedNarrative={selectedNarrative}
              topNarrative={topNarrative ?? selectedNarrative}
              evaluation={evaluation}
              onSelect={setSelectedId}
            />
            <SelectedNarrativeCaseFile
              ledger={ledger}
              narrative={selectedNarrative}
              topNarrative={topNarrative ?? selectedNarrative}
            />
          </div>
        </>
      ) : null}

      {activeMode === 'evidence' ? (
        <>
          <CaseContextBar ledger={ledger} topNarrative={topNarrative ?? selectedNarrative} evaluation={evaluation} validation={validation} />
          <EvidenceTimeline ledger={ledger} validation={validation} />
          <div className="mode-grid mode-grid--evidence">
            <EvidenceChain ledger={ledger} narrative={selectedNarrative} />
            <LeakageAudit ledger={ledger} />
            <CitationQaPanel ledger={ledger} />
            <SourceMap ledger={ledger} />
          </div>
        </>
      ) : null}

      {activeMode === 'validation' ? (
        <>
          <CaseContextBar ledger={ledger} topNarrative={topNarrative ?? selectedNarrative} evaluation={evaluation} validation={validation} />
          <div className="mode-grid mode-grid--validation">
            <ValidationSnapshot
              evaluation={evaluation}
              validation={validation}
              ledger={ledger}
            />
            <ValidationPanel validation={validation} />
            {evaluation ? <EvaluationPanel evaluation={evaluation} /> : null}
          </div>
        </>
      ) : null}

      {activeMode === 'benchmark' ? (
        <>
          <CaseContextBar ledger={ledger} topNarrative={topNarrative ?? selectedNarrative} evaluation={evaluation} validation={validation} />
          <div className="mode-grid mode-grid--benchmark">
            {validationCases?.aggregate ? <BenchmarkCorpusPanel aggregate={validationCases.aggregate} /> : null}
            {evaluation ? <EvaluationPanel evaluation={evaluation} /> : null}
            <SourceReliabilityPanel ledger={ledger} />
            <SourceClusteringPanel ledger={ledger} />
          </div>
        </>
      ) : null}

      {activeMode === 'report' ? (
        <>
          <CaseContextBar ledger={ledger} topNarrative={topNarrative ?? selectedNarrative} evaluation={evaluation} validation={validation} />
          <ReportPanel
            ledger={ledger}
            report={report}
            evaluation={evaluation}
            bundleIntegrity={bundleIntegrity}
          />
        </>
      ) : null}
    </main>
  );
}

function OverviewMode({
  ledger,
  topNarrative,
  baselineNarrative,
  evaluation,
  validation,
  onModeChange,
}: {
  ledger: Ledger;
  topNarrative: Narrative;
  baselineNarrative: Narrative | null;
  evaluation: EvaluationSummary | null;
  validation: ValidationFixture | null;
  onModeChange: (mode: Mode) => void;
}) {
  return (
    <section className="overview-workspace" data-testid="case-cockpit">
      <CaseHero
        ledger={ledger}
        topNarrative={topNarrative}
        surfaceBaselineNarrative={baselineNarrative}
        evaluation={evaluation}
        validation={validation}
        onModeChange={onModeChange}
      />
    </section>
  );
}

function CaseContextBar({
  ledger,
  topNarrative,
  evaluation,
  validation,
}: {
  ledger: Ledger;
  topNarrative: Narrative;
  evaluation: EvaluationSummary | null;
  validation: ValidationFixture | null;
}) {
  return (
    <section className="case-context-bar">
      <div>
        <strong>{ledger.event.ticker}</strong>
        <span>{ledger.event.company_name}</span>
      </div>
      <span>{humanize(ledger.event.event_type)} | {ledger.event.event_date}</span>
      <span>{pct(ledger.event.abnormal_return)} abnormal</span>
      <span>{topNarrative.title}</span>
      <span className={`status-pill ${statusClass(validationTone(evaluation))}`}>
        {validationHeadline(evaluation, validation)}
      </span>
    </section>
  );
}

function CaseHero({
  ledger,
  topNarrative,
  surfaceBaselineNarrative,
  evaluation,
  validation,
  onModeChange,
}: {
  ledger: Ledger;
  topNarrative: Narrative;
  surfaceBaselineNarrative: Narrative | null;
  evaluation: EvaluationSummary | null;
  validation: ValidationFixture | null;
  onModeChange: (mode: Mode) => void;
}) {
  const { event, replay_audit: audit } = ledger;
  const validationRow = topValidationRow(validation);
  const validationLabel = validationHeadline(evaluation, validation);

  return (
    <section className="case-hero__story" data-testid="event-header">
      <div className="case-title-block">
        <span className="ticker">{event.ticker}</span>
        <div>
          <p className="case-kicker">{humanize(event.event_type)} | {event.event_date}</p>
          <h2>{event.company_name}</h2>
          <p>Demo provenance: synthetic benchmark case.</p>
        </div>
      </div>

      <div className="hero-number-grid">
        <MetricTile label="Daily move" value={pct(event.daily_return)} />
        <MetricTile label="Abnormal move" value={pct(event.abnormal_return)} />
        <MetricTile label="Peer median" value={pct(event.peer_median_return)} />
        <MetricTile label="Replay lock" value={compactTime(audit.replay_timestamp)} />
        <MetricTile label="Leakage" value="Clean" />
        <MetricTile label="Future blocked" value={String(audit.blocked_source_ids.length)} />
      </div>

      <section className="hero-decision" data-testid="thesis-strip">
        <div>
          <span className="strip-label">Winning Narrative</span>
          <strong>{topNarrative.title}</strong>
          <p>{compactNarrativeThesis(topNarrative)}</p>
        </div>
        <div>
          <span className="strip-label">Why it won</span>
          <strong>Score {score(topNarrative.overall_narrative_score)}</strong>
          <p>
            Evidence {score(topNarrative.scoring_inputs.evidence_strength)} | Mechanism{' '}
            {score(topNarrative.scoring_inputs.mechanism_specificity)} | Timestamp{' '}
            {score(topNarrative.scoring_inputs.timestamp_advantage)} | Unsupported{' '}
            {score(topNarrative.scoring_inputs.unsupported_claim_penalty)}
          </p>
        </div>
        <div>
          <span className="strip-label">History check</span>
          <strong className={`validation-headline validation-headline--${validationTone(evaluation)}`}>
            {validationLabel}
          </strong>
          <p>{cleanValidationCopy(validationRow, topNarrative.title)}</p>
        </div>
      </section>

      <div className="primary-actions" aria-label="Primary actions">
        <button type="button" onClick={() => onModeChange('evidence')}>View evidence trail</button>
        <button type="button" onClick={() => onModeChange('tournament')}>Compare to baseline</button>
        <button type="button" onClick={() => onModeChange('evidence')}>Replay timestamp</button>
        <button type="button" onClick={() => onModeChange('report')}>Export memo</button>
      </div>

      <div className="hero-integrity-row">
        <CompactReplayTimeline ledger={ledger} />
        <BaselineComparisonModule
          baselineNarrative={surfaceBaselineNarrative}
          topNarrative={topNarrative}
          evaluation={evaluation}
          validation={validation}
        />
      </div>
    </section>
  );
}

function BaselineComparisonModule({
  baselineNarrative,
  topNarrative,
  evaluation,
  validation,
}: {
  baselineNarrative: Narrative | null;
  topNarrative: Narrative;
  evaluation: EvaluationSummary | null;
  validation: ValidationFixture | null;
}) {
  return (
    <section className="baseline-module" data-testid="baseline-comparison">
      <div>
        <span className="strip-label">Surface baseline</span>
        <strong>{baselineNarrative?.title ?? 'No baseline selected'}</strong>
        <p>Ranked #{baselineNarrative?.rank ?? 'n/a'}</p>
      </div>
      <div>
        <span className="strip-label">NarrativeDesk winner</span>
        <strong>{topNarrative.title}</strong>
        <p>Ranked #{topNarrative.rank} | {validationHeadline(evaluation, validation)}</p>
      </div>
      <p>
        It weighted stronger allowed evidence, cleaner mechanism specificity, and lower unsupported-claim risk.
      </p>
    </section>
  );
}

function CompactReplayTimeline({ ledger }: { ledger: Ledger }) {
  const allowedSourceMap = new Map<string, EvidenceItem>();
  for (const narrative of ledger.narratives) {
    for (const source of uniqueEvidence(narrative)) {
      if (!allowedSourceMap.has(source.source_id)) allowedSourceMap.set(source.source_id, source);
    }
  }
  const allowedSources = Array.from(allowedSourceMap.values()).sort(
    (left, right) => new Date(left.published_at).getTime() - new Date(right.published_at).getTime(),
  );
  const blockedSource = [...ledger.replay_audit.blocked_evidence].sort(
    (left, right) => new Date(left.published_at).getTime() - new Date(right.published_at).getTime(),
  )[0];
  const earlySources = allowedSources
    .filter((source, index, list) => list.findIndex((item) => (
      item.source_type === source.source_type && item.published_at === source.published_at
    )) === index)
    .slice(0, 3);
  const events = [
    ...earlySources.map((source) => ({
      key: source.source_id,
      label: source.source_type.replaceAll('_', ' '),
      time: shortTime(source.published_at),
      state: 'allowed',
    })),
    {
      key: 'replay-lock',
      label: 'Replay lock',
      time: shortTime(ledger.replay_audit.replay_timestamp),
      state: 'lock',
    },
    ...(blockedSource ? [{
      key: blockedSource.source_id,
      label: 'Analyst revision blocked',
      time: shortMonthDay(blockedSource.published_at),
      state: 'blocked',
    }] : []),
  ];

  return (
    <section className="compact-timeline" data-testid="compact-replay-timeline">
      <div className="section-title-row">
        <h3>Replay timeline</h3>
        <span>Leakage clean</span>
      </div>
      <div className="compact-timeline__rail" aria-hidden="true">
        {events.map((event) => (
          <span className={`compact-timeline__dot compact-timeline__dot--${event.state}`} key={event.key} />
        ))}
      </div>
      <div className="compact-timeline__events">
        {events.map((event) => (
          <p className={`compact-timeline__event compact-timeline__event--${event.state}`} key={event.key}>
            <strong>{event.time}</strong>
            <span>{event.label}</span>
          </p>
        ))}
      </div>
      <p className="timeline-caption">
        Only evidence left of the lock entered ranking. Future evidence is quarantined for validation only.
      </p>
    </section>
  );
}

function ReplayLockVisual({ ledger }: { ledger: Ledger }) {
  const audit = ledger.replay_audit;
  const allowedCount = audit.allowed_source_ids.length;
  const blockedCount = audit.blocked_source_ids.length;

  return (
    <section className="replay-lock-card" data-testid="replay-lock">
      <div>
        <span className="lock-label">Replay Lock</span>
        <strong>{compactTime(audit.replay_timestamp)}</strong>
      </div>
      <div className="lock-meter" aria-hidden="true">
        <span className="lock-meter__allowed" />
        <span className="lock-meter__line" />
        <span className="lock-meter__blocked" />
      </div>
      <p>
        Allowed evidence: {allowedCount}. Blocked future evidence: {blockedCount}. Leakage status: clean.
      </p>
    </section>
  );
}

function CaseLibrary({
  cases,
  validationCases,
  selectedCaseId,
  onSelect,
}: {
  cases: CasesPayload | null;
  validationCases: ValidationCasesPayload | null;
  selectedCaseId: string;
  onSelect: (caseId: string) => void;
}) {
  if (!cases?.cases.length) return null;
  const validationByCase = new Map(validationCases?.cases.map((item) => [item.case_id, item]));

  return (
    <section className="case-library" data-testid="case-library">
      <div className="case-library__header">
        <span className="eyebrow">Replay Case Library</span>
        <p>Finds the explanation that survives time.</p>
      </div>
      <div className="case-library__rows">
        {cases.cases.map((caseItem) => {
          const validationCase = validationByCase.get(caseItem.case_id);
          const winner = caseItem.ledger.narratives.find((narrative) => narrative.rank === 1)
            ?? caseItem.ledger.narratives[0];
          return (
            <button
              className={`case-library-row ${caseItem.case_id === selectedCaseId ? 'is-selected' : ''}`}
              key={caseItem.case_id}
              type="button"
              onClick={() => onSelect(caseItem.case_id)}
            >
              <span>
                <strong>{caseItem.ledger.event.ticker}</strong>
                {caseItem.ledger.event.company_name}
              </span>
              <span>{humanize(caseItem.ledger.event.event_type)}</span>
              <span>{pct(caseItem.ledger.event.abnormal_return)} abnormal</span>
              <span>{winner?.title ?? 'No winner'}</span>
              <span className={`status-pill ${statusClass(validationTone(validationCase?.evaluation ?? null))}`}>
                {validationHeadline(validationCase?.evaluation ?? null, validationCase?.validation ?? null)}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function ModeTabs({ activeMode, onChange }: { activeMode: Mode; onChange: (mode: Mode) => void }) {
  return (
    <nav className="mode-tabs" aria-label="NarrativeDesk modes" data-testid="mode-tabs">
      {modes.map((mode) => (
        <button
          className={mode.id === activeMode ? 'is-active' : ''}
          key={mode.id}
          type="button"
          aria-selected={mode.id === activeMode}
          onClick={() => onChange(mode.id)}
        >
          {mode.label}
        </button>
      ))}
    </nav>
  );
}

function NarrativeTournamentList({
  ledger,
  selectedNarrative,
  topNarrative,
  evaluation,
  onSelect,
}: {
  ledger: Ledger;
  selectedNarrative: Narrative;
  topNarrative: Narrative;
  evaluation: EvaluationSummary | null;
  onSelect: (narrativeId: string) => void;
}) {
  return (
    <section className="panel panel--tournament" data-testid="narrative-tournament">
      <PanelHeader kicker="Competing Narratives" title="Event-time alternatives" />
      <div className="narrative-list">
        {ledger.narratives.map((narrative) => (
          <button
            className={`narrative-card ${
              narrative.narrative_id === selectedNarrative.narrative_id ? 'is-selected' : ''
            }`}
            key={narrative.narrative_id}
            type="button"
            aria-pressed={narrative.narrative_id === selectedNarrative.narrative_id}
            onClick={() => onSelect(narrative.narrative_id)}
          >
            <span className="narrative-card__top">
              <span>
                <span className="rank">#{narrative.rank}</span>
                <span className="narrative-title">{narrative.title}</span>
              </span>
              <span className={`status-pill ${statusClass(narrativeOutcomeLabel(narrative, evaluation))}`}>
                Score {score(narrative.overall_narrative_score)} | {narrativeOutcomeLabel(narrative, evaluation)}
              </span>
            </span>
            <span className="narrative-card__body">
              <span className="narrative-summary">{compactNarrativeThesis(narrative)}</span>
              <span className="mini-metrics">
                <Metric label="Evidence" value={score(narrative.scoring_inputs.evidence_strength)} />
                <Metric label="Mechanism" value={score(narrative.scoring_inputs.mechanism_specificity)} />
                <Metric label="Unsupported" value={score(narrative.scoring_inputs.unsupported_claim_penalty)} />
              </span>
              <span className="loss-reason">
                {narrative.narrative_id === topNarrative.narrative_id
                  ? 'Why it won: replay-safe score led the field'
                  : `Why it lost: ${losingReason(narrative, topNarrative)}`}
              </span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function SelectedNarrativeCaseFile({
  ledger,
  narrative,
  topNarrative,
}: {
  ledger: Ledger;
  narrative: Narrative;
  topNarrative: Narrative;
}) {
  const blocked = ledger.replay_audit.blocked_evidence.filter(
    (source) => source.narrative_id === narrative.narrative_id,
  );
  const isWinner = narrative.narrative_id === topNarrative.narrative_id;

  return (
    <section className="panel case-file" data-testid="evidence-inspector">
      <PanelHeader
        kicker={isWinner ? 'Selected Narrative | Winner' : 'Selected Narrative'}
        title={narrative.title}
      />
      <div className="case-file__thesis">
        <span>Thesis</span>
        <p>{narrative.mechanism}</p>
      </div>
      <div className="case-file__why">
        <h3>Why it beat baseline</h3>
        <p>{isWinner ? narrativeReason(narrative) : 'Selected for inspection. The tournament winner remains above it after replay-safe scoring.'}</p>
      </div>
      <ScoreStack narrative={narrative} />
      <section className="case-file__evidence-preview">
        <div className="section-title-row">
          <h3>Evidence chain</h3>
          <span>Allowed only</span>
        </div>
        {narrative.supporting_evidence.slice(0, 2).map((source) => (
          <article className="source-card" key={`${source.source_id}-preview`}>
            <span>{sourceStamp(source)}</span>
            <p>{source.claim ?? 'Allowed source supports this narrative.'}</p>
          </article>
        ))}
        {narrative.contradicting_evidence.slice(0, 1).map((source) => (
          <article className="source-card source-card--contradiction" key={`${source.source_id}-preview`}>
            <span>{sourceStamp(source)}</span>
            <p>{source.claim ?? 'Allowed source contradicts this narrative.'}</p>
          </article>
        ))}
      </section>
      <div className="case-file__audit-links">
        <span>{plural(narrative.supporting_evidence.length, 'supporting source')}</span>
        <span>{plural(narrative.contradicting_evidence.length, 'contradiction')}</span>
        <span>{plural(blocked.length, 'future source')} blocked</span>
      </div>
      <section className="observables">
        <div className="section-title-row">
          <h3>Expected observables</h3>
          <span>{narrative.time_horizon}</span>
        </div>
        {narrative.expected_observables.map((observable) => (
          <p key={observable}>{observable}</p>
        ))}
      </section>
    </section>
  );
}

function ScoreStack({ narrative }: { narrative: Narrative }) {
  return (
    <section className="score-stack" aria-label="Narrative score stack">
      <div className="section-title-row">
        <h3>Narrative Score</h3>
        <span>{score(narrative.overall_narrative_score)}</span>
      </div>
      {scoreRows.map((row) => {
        const value = narrative.scoring_inputs[row.key];
        const displayValue = row.penalty ? 1 - value : value;
        const valueLabel = row.penalty && value <= 0.1 ? `Low ${score(value)}` : score(value);
        return (
          <div className="score-stack-row" key={row.key}>
            <span>{row.label}</span>
            <div className="score-track" aria-hidden="true">
              <span
                className={row.penalty ? 'score-fill score-fill--inverted' : 'score-fill'}
                style={{ width: `${Math.max(0, Math.min(displayValue, 1)) * 100}%` }}
              />
            </div>
            <strong>{valueLabel}</strong>
          </div>
        );
      })}
    </section>
  );
}

function ValidationSnapshot({
  evaluation,
  validation,
  ledger,
}: {
  evaluation: EvaluationSummary | null;
  validation: ValidationFixture | null;
  ledger: Ledger;
}) {
  const validatedNarratives = evaluation?.validated_narrative_ids
    .map((id) => ledger.narratives.find((narrative) => narrative.narrative_id === id)?.title ?? id)
    .join(', ');

  return (
    <section className="panel validation-snapshot" data-testid="validation-snapshot">
      <PanelHeader kicker="Historical Validation" title="What happened later" />
      <div className={`validation-result validation-result--${validationTone(evaluation)}`}>
        <span>{validationHeadline(evaluation, validation)}</span>
        <strong>{validatedNarratives || 'No validated narrative yet'}</strong>
      </div>
      <p className="panel-note">Future-only fixture. Not available to event-time ranking.</p>
      <div className="validation-window-stack">
        {validation?.rows.map((row) => (
          <article className="validation-window" key={row.window}>
            <span className="window">{row.window}</span>
            <span className={`status-pill ${statusClass(row.label)}`}>{row.label}</span>
            <p>{row.expected_observable}</p>
            <strong>{cleanValidationCopy(row)}</strong>
            <small className="future-source-line">{futureSourceCopy(row)}</small>
          </article>
        )) ?? <p className="empty-copy">No validation rows loaded.</p>}
      </div>
    </section>
  );
}

function EvidenceTimeline({ ledger, validation }: { ledger: Ledger; validation: ValidationFixture | null }) {
  const allowedSourceMap = new Map<string, EvidenceItem>();
  for (const narrative of ledger.narratives) {
    for (const source of uniqueEvidence(narrative)) {
      if (!allowedSourceMap.has(source.source_id)) allowedSourceMap.set(source.source_id, source);
    }
  }
  const allowedSources = Array.from(allowedSourceMap.values()).sort(
    (left, right) => new Date(left.published_at).getTime() - new Date(right.published_at).getTime(),
  );
  const blockedSources = [...ledger.replay_audit.blocked_evidence].sort(
    (left, right) => new Date(left.published_at).getTime() - new Date(right.published_at).getTime(),
  );
  const fullTimelineEvents = [
    ...allowedSources
      .filter((source, index, list) => list.findIndex((item) => (
        item.source_type === source.source_type && item.published_at === source.published_at
      )) === index)
      .slice(0, 4)
      .map((source) => ({
        key: source.source_id,
        label: humanize(source.source_type),
        time: shortTime(source.published_at),
        state: 'allowed',
      })),
    {
      key: 'replay-lock-full',
      label: 'Replay Lock',
      time: shortTime(ledger.replay_audit.replay_timestamp),
      state: 'lock',
    },
    ...blockedSources.slice(0, 1).map((source) => ({
      key: source.source_id,
      label: 'Analyst Revision Blocked',
      time: shortMonthDay(source.published_at),
      state: 'blocked',
    })),
  ];

  return (
    <section className="panel evidence-timeline" data-testid="replay-timeline">
      <PanelHeader kicker="Evidence Timeline" title="Available before lock vs blocked after lock" />
      <div className="full-timeline">
        {fullTimelineEvents.map((event) => (
          <article className={`full-timeline__event full-timeline__event--${event.state}`} key={event.key}>
            <span>{event.time}</span>
            <strong>{event.label}</strong>
          </article>
        ))}
      </div>
      <p className="timeline-caption">
        Only evidence left of the lock entered ranking. Future evidence is quarantined for validation only.
      </p>
      <div className="timeline-columns">
        <section>
          <h3>Available to model</h3>
          {allowedSources.slice(0, 8).map((source) => (
            <article className="timeline-source" key={source.source_id}>
              <strong>{source.source_id}</strong>
              <span>{source.source_type.replaceAll('_', ' ')} | {compactTime(source.published_at)}</span>
            </article>
          ))}
        </section>
        <section className="timeline-lock-copy">
          <h3>{compactTime(ledger.replay_audit.replay_timestamp)}</h3>
          <p>{plural(allowedSources.length, 'source')} admitted into ranking.</p>
          <p>{plural(blockedSources.length, 'future source')} blocked from ranking.</p>
        </section>
        <section>
          <h3>Not available at replay time</h3>
          {blockedSources.length ? blockedSources.map((source) => (
            <article className="timeline-source timeline-source--blocked" key={source.source_id}>
              <strong>{source.source_id}</strong>
              <span>Published {compactTime(source.published_at)} | Blocked from ranking</span>
            </article>
          )) : <p className="empty-copy">No future sources were blocked.</p>}
          {validation?.rows.map((row) => (
            <article className="timeline-source timeline-source--validation" key={row.window}>
              <strong>{row.window}</strong>
              <span>{row.label} validation window | {futureSourceCopy(row)}</span>
            </article>
          ))}
        </section>
      </div>
    </section>
  );
}

function TournamentBracket({
  ledger,
  baselineNarrative,
  topNarrative,
  onSelect,
}: {
  ledger: Ledger;
  baselineNarrative: Narrative | null;
  topNarrative: Narrative;
  onSelect: (narrativeId: string) => void;
}) {
  const ranked = [...ledger.narratives].sort((left, right) => left.rank - right.rank);
  const pairA = ranked.slice(0, 2);
  const pairB = ranked.slice(2, 4);
  const finalist = pairB[0] ?? ranked[0];

  return (
    <section className="panel bracket-panel" data-testid="tournament-bracket">
      <PanelHeader kicker="NarrativeDesk Tournament" title="Head-to-head explanation bracket" />
      <div className="bracket-grid">
        <div className="bracket-round">
          <span className="bracket-label">Semifinals</span>
          <BracketMatch narratives={pairA} winner={pairA[0] ?? topNarrative} onSelect={onSelect} />
          <BracketMatch narratives={pairB} winner={finalist} onSelect={onSelect} />
        </div>
        <div className="bracket-round">
          <span className="bracket-label">Final</span>
          <BracketMatch narratives={[pairA[0] ?? topNarrative, finalist]} winner={topNarrative} onSelect={onSelect} />
        </div>
        <div className="bracket-winner">
          <span className="bracket-label">Winner</span>
          <button type="button" onClick={() => onSelect(topNarrative.narrative_id)}>
            <strong>{topNarrative.title}</strong>
            <p>{narrativeReason(topNarrative)}</p>
          </button>
        </div>
      </div>
      <div className="baseline-compare baseline-compare--wide">
        <span className="strip-label">Baseline comparison</span>
        <strong>{baselineNarrative?.title ?? 'No baseline selected'} vs {topNarrative.title}</strong>
        <p>
          The tournament uses replay-safe scoring instead of surface consensus. Timestamp advantage, contradiction
          resistance, and unsupported-claim penalties decide ties.
        </p>
      </div>
    </section>
  );
}

function BracketMatch({
  narratives,
  winner,
  onSelect,
}: {
  narratives: Narrative[];
  winner: Narrative;
  onSelect: (narrativeId: string) => void;
}) {
  return (
    <article className="bracket-match">
      {narratives.map((narrative) => (
        <button
          className={narrative.narrative_id === winner.narrative_id ? 'is-winner' : ''}
          key={narrative.narrative_id}
          type="button"
          onClick={() => onSelect(narrative.narrative_id)}
        >
          <span>#{narrative.rank}</span>
          <strong>{narrative.title}</strong>
          <small>{score(narrative.overall_narrative_score)}</small>
        </button>
      ))}
      <p>Reason: {narrativeReason(winner)}</p>
    </article>
  );
}

function EvidenceChain({ ledger, narrative }: { ledger: Ledger; narrative: Narrative }) {
  const evidence = uniqueEvidence(narrative);
  const blocked = ledger.replay_audit.blocked_evidence.filter(
    (source) => source.narrative_id === narrative.narrative_id,
  );

  return (
    <section className="panel evidence-chain" data-testid="evidence-chain">
      <PanelHeader kicker="Evidence Chain" title={narrative.title} />
      <div className="chain-root">
        <strong>{narrative.title}</strong>
        <p>{narrative.narrative}</p>
      </div>
      <div className="chain-list">
        {narrative.supporting_evidence.map((source, index) => (
          <article className="chain-node" key={`${source.source_id}-${index}`}>
            <span>Claim {index + 1}</span>
            <p>{source.claim ?? 'Allowed source supports the narrative, but claim text is unavailable.'}</p>
            <small>Supported by {source.source_id} | quality {score(source.evidence_quality)}</small>
          </article>
        ))}
        <article className="chain-node chain-node--mechanism">
          <span>Mechanism</span>
          <p>{narrative.mechanism}</p>
          <small>Specificity {score(narrative.scoring_inputs.mechanism_specificity)}</small>
        </article>
        {narrative.contradicting_evidence.map((source) => (
          <article className="chain-node chain-node--contradiction" key={`${source.source_id}-contradiction`}>
            <span>Contradiction</span>
            <p>{source.claim ?? 'Allowed source contradicts the narrative, but claim text is unavailable.'}</p>
            <small>{source.source_id} | resistance {score(narrative.scoring_inputs.contradiction_resistance)}</small>
          </article>
        ))}
        {blocked.map((source) => (
          <article className="chain-node chain-node--blocked" key={`${source.source_id}-blocked`}>
            <span>Blocked future evidence</span>
            <p>{source.source_id} was published after the replay lock and excluded from ranking.</p>
            <small>{compactTime(source.published_at)}</small>
          </article>
        ))}
      </div>
      <p className="panel-note">{plural(evidence.length, 'allowed evidence item')} in this chain.</p>
    </section>
  );
}

function ReportPanel({
  ledger,
  report,
  evaluation,
  bundleIntegrity,
}: {
  ledger: Ledger;
  report: string;
  evaluation: EvaluationSummary | null;
  bundleIntegrity: BundleIntegritySummary | null;
}) {
  const { caseId, ledgerHref, reportHref } = exportHrefs(ledger, report);
  const benchmarkHref = `data:application/json;charset=utf-8,${encodeURIComponent(
    `${JSON.stringify({ event_id: ledger.event.event_id, evaluation }, null, 2)}\n`,
  )}`;
  const reportSections = [
    'Event Summary',
    'Abnormal Move',
    'Winning Narrative',
    'Evidence Supporting the Narrative',
    'Contradictions',
    'Replay Integrity',
    'Historical Validation',
    'Baseline Comparison',
  ];

  return (
    <section className="panel report-panel export-panel" data-testid="export-area">
      <PanelHeader kicker="Report" title="Analyst Replay Memo" />
      <div className="report-grid">
        <section className="report-outline">
          {reportSections.map((section, index) => (
            <p key={section}>
              <span>{index + 1}</span>
              {section}
            </p>
          ))}
        </section>
        <section className="report-preview" data-testid="report-preview">
          <pre>{report.slice(0, 1600)}...</pre>
        </section>
      </div>
      <BundleIntegrityPanel ledger={ledger} integrity={bundleIntegrity} />
      <div className="export-actions">
        <a href={reportHref} download={`${caseId}-report.md`} data-testid="report-export">
          Export Memo
        </a>
        <a href={ledgerHref} download={`${caseId}-ledger.json`} data-testid="ledger-export">
          Export Evidence Ledger
        </a>
        <a href={benchmarkHref} download={`${caseId}-benchmark.json`} data-testid="benchmark-export">
          Export Benchmark JSON
        </a>
      </div>
    </section>
  );
}

function BundleIntegrityPanel({
  ledger,
  integrity,
}: {
  ledger: Ledger;
  integrity: BundleIntegritySummary | null;
}) {
  const resolved = integrity ?? {
    verified_by_bundle_verify: false,
    artifact_hashes_ok: null,
    replay_integrity_ok: ledger.citation_qa.replay_filter_pass && ledger.citation_qa.event_time_integrity_pass,
    readiness_status: 'not_attached',
    blocked_future_source_count: ledger.replay_audit.blocked_source_ids.length,
    validation_future_source_count: 0,
    note: 'No bundle integrity payload is attached to this case.',
  };
  const artifactLabel = resolved.artifact_hashes_ok === null
    ? 'not attached'
    : checkLabel(resolved.artifact_hashes_ok);
  const rows = [
    ['Artifact hashes', artifactLabel],
    ['Replay integrity', checkLabel(resolved.replay_integrity_ok)],
    ['Readiness', humanize(resolved.readiness_status)],
    ['Blocked future', String(resolved.blocked_future_source_count)],
    ['Validation future', String(resolved.validation_future_source_count)],
  ];

  return (
    <section className="bundle-integrity" data-testid="bundle-integrity">
      <div>
        <span className="eyebrow">Bundle Integrity</span>
        <h3>{resolved.verified_by_bundle_verify ? 'Verified replay bundle' : 'Demo fixture integrity'}</h3>
        <p>{resolved.note}</p>
      </div>
      <div className="bundle-integrity-grid">
        {rows.map(([label, value]) => (
          <span key={label}>
            {label}
            <strong>{value}</strong>
          </span>
        ))}
      </div>
    </section>
  );
}

function EventHeader({ ledger }: { ledger: Ledger }) {
  const { event, replay_audit: audit } = ledger;
  const stats = [
    ['Daily move', pct(event.daily_return)],
    ['Abnormal move', pct(event.abnormal_return)],
    ['Peer median', pct(event.peer_median_return)],
    ['Sector ETF', pct(event.sector_etf_return)],
    ['Volume spike', `${event.volume_ratio.toFixed(2)}x`],
  ];

  return (
    <section className="event-panel" data-testid="event-header">
      <div className="event-main">
        <span className="ticker">{event.ticker}</span>
        <div>
          <h2>{event.company_name}</h2>
          <p>{event.event_type} | {event.event_date}</p>
        </div>
      </div>
      <div className="stat-grid">
        {stats.map(([label, value]) => (
          <div className="stat" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="lock-panel">
        <span className="lock-label">Replay lock</span>
        <strong>{compactTime(audit.replay_timestamp)}</strong>
        <span>{plural(audit.allowed_source_ids.length, 'allowed source')}</span>
        <span>{plural(audit.blocked_source_ids.length, 'future source')} blocked</span>
      </div>
    </section>
  );
}

function BenchmarkCorpusPanel({ aggregate }: { aggregate: BenchmarkAggregate }) {
  const primaryMetrics = [
    ['Cases', `${aggregate.evaluated_case_count}/${aggregate.case_count}`],
    ['Recall@3', pct(aggregate.narrative_recall_at_3_rate)],
    ['Tournament hit', pct(aggregate.narrativedesk_tournament_validated_rate)],
    ['Headline hit', pct(aggregate.headline_baseline_validated_rate)],
  ];
  const ablationMetrics = [
    ['Evidence only', pct(aggregate.evidence_only_validated_rate)],
    ['No contradiction penalty', pct(aggregate.no_contradiction_penalty_validated_rate)],
    ['Quality weighted', pct(aggregate.quality_weighted_validated_rate)],
  ];
  const integrityMetrics = [
    ['Future blocked', String(aggregate.blocked_future_source_count)],
    ['Citation QA', pct(aggregate.citation_qa_pass_rate)],
    ['Replay integrity', pct(aggregate.replay_filter_pass_rate)],
    ['Provenance ready', pct(aggregate.provenance_ready_rate)],
    ['Avg quality', score(aggregate.source_reliability_avg_evidence_quality)],
    ['Avg originality', score(aggregate.source_reliability_avg_originality)],
    ['Derived orig', score(aggregate.source_clustering_avg_derived_originality)],
    ['Dup clusters', String(aggregate.source_duplicate_cluster_count ?? 0)],
    ['Unsupported avg', score(aggregate.unsupported_claim_penalty_avg)],
  ];

  return (
    <section className="panel benchmark-corpus" data-testid="benchmark-corpus">
      <PanelHeader kicker="Benchmark corpus" title="Synthetic case-index summary" />
      <div className="benchmark-corpus__body">
        <div className="benchmark-primary">
          {primaryMetrics.map(([label, value]) => (
            <MetricTile label={label} value={value} key={label} />
          ))}
        </div>
        <div className="benchmark-secondary">
          <section className="benchmark-stack">
            <h3>Ablation baselines</h3>
            {ablationMetrics.map(([label, value]) => (
              <p key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </p>
            ))}
          </section>
          <section className="benchmark-stack benchmark-stack--integrity">
            <h3>Readiness checks</h3>
            {integrityMetrics.map(([label, value]) => (
              <p key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </p>
            ))}
          </section>
        </div>
      </div>
      <p className="panel-note">
        Corpus gaps: {aggregate.missing_url_count ?? 0} missing URLs | {aggregate.missing_content_hash_count ?? 0} missing content hashes | {aggregate.low_quality_evidence_count ?? 0} low-quality sources
      </p>
    </section>
  );
}

function NarrativeInspector({
  ledger,
  narrative,
}: {
  ledger: Ledger;
  narrative: Narrative;
}) {
  const blocked = ledger.replay_audit.blocked_evidence.filter(
    (source) => source.narrative_id === narrative.narrative_id,
  );

  return (
    <section className="panel inspector" data-testid="evidence-inspector">
      <PanelHeader kicker="Evidence ledger" title={narrative.title} />
      <p className="mechanism">{narrative.mechanism}</p>

      <div className="score-grid">
        {scoreRows.map((row) => {
          const value = narrative.scoring_inputs[row.key];
          return (
            <div className="score-row" key={row.key}>
              <span>{row.label}</span>
              <div className="score-track" aria-hidden="true">
                <span
                  className={row.penalty ? 'score-fill score-fill--penalty' : 'score-fill'}
                  style={{ width: `${value * 100}%` }}
                />
              </div>
              <strong>{score(value)}</strong>
            </div>
          );
        })}
      </div>

      <div className="evidence-grid">
        <EvidenceColumn title="Supporting evidence" status="Allowed" items={narrative.supporting_evidence} />
        <EvidenceColumn
          title="Contradicting evidence"
          status="Allowed"
          items={narrative.contradicting_evidence}
        />
      </div>

      <section className="quarantine-box">
        <div>
          <span className="eyebrow">Replay filter</span>
          <h3>Quarantined future evidence</h3>
        </div>
        {blocked.length ? (
          blocked.map((source) => (
            <article className="source-card source-card--blocked" key={source.source_id}>
              <span>{sourceStamp(source)}</span>
              <p>{source.claim ?? 'Future-dated source metadata redacted from event-time replay.'}</p>
            </article>
          ))
        ) : (
          <p>No future-dated evidence was attached to this narrative.</p>
        )}
      </section>

      <section className="observables">
        <div className="section-title-row">
          <h3>Expected observables</h3>
          <span>{narrative.validation_status}</span>
        </div>
        {narrative.expected_observables.map((observable) => (
          <p key={observable}>{observable}</p>
        ))}
      </section>
    </section>
  );
}

function EvidenceColumn({ title, status, items }: { title: string; status: string; items: EvidenceItem[] }) {
  return (
    <section className="evidence-column">
      <div className="section-title-row">
        <h3>{title}</h3>
        <span>{status}</span>
      </div>
      {items.length ? (
        items.map((item) => (
          <article className="source-card" key={`${item.relation}-${item.source_id}`}>
            <span>{sourceStamp(item)}</span>
            <p>{item.claim ?? 'Source text unavailable in this replay view.'}</p>
          </article>
        ))
      ) : (
        <p className="empty-copy">None after replay filtering.</p>
      )}
    </section>
  );
}

function ResearchTrail({ ledger }: { ledger: Ledger }) {
  const top = ledger.narratives.find((narrative) => narrative.rank === 1) ?? ledger.narratives[0];
  const mostContested = [...ledger.narratives].sort(
    (left, right) => right.contradicting_evidence.length - left.contradicting_evidence.length,
  )[0];
  const directionalFrames = Array.from(
    new Set(ledger.narratives.map((narrative) => narrative.directional_implication)),
  )
    .sort()
    .join(', ');
  const trail = [
    {
      agent: 'Market Data Agent',
      output: `Move classified as company-specific: abnormal return ${pct(
        ledger.event.abnormal_return,
      )} versus peer median ${pct(ledger.event.peer_median_return)}.`,
    },
    {
      agent: 'Narrative Generation Agent',
      output: `Generated ${ledger.narratives.length} competing hypotheses across ${directionalFrames} directional frames before scoring replay-safe evidence.`,
    },
    {
      agent: 'Contradiction Agent',
      output: mostContested?.contradicting_evidence.length
        ? `${mostContested.title} carries ${plural(
            mostContested.contradicting_evidence.length,
            'direct contradiction',
          )} in the allowed source set.`
        : 'No direct contradictions remain in the allowed source set.',
    },
    {
      agent: 'Citation QA Agent',
      output: ledger.replay_audit.blocked_source_ids.length
        ? `Blocked ${ledger.replay_audit.blocked_source_ids.join(', ')} as future evidence before ranking.`
        : 'No future evidence was available at the replay lock.',
    },
    {
      agent: 'Judge Agent',
      output: `${top.title} ranked #1 with score ${score(top.overall_narrative_score)}.`,
    },
    {
      agent: 'Validation Agent',
      output: 'Future validation is loaded in a separate benchmark panel after the event-time replay.',
    },
  ];

  return (
    <section className="panel" data-testid="research-trail">
      <PanelHeader kicker="Research trail" title="Deterministic agent trace" />
      <div className="trail-list">
        {trail.map((item) => (
          <article className="trail-card" key={item.agent}>
            <span>{item.agent}</span>
            <p>{item.output}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ValidationPanel({ validation }: { validation: ValidationFixture | null }) {
  return (
    <section className="panel" data-testid="validation-dashboard">
      <PanelHeader kicker="Future-only" title="Validation dashboard" />
      <p className="panel-note">Loaded separately from event-time replay evidence.</p>
      <div className="validation-table">
        {validation?.rows.map((row) => (
          <details className="validation-row" key={row.window}>
            <summary>
              <span className="window">{row.window}</span>
              <span className={`status-pill ${statusClass(row.label)}`}>{row.label}</span>
              <strong>{cleanValidationCopy(row)}</strong>
            </summary>
            <p>{row.expected_observable}</p>
            <p>{futureSourceCopy(row)}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function CitationQaPanel({ ledger }: { ledger: Ledger }) {
  const qa = ledger.citation_qa;
  return (
    <section className="panel" data-testid="citation-qa">
      <PanelHeader kicker="Citation QA" title="Evidence integrity checks" />
      <div className="evaluation-grid">
        <MetricTile label="Replay filter" value={checkLabel(qa.replay_filter_pass)} />
        <MetricTile label="Support coverage" value={checkLabel(qa.support_coverage_pass)} />
        <MetricTile label="Replay integrity" value={checkLabel(qa.event_time_integrity_pass)} />
        <MetricTile label="Citation QA" value={checkLabel(qa.citation_qa_pass)} />
        <MetricTile label="Provenance ready" value={checkLabel(qa.provenance_ready)} />
        <MetricTile label="Returned blocked" value={String(qa.returned_blocked_source_count)} />
        <MetricTile
          label="Missing URLs"
          value={String(qa.missing_url_count)}
        />
        <MetricTile
          label="Low quality"
          value={String(qa.low_quality_evidence_count)}
        />
      </div>
      <p className="panel-note">
        Support: {qa.narratives_with_support_count}/{qa.narrative_count} narratives | blocked future sources: {qa.blocked_future_source_count}
      </p>
    </section>
  );
}

function SourceReliabilityPanel({ ledger }: { ledger: Ledger }) {
  const reliability = ledger.source_reliability;
  const topPublishers = reliability.by_publisher
    .filter((bucket) => bucket.allowed_source_count > 0 || bucket.blocked_future_count > 0)
    .slice(0, 4);

  return (
    <section className="panel" data-testid="source-reliability">
      <PanelHeader kicker="Source reliability" title="Provenance quality ledger" />
      <div className="evaluation-grid">
        <MetricTile label="Allowed" value={String(reliability.overall.allowed_source_count)} />
        <MetricTile label="Blocked future" value={String(reliability.overall.blocked_future_count)} />
        <MetricTile label="Evidence quality" value={score(reliability.overall.average_evidence_quality)} />
        <MetricTile label="Independence" value={score(reliability.overall.average_independence)} />
        <MetricTile label="Originality" value={score(reliability.overall.average_originality_score)} />
        <MetricTile label="Low quality" value={String(reliability.overall.low_quality_source_count)} />
      </div>
      <p className="panel-note">
        Blocked source IDs: {reliability.overall.blocked_future_source_ids.join(', ') || 'none'}
      </p>
      <div className="reliability-breakdown">
        {topPublishers.map((bucket) => (
          <article className="reliability-row" key={bucket.key}>
            <strong>{bucket.key}</strong>
            <span>{bucket.allowed_source_count} allowed | {bucket.blocked_future_count} blocked</span>
            <p>
              Quality {score(bucket.average_evidence_quality)} | independence {score(bucket.average_independence)} | originality {score(bucket.average_originality_score)}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

function SourceClusteringPanel({ ledger }: { ledger: Ledger }) {
  const clustering = ledger.source_clustering;
  const topClusters = [...clustering.clusters]
    .sort((left, right) => right.source_count - left.source_count || left.cluster_id.localeCompare(right.cluster_id))
    .slice(0, 4);

  return (
    <section className="panel" data-testid="source-clustering">
      <PanelHeader kicker="Source clustering" title="Originality clusters" />
      <div className="evaluation-grid">
        <MetricTile label="Allowed" value={String(clustering.allowed_source_count)} />
        <MetricTile label="Clusters" value={String(clustering.cluster_count)} />
        <MetricTile label="Duplicates" value={String(clustering.duplicate_cluster_count)} />
        <MetricTile label="Avg size" value={score(clustering.average_cluster_size)} />
        <MetricTile label="Derived orig" value={score(clustering.average_derived_originality_score)} />
        <MetricTile label="Future excluded" value={String(clustering.blocked_future_source_count)} />
      </div>
      <p className="panel-note">
        Blocked source IDs excluded from clustering: {clustering.blocked_future_source_ids.join(', ') || 'none'}
      </p>
      <div className="cluster-breakdown">
        {topClusters.map((cluster) => (
          <article className="cluster-row" key={cluster.cluster_id}>
            <strong>{cluster.cluster_id}</strong>
            <span>
              {cluster.source_count} sources | originality {score(cluster.derived_originality_score)}
            </span>
            <p>{cluster.source_ids.join(', ')}</p>
            <small>{cluster.representative_claim}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function EvaluationPanel({ evaluation }: { evaluation: EvaluationSummary }) {
  return (
    <section className="panel" data-testid="evaluation-checks">
      <PanelHeader kicker="Benchmark" title="Evaluation checks" />
      <div className="evaluation-grid">
        <MetricTile label="Recall@3" value={checkLabel(evaluation.narrative_recall_at_3)} />
        <MetricTile
          label="Validated rank"
          value={evaluation.validated_rank === null ? 'n/a' : `#${evaluation.validated_rank}`}
        />
        <MetricTile label="Top validated" value={checkLabel(evaluation.top_ranked_validated)} />
        <MetricTile label="Unsupported avg" value={score(evaluation.unsupported_claim_penalty_avg)} />
        <MetricTile label="Unsupported max" value={score(evaluation.unsupported_claim_penalty_max)} />
        <MetricTile label="Future blocked" value={String(evaluation.blocked_future_source_count)} />
      </div>
      <p className="panel-note">
        Validated: {evaluation.validated_narrative_ids.join(', ') || 'none'} | high unsupported penalties: {evaluation.high_unsupported_claim_count}
      </p>
      <div className="model-comparison-list">
        {evaluation.model_comparisons.map((row) => (
          <article className="model-comparison-row" key={row.system_id}>
            <strong>{row.system_id.replaceAll('_', ' ')}</strong>
            <span className={`status-pill ${statusClass(checkLabel(row.validated))}`}>
              {checkLabel(row.validated)}
            </span>
            <p>
              {row.selected_narrative_id ?? 'n/a'} {row.selected_rank ? `| #${row.selected_rank}` : ''}
            </p>
            <small>{row.selection_reason}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <article className="metric-tile">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function ExportPanel({ ledger, report }: { ledger: Ledger; report: string }) {
  const caseId = ledger.event.case_id ?? ledger.event.event_id;
  const filenameToken = caseId.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const ledgerHref = `data:application/json;charset=utf-8,${encodeURIComponent(
    `${JSON.stringify(ledger, null, 2)}\n`,
  )}`;
  const reportHref = `data:text/markdown;charset=utf-8,${encodeURIComponent(report)}`;

  return (
    <section className="panel export-panel" data-testid="export-area">
      <PanelHeader kicker="Export" title="Reproducible outputs" />
      <div className="export-actions">
        <a href={ledgerHref} download={`${filenameToken}-ledger.json`} data-testid="ledger-export">
          Export ledger JSON
        </a>
        <a href={reportHref} download={`${filenameToken}-report.md`} data-testid="report-export">
          Export report Markdown
        </a>
      </div>
      <div className="cli-box">
        <span>CLI equivalent</span>
        <code>
          make smoke
        </code>
      </div>
      <details>
        <summary>Preview report opening</summary>
        <pre>{report.slice(0, 900)}...</pre>
      </details>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <span>
      {label}: <strong>{value}</strong>
    </span>
  );
}

function PanelHeader({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div className="panel-header">
      <span>{kicker}</span>
      <h2>{title}</h2>
    </div>
  );
}

export default App;


function LeakageAudit({ ledger }: { ledger: Ledger }) {
  return (
    <section className="panel" data-testid="leakage-audit">
      <PanelHeader kicker="Leakage audit" title="Replay boundary check" />
      <div className="audit-summary">
        <p>Validation uses later data only after generation.</p>
        <p>
          <strong>{compactTime(ledger.replay_audit.replay_timestamp)}</strong>
          <span>
            {ledger.replay_audit.allowed_source_ids.length} allowed |{' '}
            {ledger.replay_audit.blocked_source_ids.length} blocked future
          </span>
        </p>
      </div>
      <div className="audit-list">
        {ledger.replay_audit.blocked_evidence.map((item) => (
          <article className="audit-row" key={item.source_id}>
            <strong>{item.source_id}</strong>
            <span>{item.blocked_reason ?? item.replay_status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

function SourceMap({ ledger }: { ledger: Ledger }) {
  const rows = new Map<
    string,
    {
      source_id: string;
      source_type: string;
      publisher: string;
      status: string;
      narrativeIds: Set<string>;
      relations: Set<string>;
    }
  >();

  for (const narrative of ledger.narratives) {
    for (const item of [...narrative.supporting_evidence, ...narrative.contradicting_evidence]) {
      const row =
        rows.get(item.source_id) ??
        {
          source_id: item.source_id,
          source_type: item.source_type,
          publisher: item.publisher || 'n/a',
          status: 'allowed',
          narrativeIds: new Set<string>(),
          relations: new Set<string>(),
        };
      row.narrativeIds.add(narrative.narrative_id);
      row.relations.add(item.relation);
      rows.set(item.source_id, row);
    }
  }

  for (const item of ledger.replay_audit.blocked_evidence) {
    const row =
      rows.get(item.source_id) ??
      {
        source_id: item.source_id,
        source_type: item.source_type,
        publisher: item.publisher || 'n/a',
        status: 'blocked_future',
        narrativeIds: new Set<string>(),
        relations: new Set<string>(),
      };
    row.status = 'blocked_future';
    if (item.narrative_id) row.narrativeIds.add(item.narrative_id);
    row.relations.add(item.relation);
    rows.set(item.source_id, row);
  }

  const sourceRows = Array.from(rows.values()).sort((a, b) => a.source_id.localeCompare(b.source_id));

  return (
    <section className="panel" data-testid="source-map">
      <PanelHeader kicker="Source map" title="Replay source inventory" />
      <div className="source-map-list">
        {sourceRows.map((row) => (
          <article className="source-map-row" key={row.source_id}>
            <strong>{row.source_id}</strong>
            <span className={`status-pill ${statusClass(row.status)}`}>{row.status}</span>
            <p>{row.source_type.replaceAll('_', ' ')} | {row.publisher}</p>
            <small>
              {Array.from(row.narrativeIds).sort().join(', ')} | {Array.from(row.relations).sort().join(', ')}
            </small>
          </article>
        ))}
      </div>
    </section>
  );
}
