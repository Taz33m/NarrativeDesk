import { useEffect, useMemo, useState } from 'react';
import type { EvidenceItem, Ledger, Narrative, ValidationFixture } from './types';

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

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'n/a';
  return `${(value * 100).toFixed(1)}%`;
}

function score(value: number): string {
  return value.toFixed(2);
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

function sourceStamp(source: EvidenceItem): string {
  return `${source.source_id} | ${source.source_type.replaceAll('_', ' ')} | ${compactTime(
    source.published_at,
  )}`;
}

function labelForNarrative(narrative: Narrative, validation: ValidationFixture | null): string {
  const row = validation?.rows.find((item) => item.narrative_id === narrative.narrative_id && item.label === 'validated');
  return row?.label ?? narrative.validation_status;
}

function App() {
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [validation, setValidation] = useState<ValidationFixture | null>(null);
  const [report, setReport] = useState<string>('');
  const [selectedId, setSelectedId] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function loadDemo() {
      try {
        const demoAsset = (name: string) => `${import.meta.env.BASE_URL}demo/${name}`;
        const [ledgerResponse, validationResponse, reportResponse] = await Promise.all([
          fetch(demoAsset('ledger.json')),
          fetch(demoAsset('validation.json')),
          fetch(demoAsset('report.md')),
        ]);
        if (!ledgerResponse.ok || !validationResponse.ok || !reportResponse.ok) {
          throw new Error('Demo assets are missing. Run `make web-data` from the repo root.');
        }
        const nextLedger = (await ledgerResponse.json()) as Ledger;
        const nextValidation = (await validationResponse.json()) as ValidationFixture;
        const nextReport = await reportResponse.text();
        setLedger(nextLedger);
        setValidation(nextValidation);
        setReport(nextReport);
        setSelectedId(nextLedger.narratives[0]?.narrative_id ?? '');
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : 'Unable to load demo assets.');
      }
    }

    loadDemo();
  }, []);

  const selectedNarrative = useMemo(() => {
    return ledger?.narratives.find((narrative) => narrative.narrative_id === selectedId) ?? ledger?.narratives[0] ?? null;
  }, [ledger, selectedId]);

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
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">NarrativeDesk v0</p>
          <h1>Timestamp-locked narrative replay</h1>
          <p className="dek">
            Competing explanations for an abnormal earnings move, ranked by evidence,
            mechanism, contradictions, crowding, and forward observables.
          </p>
        </div>
        <div className="research-note">Research support only. Not investment advice.</div>
      </header>

      <EventHeader ledger={ledger} />

      <section className="thesis-strip">
        <div>
          <span className="strip-label">Surface narrative</span>
          <strong>Margin disappointment</strong>
        </div>
        <div className="strip-arrow">ranked below</div>
        <div>
          <span className="strip-label">Best-supported narrative</span>
          <strong>Forward demand slowdown</strong>
        </div>
      </section>

      <div className="workbench-grid">
        <section className="panel panel--tournament" data-testid="narrative-tournament">
          <PanelHeader kicker="Tournament" title="Ranked competing explanations" />
          <div className="narrative-list">
            {ledger.narratives.map((narrative) => (
              <button
                className={`narrative-card ${
                  narrative.narrative_id === selectedNarrative.narrative_id ? 'is-selected' : ''
                }`}
                key={narrative.narrative_id}
                type="button"
                aria-pressed={narrative.narrative_id === selectedNarrative.narrative_id}
                onClick={() => setSelectedId(narrative.narrative_id)}
              >
                <span className="rank">#{narrative.rank}</span>
                <span className="narrative-card__body">
                  <span className="narrative-title">{narrative.title}</span>
                  <span className="narrative-summary">{narrative.narrative}</span>
                  <span className="mini-metrics">
                    <Metric label="Evidence" value={score(narrative.scoring_inputs.evidence_strength)} />
                    <Metric
                      label="Contradiction"
                      value={score(1 - narrative.scoring_inputs.contradiction_resistance)}
                    />
                    <Metric label="Crowding" value={score(narrative.scoring_inputs.crowding_risk)} />
                  </span>
                </span>
                <span className="score-pill">{score(narrative.overall_narrative_score)}</span>
                <span className={`status-pill status-pill--${labelForNarrative(narrative, validation)}`}>
                  {labelForNarrative(narrative, validation)}
                </span>
              </button>
            ))}
          </div>
        </section>

        <NarrativeInspector
          ledger={ledger}
          narrative={selectedNarrative}
          validation={validation}
        />
      </div>

      <div className="lower-grid">
        <ResearchTrail ledger={ledger} validation={validation} />
        <ValidationPanel validation={validation} />
        <ExportPanel report={report} />
      </div>
    </main>
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
        <span>{audit.allowed_source_ids.length} allowed sources</span>
        <span>{audit.blocked_source_ids.length} future source blocked</span>
      </div>
    </section>
  );
}

function NarrativeInspector({
  ledger,
  narrative,
  validation,
}: {
  ledger: Ledger;
  narrative: Narrative;
  validation: ValidationFixture | null;
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
              <p>{source.claim}</p>
            </article>
          ))
        ) : (
          <p>No future-dated evidence was attached to this narrative.</p>
        )}
      </section>

      <section className="observables">
        <div className="section-title-row">
          <h3>Expected observables</h3>
          <span>{labelForNarrative(narrative, validation)}</span>
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
            <p>{item.claim}</p>
          </article>
        ))
      ) : (
        <p className="empty-copy">None after replay filtering.</p>
      )}
    </section>
  );
}

function ResearchTrail({ ledger, validation }: { ledger: Ledger; validation: ValidationFixture | null }) {
  const top = ledger.narratives[0];
  const margin = ledger.narratives.find((narrative) => narrative.title.includes('Margin'));
  const trail = [
    {
      agent: 'Market Data Agent',
      output: `Move classified as company-specific: abnormal return ${pct(
        ledger.event.abnormal_return,
      )} versus peer median ${pct(ledger.event.peer_median_return)}.`,
    },
    {
      agent: 'Narrative Generation Agent',
      output: `Generated ${ledger.narratives.length} competing hypotheses including bearish, bullish, sector, and overreaction narratives.`,
    },
    {
      agent: 'Contradiction Agent',
      output: `${margin?.title ?? 'Margin narrative'} weakened by direct contradictory evidence in the allowed source set.`,
    },
    {
      agent: 'Citation QA Agent',
      output: `Blocked ${ledger.replay_audit.blocked_source_ids.join(', ')} as future evidence before ranking.`,
    },
    {
      agent: 'Judge Agent',
      output: `${top.title} ranked #1 with score ${score(top.overall_narrative_score)}.`,
    },
    {
      agent: 'Validation Agent',
      output: validation?.rows.find((row) => row.label === 'validated')?.what_happened ?? 'Validation pending.',
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
          <article className="validation-row" key={row.window}>
            <span className="window">{row.window}</span>
            <span className={`status-pill status-pill--${row.label}`}>{row.label}</span>
            <p>{row.expected_observable}</p>
            <strong>{row.what_happened}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

function ExportPanel({ report }: { report: string }) {
  const demoAsset = (name: string) => `${import.meta.env.BASE_URL}demo/${name}`;
  return (
    <section className="panel export-panel" data-testid="export-area">
      <PanelHeader kicker="Export" title="Reproducible outputs" />
      <div className="export-actions">
        <a href={demoAsset('ledger.json')} download>
          Export ledger JSON
        </a>
        <a href={demoAsset('report.md')} download>
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
