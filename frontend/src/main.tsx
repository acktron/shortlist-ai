import { useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, useNavigate } from 'react-router-dom';
import { api, login, logout } from './api/client';
import { EmptyState, ErrorState, PageHeader, Skeleton, StatusBadge } from './components/shared';
import { UploadScreen } from './components/upload';
import './styles.css';

type Req = { id: string; title: string; location: string; jd_text: string; status: string; client_name?: string };
type Summary = { candidates: number; strong_matches: number; submitted: number; uploads: number };
type Draft = {
  title: string;
  location: string;
  experience: { min_years?: number | null; max_years?: number | null };
  must_have_skills: { name: string; aliases: string[] }[];
  nice_to_have_skills: { name: string; aliases: string[] }[];
  notice: { max_days?: number | null };
  ctc: { max_lpa?: number | null };
  field_confidence: Record<string, string>;
  missing_fields: string[];
};
type Criterion = { id: string; kind: 'must_skill' | 'nice_skill' | 'experience' | 'notice' | 'ctc' | 'location'; label: string; weight: number; params: Record<string, unknown> };
type ScorecardData = { version: number; criteria: Criterion[]; ai_draft: Draft; ai_confidence: Record<string, string> };
type Counts = { candidates: number; strong_matches: number; submitted: number; uploads: number };
const accounts = [['Recruiter', 'recruiter@companya.demo'], ['Delivery head', 'head@companya.demo'], ['Meridian client', 'priya@meridianbank.demo'], ['Kestrel client', 'rahul@kestrelit.demo']];
const defaultWeights = { must_skill: 3, nice_skill: 1, experience: 3, notice: 2, ctc: 1, location: 1 };
const emptyDraft: Draft = { title: '', location: '', experience: {}, must_have_skills: [], nice_to_have_skills: [], notice: {}, ctc: {}, field_confidence: {}, missing_fields: [] };
function normalizeDraft(value: Partial<Draft> | undefined, fallbackLocation: string): Draft {
  return { ...emptyDraft, ...value, location: value?.location || fallbackLocation, experience: { ...emptyDraft.experience, ...value?.experience }, must_have_skills: value?.must_have_skills || [], nice_to_have_skills: value?.nice_to_have_skills || [], notice: { ...emptyDraft.notice, ...value?.notice }, ctc: { ...emptyDraft.ctc, ...value?.ctc }, field_confidence: value?.field_confidence || {}, missing_fields: value?.missing_fields || [] };
}
function draftFromScorecard(value: ScorecardData, fallbackLocation: string): Draft {
  const draft = normalizeDraft(value.ai_draft, fallbackLocation);
  const criterion = (kind: Criterion['kind']) => value.criteria.find(item => item.kind === kind);
  const experience = criterion('experience')?.params || {};
  const notice = criterion('notice')?.params || {};
  const ctc = criterion('ctc')?.params || {};
  return {
    ...draft,
    experience: { min_years: draft.experience.min_years ?? (experience as any).min_years, max_years: draft.experience.max_years ?? (experience as any).max_years },
    notice: { max_days: draft.notice.max_days ?? (notice as any).max_days },
    ctc: { max_lpa: draft.ctc.max_lpa ?? (ctc as any).max_lpa },
    must_have_skills: draft.must_have_skills.length ? draft.must_have_skills : value.criteria.filter(item => item.kind === 'must_skill').map(item => ({ name: item.label, aliases: ((item.params.aliases as string[]) || []) })),
    nice_to_have_skills: draft.nice_to_have_skills.length ? draft.nice_to_have_skills : value.criteria.filter(item => item.kind === 'nice_skill').map(item => ({ name: item.label, aliases: ((item.params.aliases as string[]) || []) })),
  };
}

function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('Demo@1234');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError('');
    try { const data = await login(email, password); localStorage.setItem('token', data.access_token); localStorage.setItem('user', JSON.stringify(data.user)); nav(data.user.role === 'client' ? '/portal' : '/recruiter'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to sign in'); }
    finally { setLoading(false); }
  }
  return <main className="login"><section><div className="brand">Shortlist<span>AI</span></div><h1>Sign in</h1><form onSubmit={submit}>
    <label>Email<input value={email} onChange={event => setEmail(event.target.value)} type="email" required /></label>
    <label>Password<input value={password} onChange={event => setPassword(event.target.value)} type="password" required /></label>
    {error && <ErrorState message={error} retry={() => setError('')} />}
    <button type="submit" disabled={loading}>{loading ? 'Signing in…' : 'Continue'}</button>
  </form><div className="chips">{accounts.map(([label, address]) => <button type="button" className="chip" key={address} onClick={() => { setEmail(address); setPassword('Demo@1234'); }}>{label}</button>)}</div></section></main>;
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="shell"><header><div className="brand">Shortlist<span>AI</span></div><button type="button" className="link" onClick={() => { logout(); window.location.assign('/login'); }}>Sign out</button></header>{children}</div>;
}

function Recruiter() {
  const [rows, setRows] = useState<Req[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = () => { setLoading(true); setError(''); void api<Req[]>('/requisitions').then(setRows).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load requisitions')).finally(() => setLoading(false)); };
  useEffect(load, []);
  return <main><PageHeader title="Requisitions" description="Open a role to review the scorecard, applicants, and pipeline." />
    {loading ? <Skeleton rows={4} /> : error ? <ErrorState message={error} retry={load} /> : rows.length === 0 ? <EmptyState title="No requisitions yet" /> : <div className="req-grid">{rows.map(req => <button type="button" className="req-card" key={req.id} onClick={() => window.location.assign(`/recruiter/requisitions/${req.id}/scorecard`)}><strong>{req.title}</strong><span>{req.client_name || 'Client'} · {req.location}</span><small>Open requisition workspace</small><StatusBadge status={req.status} /></button>)}</div>}
  </main>;
}

function HubTabs({ req, counts, tab }: { req: Req; counts: Counts; tab: string }) {
  const nav = useNavigate();
  const tabs = [['scorecard', 'Scorecard', ''], ['upload', 'Upload CVs', ` ${counts.uploads}`], ['candidates', 'Candidates', ` ${counts.candidates}`], ['pipeline', 'Pipeline', ` ${counts.submitted}`]];
  return <><PageHeader title={req.title} description={`${req.client_name || 'Client'} · ${req.location}`} /><nav className="tabs">{tabs.map(([key, label, count]) => <button type="button" className={tab === key ? 'active' : ''} onClick={() => nav(`/recruiter/requisitions/${req.id}/${key}`)} key={key}>{label}{count && <span className="tab-count">{count.trim()}</span>}</button>)}</nav></>;
}

function confirmField(field: string, value: unknown, jd: string): 'confirmed' | 'empty' | 'missing' {
  const text = jd.toLowerCase(); const raw = String(value ?? '').trim().toLowerCase();
  if (!raw) return 'empty';
  if (field === 'location') return text.includes(raw) ? 'confirmed' : 'missing';
  if (field === 'experience_min' || field === 'experience_max') {
    const range = text.match(/(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*(?:yr|year|yrs)/);
    if (!range) return 'missing';
    const expected = Number(field === 'experience_min' ? range[1] : range[2]);
    return Number(value) === expected ? 'confirmed' : 'missing';
  }
  if (field === 'notice') return new RegExp(`notice[^\\d]{0,30}${String(value)}`, 'i').test(jd) ? 'confirmed' : 'missing';
  if (field === 'ctc') return new RegExp(`(?:budget|up to)[^\\d]{0,30}${String(value)}\\s*lpa`, 'i').test(jd) ? 'confirmed' : 'missing';
  return text.includes(raw) ? 'confirmed' : 'missing';
}

function fieldState(label: string, state: string) { return <small className={state === 'confirmed' ? 'confirmed-note' : 'amber-note'}>{state === 'confirmed' ? 'Found in JD' : state === 'empty' ? 'Not found in JD — fill this in.' : `Check this value — it could not be found in the JD.`}</small>; }

function SkillCriterionList({ kind, criteria, onChange, onAdd, onRemove }: { kind: 'must_skill' | 'nice_skill'; criteria: Criterion[]; onChange: (id: string, next: Partial<Criterion>) => void; onAdd: () => void; onRemove: (id: string) => void }) {
  return <section className="criterion-section"><div className="section-title"><h3>{kind === 'must_skill' ? 'Must-have skills' : 'Nice-to-have skills'}</h3><button type="button" className="secondary small-button" onClick={onAdd}>Add skill</button></div>
    {criteria.length === 0 ? <p className="muted">No skills added yet.</p> : criteria.map(item => <div className="criterion" key={item.id}><label>Skill<input value={item.label} onChange={event => onChange(item.id, { label: event.target.value })} /></label><label className="weight-control">Weight <span className="weight-step"><button type="button" className="secondary" disabled={item.weight <= 1} onClick={() => onChange(item.id, { weight: item.weight - 1 })}>−</button><b>{item.weight}</b><button type="button" className="secondary" disabled={item.weight >= 5} onClick={() => onChange(item.id, { weight: item.weight + 1 })}>+</button></span></label><button type="button" className="link remove-button" onClick={() => onRemove(item.id)}>Remove</button></div>)}
  </section>;
}

function WeightStepper({ weight, onChange }: { weight: number; onChange: (delta: number) => void }) {
  return <span className="numeric-weight"><span>Weight</span><button type="button" className="secondary" disabled={weight <= 1} onClick={() => onChange(-1)}>−</button><b>{weight}</b><button type="button" className="secondary" disabled={weight >= 5} onClick={() => onChange(1)}>+</button></span>;
}

function ensureNumericCriteria(criteria: Criterion[], draft: Draft): Criterion[] {
  const defaults: Criterion[] = [
    { id: 'experience', kind: 'experience', label: 'Experience', weight: defaultWeights.experience, params: draft.experience },
    { id: 'notice', kind: 'notice', label: 'Notice period', weight: defaultWeights.notice, params: draft.notice },
    { id: 'ctc', kind: 'ctc', label: 'Expected CTC', weight: defaultWeights.ctc, params: draft.ctc },
    { id: 'location', kind: 'location', label: 'Location', weight: defaultWeights.location, params: {} },
  ];
  return [...criteria, ...defaults.filter(item => !criteria.some(existing => existing.kind === item.kind))];
}

function Scorecard({ req, counts }: { req: Req; counts: Counts }) {
  const nav = useNavigate(); const tab = window.location.pathname.split('/').pop() || 'scorecard';
  const [draft, setDraft] = useState<Draft>(emptyDraft); const [criteria, setCriteria] = useState<Criterion[]>([]); const [version, setVersion] = useState<number>();
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('');
  const [retryAction, setRetryAction] = useState<() => void>(() => () => {});
  const jd = req.jd_text;
  useEffect(() => {
    setLoading(true); setError('');
    void api<ScorecardData>(`/requisitions/${req.id}/scorecard`).then(value => { const nextDraft = draftFromScorecard(value, req.location); setVersion(value.version); setDraft(nextDraft); setCriteria(ensureNumericCriteria(value.criteria, nextDraft)); })
      .catch(reason => { const message = reason instanceof Error ? reason.message : 'Unable to load scorecard'; if (!message.toLowerCase().includes('not found')) setError(message); const nextDraft = normalizeDraft(undefined, req.location); setDraft(nextDraft); setCriteria(ensureNumericCriteria([], nextDraft)); })
      .finally(() => setLoading(false));
  }, [req.id]);
  const setNumeric = (path: 'experience.min_years' | 'experience.max_years' | 'notice.max_days' | 'ctc.max_lpa', raw: string) => {
    const value = raw === '' ? undefined : Number(raw);
    setDraft(current => path.startsWith('experience.') ? { ...current, experience: { ...current.experience, [path.split('.')[1]]: value } } : path.startsWith('notice.') ? { ...current, notice: { ...current.notice, max_days: value } } : { ...current, ctc: { ...current.ctc, max_lpa: value } });
  };
  function fromDraft(value: Draft): Criterion[] {
    const skill = (list: Draft['must_have_skills'], kind: 'must_skill' | 'nice_skill') => list.map((item, index) => ({ id: `${kind}-${index + 1}-${Date.now()}`, kind, label: item.name, weight: defaultWeights[kind], params: { aliases: item.aliases || [] } }));
    return [...skill(value.must_have_skills, 'must_skill'), ...skill(value.nice_to_have_skills, 'nice_skill'),
      { id: 'experience', kind: 'experience', label: 'Experience', weight: defaultWeights.experience, params: value.experience },
      { id: 'notice', kind: 'notice', label: 'Notice period', weight: defaultWeights.notice, params: value.notice },
      { id: 'ctc', kind: 'ctc', label: 'Expected CTC', weight: defaultWeights.ctc, params: value.ctc },
      { id: 'location', kind: 'location', label: 'Location', weight: defaultWeights.location, params: {} }];
  }
  async function extract() {
    setBusy(true); setError(''); setMessage('');
    try { const response = await api<{ draft: Draft; warning?: string | null }>(`/requisitions/${req.id}/scorecard/extract`, { method: 'POST' }); setDraft(response.draft); setCriteria(fromDraft(response.draft)); if (response.warning) setMessage(`Automatic extraction needs review: ${response.warning}`); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Scorecard extraction failed'); setRetryAction(() => () => { void extract(); }); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError(''); setMessage('');
    const nextCriteria = criteria.map(item => item.kind === 'experience' ? { ...item, params: draft.experience } : item.kind === 'notice' ? { ...item, params: draft.notice } : item.kind === 'ctc' ? { ...item, params: draft.ctc } : item);
    try {
      const result = await api<ScorecardData>(`/requisitions/${req.id}/scorecard`, { method: 'PUT', body: JSON.stringify({ criteria: nextCriteria, ai_draft: draft, ai_confidence: draft.field_confidence }) });
      setCriteria(result.criteria); const hadPrevious = version !== undefined; setVersion(result.version); setMessage(`Saved scorecard version ${result.version}.`);
      if (hadPrevious && window.confirm(`Scorecard changed. Rescore ${counts.candidates} candidates now?`)) {
        const scored = await api<{ reprocessed: number }>(`/requisitions/${req.id}/rescore`, { method: 'POST' });
        setMessage(`Saved version ${result.version}; rescored ${scored.reprocessed} CVs.`);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to save scorecard'); setRetryAction(() => () => { void save(); }); }
    finally { setBusy(false); }
  }
  const updateCriterion = (id: string, next: Partial<Criterion>) => setCriteria(current => current.map(item => item.id === id ? { ...item, ...next } : item));
  const updateKindWeight = (kind: Criterion['kind'], delta: number) => setCriteria(current => current.map(item => item.kind === kind ? { ...item, weight: Math.min(5, Math.max(1, item.weight + delta)) } : item));
  const addSkill = (kind: 'must_skill' | 'nice_skill') => { const label = window.prompt('Skill name'); if (!label?.trim()) return; setCriteria(current => [...current, { id: `${kind}-${Date.now()}`, kind, label: label.trim(), weight: defaultWeights[kind], params: {} }]); };
  const updateLocationCriterion = (value: string) => setCriteria(current => current.map(item => item.kind === 'location' ? { ...item, label: 'Location', params: { value } } : item));
  if (tab === 'upload') return <><HubTabs req={req} counts={counts} tab={tab} /><UploadScreen requisitionId={req.id} onBack={() => nav(`/recruiter/requisitions/${req.id}/scorecard`)} /></>;
  if (tab === 'candidates') return <><HubTabs req={req} counts={counts} tab={tab} /><CandidateList id={req.id} /></>;
  if (tab === 'pipeline') return <><HubTabs req={req} counts={counts} tab={tab} /><PipelineBoard requisitionId={req.id} /></>;
  return <><HubTabs req={req} counts={counts} tab={tab} /><main>
    {loading ? <Skeleton rows={6} /> : error ? <ErrorState message={error} retry={() => window.location.reload()} /> : <>
      <div className="card scorecard-card"><div className="scorecard-actions"><div><h2>Job description</h2><p className="muted">Confirm each field against the original JD before saving.</p></div><button type="button" disabled={busy} onClick={() => void extract()}>{busy ? 'Working…' : 'Extract with AI'}</button></div>
        <textarea className="jd" value={jd} readOnly aria-label="Job description" />
        {message && <p className="success-message">{message}</p>}{error && <ErrorState message={error} retry={retryAction} />}
        <div className="scorecard-fields">
          <label>Location<input value={draft.location} onChange={event => { setDraft({ ...draft, location: event.target.value }); updateLocationCriterion(event.target.value); }} />{fieldState('Location', confirmField('location', draft.location, jd))}<WeightStepper weight={criteria.find(item => item.kind === 'location')?.weight || 1} onChange={delta => updateKindWeight('location', delta)} /></label>
          <label>Minimum experience (years)<input type="number" min="0" max="50" step="0.5" value={draft.experience.min_years ?? ''} onChange={event => setNumeric('experience.min_years', event.target.value)} />{fieldState('Experience', confirmField('experience_min', draft.experience.min_years, jd))}<WeightStepper weight={criteria.find(item => item.kind === 'experience')?.weight || 3} onChange={delta => updateKindWeight('experience', delta)} /></label>
          <label>Maximum experience (years)<input type="number" min="0" max="50" step="0.5" value={draft.experience.max_years ?? ''} onChange={event => setNumeric('experience.max_years', event.target.value)} />{fieldState('Experience', confirmField('experience_max', draft.experience.max_years, jd))}</label>
          <label>Notice limit (days)<input type="number" min="0" max="180" value={draft.notice.max_days ?? ''} onChange={event => setNumeric('notice.max_days', event.target.value)} />{fieldState('Notice', confirmField('notice', draft.notice.max_days, jd))}<WeightStepper weight={criteria.find(item => item.kind === 'notice')?.weight || 2} onChange={delta => updateKindWeight('notice', delta)} /></label>
          <label>CTC limit (LPA)<input type="number" min="0" max="500" step="0.5" value={draft.ctc.max_lpa ?? ''} onChange={event => setNumeric('ctc.max_lpa', event.target.value)} />{fieldState('CTC', confirmField('ctc', draft.ctc.max_lpa, jd))}<WeightStepper weight={criteria.find(item => item.kind === 'ctc')?.weight || 1} onChange={delta => updateKindWeight('ctc', delta)} /></label>
        </div>
        <SkillCriterionList kind="must_skill" criteria={criteria.filter(item => item.kind === 'must_skill')} onChange={updateCriterion} onAdd={() => addSkill('must_skill')} onRemove={id => setCriteria(current => current.filter(item => item.id !== id))} />
        <SkillCriterionList kind="nice_skill" criteria={criteria.filter(item => item.kind === 'nice_skill')} onChange={updateCriterion} onAdd={() => addSkill('nice_skill')} onRemove={id => setCriteria(current => current.filter(item => item.id !== id))} />
        <div className="form-footer"><span className="muted">{version ? `Editing version ${version}; saving creates a new version.` : 'Unsaved scorecard'}</span><button type="button" disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save scorecard'}</button></div>
      </div>
    </>}
  </main></>;
}

type CandidateRow = { id: string; candidate_id: string; candidate_code: string; name: string; current_role: string; experience: number | null; skills: string[]; score: number | null; band: string | null; needs_review: boolean; review_reasons: string[]; stage: string; criteria: any[]; duplicate_of_id?: string | null };
function CandidateList({ id }: { id: string }) {
  const [items, setItems] = useState<CandidateRow[]>([]); const [q, setQ] = useState(''); const [band, setBand] = useState(''); const [needsReview, setNeedsReview] = useState(''); const [stage, setStage] = useState('');
  const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = () => {
    setLoading(true); setError('');
    const params = new URLSearchParams(); if (q.trim()) params.set('q', q.trim()); if (band) params.set('band', band); if (needsReview) params.set('needs_review', needsReview); if (stage) params.set('stage', stage);
    void api<{ items: CandidateRow[] }>(`/requisitions/${id}/applications?${params.toString()}`).then(result => setItems(result.items)).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load candidates')).finally(() => setLoading(false));
  };
  useEffect(load, [id, band, needsReview, stage]);
  const open = (applicationId: string) => window.location.assign(`/recruiter/applications/${applicationId}`);
  return <main><PageHeader title="Candidates" description="Ranks are suggestions. Nobody is rejected automatically." />
    <div className="filters"><input placeholder="Search all candidates, including low matches" value={q} onChange={event => setQ(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') load(); }} />
      <select value={band} onChange={event => setBand(event.target.value)}><option value="">All bands</option><option value="strong">Strong match</option><option value="possible">Possible match</option><option value="low">Low match</option></select>
      <select value={needsReview} onChange={event => setNeedsReview(event.target.value)}><option value="">All review states</option><option value="true">Needs review</option><option value="false">No review flag</option></select>
      <select value={stage} onChange={event => setStage(event.target.value)}><option value="">All stages</option>{['sourced','screened','submitted','shortlisted','interview','offered','joined','client_rejected','withdrawn'].map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select>
      <button type="button" className="secondary" onClick={load}>Search</button></div>
    {loading ? <Skeleton rows={6} /> : error ? <ErrorState message={error} retry={load} /> : items.length === 0 ? <EmptyState title="No candidates match these filters" /> : <div className="candidate-table" role="table" aria-label="Candidates">
      <div className="candidate-head" role="row"><span>Candidate</span><span>Role · experience</span><span>Score</span><span>Evidence fit</span><span>Stage</span><span>Action</span></div>
      {items.map(item => <div className="candidate-row" role="row" key={item.id}>
        <span><b>{item.candidate_code}</b><br />{item.name}{item.needs_review && <small className="review-tag">Needs review</small>}{item.duplicate_of_id && <small className="review-tag">Possible duplicate</small>}</span>
        <span>{item.current_role || '—'}<small>{item.experience ?? '—'} years</small></span>
        <span className="score-cell"><b>{item.score ?? '—'}</b>{item.score !== null && <div className="score-track"><div style={{ width: `${item.score}%` }} /></div>}{item.band && <StatusBadge status={item.band} />}</span>
        <span className="criteria-chips">{item.criteria?.map(c => <StatusBadge key={c.criterion_id} status={c.verdict} />)}</span>
        <span><StatusBadge status={item.stage} /></span><span><button type="button" className="secondary" onClick={() => open(item.id)}>Review</button></span>
      </div>)}
    </div>}
  </main>;
}

type PipelineCard = { id: string; candidate_id: string; candidate_code: string; name: string; current_role: string; experience: number | null; score: number | null; band: string | null; needs_review: boolean; allowed_transitions: string[]; proposed_slots: string[] };
type PipelineColumn = { stage: string; count: number; applications: PipelineCard[] };
function PipelineBoard({ requisitionId }: { requisitionId: string }) {
  const [columns, setColumns] = useState<PipelineColumn[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(''); const [errors, setErrors] = useState<Record<string, string>>({});
  const [retryMoves, setRetryMoves] = useState<Record<string, { stage: string; details: { note?: string; confirmed_slot?: string } }>>({});
  const [pending, setPending] = useState<Record<string, { stage: string; slot: string }>>({});
  const load = () => { setLoading(true); setError(''); void api<{ columns: PipelineColumn[] }>(`/requisitions/${requisitionId}/pipeline`).then(data => setColumns(data.columns)).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load pipeline')).finally(() => setLoading(false)); };
  useEffect(load, [requisitionId]);
  async function move(applicationId: string, stage: string, details: { note?: string; confirmed_slot?: string } = {}) {
    setBusyId(applicationId); setErrors(current => ({ ...current, [applicationId]: '' }));
    try { await api(`/applications/${applicationId}/stage`, { method: 'POST', body: JSON.stringify({ stage, ...details }) }); setPending(current => { const next = { ...current }; delete next[applicationId]; return next; }); setRetryMoves(current => { const next = { ...current }; delete next[applicationId]; return next; }); load(); }
    catch (reason) { setErrors(current => ({ ...current, [applicationId]: reason instanceof Error ? reason.message : 'Unable to move candidate' })); setRetryMoves(current => ({ ...current, [applicationId]: { stage, details } })); }
    finally { setBusyId(''); }
  }
  function selectStage(card: PipelineCard, stage: string) {
    if (!stage) return;
    if (stage === 'withdrawn') { const note = window.prompt('Why are you withdrawing this candidate?'); if (note?.trim()) void move(card.id, stage, { note: note.trim() }); return; }
    if (stage === 'interview') { setPending(current => ({ ...current, [card.id]: { stage, slot: card.proposed_slots[0] || '' } })); return; }
    void move(card.id, stage);
  }
  if (loading) return <main><Skeleton rows={5} /></main>;
  if (error) return <main><ErrorState message={error} retry={load} /></main>;
  return <main className="pipeline-main"><PageHeader title="Pipeline" description="Move candidates through client review and hiring stages." />
    <div className="pipeline-scroll" aria-label="Candidate pipeline">
      {columns.map(column => <section className="pipeline-column" key={column.stage}>
        <header className="pipeline-column-head"><b>{column.stage.replaceAll('_', ' ')}</b><span>{column.count}</span></header>
        {column.applications.length === 0 ? <p className="pipeline-empty">No candidates</p> : column.applications.map(card => <article className="pipeline-card" key={card.id}>
          <div className="pipeline-card-top"><b>{card.candidate_code}</b>{card.needs_review && <StatusBadge status="needs_review" />}</div>
          <strong>{card.name}</strong><span className="muted">{card.current_role || 'Candidate'} · {card.experience ?? '—'} years</span>
          <div className="pipeline-card-score">{card.score !== null ? <><b>{card.score}</b><StatusBadge status={card.band || 'low'} /></> : <span className="muted">Not scored</span>}</div>
          <button type="button" className="secondary review-card" onClick={() => window.location.assign(`/recruiter/applications/${card.id}`)}>Review candidate</button>
          {card.allowed_transitions.length > 0 && <label className="stage-menu">Move stage<select value="" disabled={busyId === card.id} onChange={event => selectStage(card, event.target.value)}><option value="">Choose stage</option>{card.allowed_transitions.map(stage => <option key={stage} value={stage}>{stage.replaceAll('_', ' ')}</option>)}</select></label>}
          {pending[card.id]?.stage === 'interview' && <div className="slot-confirm"><label>Confirm a proposed time<select value={pending[card.id].slot} onChange={event => setPending(current => ({ ...current, [card.id]: { stage: 'interview', slot: event.target.value } }))}><option value="">Choose a slot</option>{card.proposed_slots.map(slot => <option key={slot} value={slot}>{new Date(slot).toLocaleString()}</option>)}</select></label><div><button type="button" disabled={busyId === card.id || !pending[card.id].slot} onClick={() => void move(card.id, 'interview', { confirmed_slot: pending[card.id].slot })}>Confirm</button><button type="button" className="link" onClick={() => setPending(current => { const next = { ...current }; delete next[card.id]; return next; })}>Cancel</button></div></div>}
          {errors[card.id] && <ErrorState message={errors[card.id]} retry={() => { const target = retryMoves[card.id]; if (target) void move(card.id, target.stage, target.details); }} />}
        </article>)}
      </section>)}
    </div>
  </main>;
}

function CandidateReview({ id }: { id: string }) {
  const [data, setData] = useState<any>(); const [error, setError] = useState(''); const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [activeQuote, setActiveQuote] = useState(''); const [showModelInput, setShowModelInput] = useState(false); const [note, setNote] = useState(''); const [message, setMessage] = useState('');
  const [retryAction, setRetryAction] = useState<() => void>(() => () => {});
  const nav = useNavigate();
  const load = () => { setLoading(true); setError(''); void api<any>(`/applications/${id}`).then(value => { setData(value); setNote(value.recruiter_note || ''); }).catch(reason => { setError(reason instanceof Error ? reason.message : 'Unable to load candidate'); setRetryAction(() => () => load()); }).finally(() => setLoading(false)); };
  useEffect(load, [id]);
  useEffect(() => { if (activeQuote) document.querySelector('.cv-panel mark')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, [activeQuote]);
  async function action(path: string, body?: object, successMessage?: string) {
    setBusy(true); setError(''); setMessage('');
    try { await api(path, { method: 'POST', ...(body ? { body: JSON.stringify(body) } : {}) }); setMessage(successMessage || 'Saved.'); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Action failed'); setRetryAction(() => () => { void action(path, body, successMessage); }); }
    finally { setBusy(false); }
  }
  async function openCv() {
    setBusy(true); setError('');
    try { await api(`/applications/${id}/cv`); await load(); setMessage('CV opened and recorded.'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to open CV'); setRetryAction(() => () => { void openCv(); }); }
    finally { setBusy(false); }
  }
  const match = activeQuote ? (data?.raw_text || '').toLowerCase().indexOf(activeQuote.toLowerCase()) : -1;
  const cvText = data?.raw_text || '';
  const renderedCv = match >= 0 ? <>{cvText.slice(0, match)}<mark>{cvText.slice(match, match + activeQuote.length)}</mark>{cvText.slice(match + activeQuote.length)}</> : cvText;
  if (loading) return <Shell><main><Skeleton rows={6} /></main></Shell>;
  if (error && !data) return <Shell><main><ErrorState message={error} retry={retryAction} /></main></Shell>;
  if (!data) return null;
  return <Shell><main className="review-main">
    <PageHeader title={`${data.candidate_code} · ${data.name}`} description={`${data.current_role || 'Candidate'} · ${data.experience ?? '—'} years`} action={<div className="review-summary">{data.score !== null && <><b>{data.score}</b><StatusBadge status={data.band} /></>}<StatusBadge status={data.stage} /></div>} />
    {data.duplicate_of && <div className="duplicate-banner"><div><b>Possible duplicate</b><p>{data.name} may match {data.duplicate_of.candidate_code} · {data.duplicate_of.name}.</p></div><div><button type="button" className="secondary" disabled={busy} onClick={() => void action(`/candidates/${data.candidate_id}/merge`, {}, 'Candidate merged.')}>Merge</button><button type="button" className="secondary" disabled={busy} onClick={() => void action(`/candidates/${data.candidate_id}/not-duplicate`, {}, 'Marked as a different candidate.')}>Not a duplicate</button></div></div>}
    {message && <p className="success-message">{message}</p>}{error && <ErrorState message={error} retry={retryAction} />}
    <div className="review-grid"><section className="card cv-panel"><div className="panel-heading"><h2>CV</h2><button type="button" className="secondary" disabled={busy || !!data.recruiter_opened_at} onClick={() => void openCv()}>{data.recruiter_opened_at ? 'CV opened' : busy ? 'Opening…' : 'Open CV'}</button></div><p className="muted">Contact details are hidden from the scoring model.</p><pre>{renderedCv}</pre></section>
      <section className="card evidence-panel"><h2>Evidence and review</h2>{data.review_reasons?.length > 0 && <div className="review-reasons"><b>Review reasons</b>{data.review_reasons.map((reason: string) => <p key={reason}>{reason}</p>)}</div>}
        <div className="hidden-note"><b>Hidden from AI</b><span>Name, gender, age, photo, marital status, contact details, address, and profile URLs.</span><button type="button" className="link" onClick={() => setShowModelInput(value => !value)}>{showModelInput ? 'Hide what the AI saw' : 'See what the AI saw'}</button>{showModelInput && <pre className="model-input">{data.scoring_input || data.redacted_text}</pre>}</div>
        <div className="evidence-list">{data.criteria?.length ? data.criteria.map((criterion: any) => <article className="evidence-item" key={criterion.criterion_id}><div className="evidence-title"><b>{criterion.label}</b><StatusBadge status={criterion.verdict} /><span className="muted">{criterion.points ?? 0}/{criterion.max_points ?? 0} pts</span></div><p>{criterion.reason}</p>{criterion.evidence?.map((evidence: any, index: number) => <button type="button" className={`quote ${evidence.verified ? '' : 'unverified'}`} key={`${evidence.quote}-${index}`} onClick={() => setActiveQuote(evidence.quote)}>{evidence.quote || 'No evidence quote'}{evidence.verified ? '' : ' · unverified'}</button>)}</article>) : <EmptyState title="No score evidence available" />}</div>
      </section>
    </div>
    <section className="card review-actions"><label>Recruiter note<textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add context for the client" /></label><div className="action-row"><button type="button" disabled={busy || !data.recruiter_opened_at} onClick={() => void action(`/applications/${id}/submit`, { note }, 'Submitted to the client.')}>Submit to client</button><button type="button" className="secondary" disabled={busy} onClick={() => { const reason = window.prompt('Why are you withdrawing this candidate?'); if (reason?.trim()) void action(`/applications/${id}/withdraw`, { note: reason.trim() }, 'Candidate withdrawn.'); }}>Withdraw</button></div>{!data.recruiter_opened_at && <small className="muted">Open the CV before submitting.</small>}</section>
  </main></Shell>;
}

function HubRoute({ id, tab }: { id: string; tab: string }) {
  const [req, setReq] = useState<Req>(); const [counts, setCounts] = useState<Counts>({ candidates: 0, strong_matches: 0, submitted: 0, uploads: 0 }); const [error, setError] = useState(''); const [loading, setLoading] = useState(true);
  const load = () => { setLoading(true); setError(''); void Promise.all([api<Req>(`/requisitions/${id}`), api<Counts>(`/requisitions/${id}/summary`)]).then(([value, summary]) => { setReq(value); setCounts(summary); }).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load requisition')).finally(() => setLoading(false)); };
  useEffect(load, [id]);
  if (loading) return <Shell><main><Skeleton rows={5} /></main></Shell>;
  if (error) return <Shell><main><ErrorState message={error} retry={load} /></main></Shell>;
  if (!req) return null;
  return <Shell><Scorecard req={req} counts={counts} /></Shell>;
}

function App() {
  const reviewMatch = window.location.pathname.match(/^\/recruiter\/applications\/([^/]+)$/);
  if (reviewMatch) return <CandidateReview id={reviewMatch[1]} />;
  const hubMatch = window.location.pathname.match(/^\/recruiter\/requisitions\/([^/]+)\/(scorecard|upload|candidates|pipeline)$/);
  if (hubMatch) return <HubRoute id={hubMatch[1]} tab={hubMatch[2]} />;
  if (window.location.pathname === '/recruiter') return <Shell><Recruiter /></Shell>;
  return <Login />;
}

createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>);
