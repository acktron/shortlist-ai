import { useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, useLocation, useNavigate } from 'react-router-dom';
import { api, login, logout } from './api/client';
import { EmptyState, ErrorState, PageHeader, ScoreSummary, Skeleton, StatusBadge, type ScoreSummaryData } from './components/shared';
import { UploadScreen } from './components/upload';
import './styles.css';

type Req = { id: string; client_id: string; title: string; location: string; jd_text: string; status: string; client_name?: string; created_at?: string; candidates?: number; strong_matches?: number; submitted?: number };
type ClientOption = { id: string; name: string };
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
  async function attemptLogin() {
    setLoading(true); setError('');
    try { const data = await login(email, password); localStorage.setItem('token', data.access_token); localStorage.setItem('user', JSON.stringify(data.user)); nav(data.user.role === 'client' ? '/portal' : '/recruiter'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to sign in'); }
    finally { setLoading(false); }
  }
  function submit(event: FormEvent) { event.preventDefault(); void attemptLogin(); }
  return <main className="login"><section><div className="brand">Shortlist<span>AI</span></div><h1>Sign in</h1><form onSubmit={submit}>
    <label>Email<input value={email} onChange={event => setEmail(event.target.value)} type="email" required /></label>
    <label>Password<input value={password} onChange={event => setPassword(event.target.value)} type="password" required /></label>
    {error && <ErrorState message={error} retry={() => void attemptLogin()} />}
    <button type="submit" disabled={loading}>{loading ? 'Signing in…' : 'Continue'}</button>
  </form><div className="chips">{accounts.map(([label, address]) => <button type="button" className="chip" key={address} onClick={() => { setEmail(address); setPassword('Demo@1234'); }}>{label}</button>)}</div></section></main>;
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="shell"><header><div className="brand">Shortlist<span>AI</span></div><div className="header-actions"><AIStatusBadge />{roleFromStorage() === 'delivery_head' && <button type="button" className="secondary" onClick={() => window.location.assign('/insights')}>Insights</button>}<button type="button" className="link" onClick={() => { logout(); window.location.assign('/login'); }}>Sign out</button></div></header>{children}</div>;
}

type ProviderMeta = { ai_mode: string; model: string };
function AIStatusBadge() {
  const [provider, setProvider] = useState<ProviderMeta>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    void api<ProviderMeta>('/meta').then(value => { if (active) setProvider(value); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);
  const label = provider?.ai_mode === 'gemini' ? `Gemini · ${provider.model}` : provider?.ai_mode === 'ollama' ? 'Local AI' : provider?.ai_mode === 'mock' ? 'Demo AI' : failed ? 'AI status unavailable' : 'Checking AI…';
  return <span className="ai-badge" aria-live="polite">{label}</span>;
}

function roleFromStorage(): string | undefined {
  try { return JSON.parse(localStorage.getItem('user') || '{}').role as string | undefined; } catch { return undefined; }
}

function Recruiter() {
  const [rows, setRows] = useState<Req[]>([]); const [clients, setClients] = useState<ClientOption[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false); const [creating, setCreating] = useState(false); const [createError, setCreateError] = useState('');
  const [draft, setDraft] = useState({ client_id: '', title: '', location: '', openings: '1', jd_text: '' });
  const load = () => {
    setLoading(true); setError('');
    void Promise.all([api<Req[]>('/requisitions'), api<ClientOption[]>('/requisitions/clients')])
      .then(async ([requisitions, clientRows]) => {
        const enriched = await Promise.all(requisitions.map(async req => ({ ...req, ...await api<Counts>(`/requisitions/${req.id}/summary`) })));
        setRows(enriched); setClients(clientRows); setDraft(current => ({ ...current, client_id: current.client_id || clientRows[0]?.id || '' }));
      }).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load requisitions')).finally(() => setLoading(false));
  };
  useEffect(load, []);
  async function createRequisition() {
    setCreating(true); setCreateError('');
    try {
      const created = await api<Req>('/requisitions', { method: 'POST', body: JSON.stringify({ ...draft, openings: Number(draft.openings) }) });
      window.location.assign(`/recruiter/requisitions/${created.id}/scorecard`);
    } catch (reason) { setCreateError(reason instanceof Error ? reason.message : 'Unable to create requisition'); }
    finally { setCreating(false); }
  }
  const daysOpen = (createdAt?: string) => createdAt ? Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 86400000)) : '—';
  return <main><PageHeader title="Requisitions" description="Open a role to review the scorecard, applicants, and pipeline." action={<button type="button" className="req-create-button" onClick={() => { setCreateError(''); setShowCreate(true); }}>New requisition</button>} />
    {loading ? <Skeleton rows={4} /> : error ? <ErrorState message={error} retry={load} /> : rows.length === 0 ? <EmptyState title="No requisitions yet" action={<button type="button" onClick={() => setShowCreate(true)}>New requisition</button>} /> : <div className="req-grid">{rows.map(req => <button type="button" className="req-card" key={req.id} onClick={() => window.location.assign(`/recruiter/requisitions/${req.id}/scorecard`)}><span className="req-title-row"><strong>{req.title}</strong><StatusBadge status={req.status} /></span><span className="req-location">{req.client_name || 'Client'} · {req.location}</span><span className="req-metrics"><span><b>{req.candidates ?? 0}</b> candidates</span><span><b>{req.strong_matches ?? 0}</b> strong matches</span><span><b>{req.submitted ?? 0}</b> submitted</span><span><b>{daysOpen(req.created_at)}</b> days open</span></span><small>Open requisition workspace</small></button>)}</div>}
    {showCreate && <div className="modal-backdrop"><form className="modal-card" onSubmit={event => { event.preventDefault(); void createRequisition(); }}><div className="modal-heading"><h2>New requisition</h2><button type="button" className="link" onClick={() => setShowCreate(false)}>Close</button></div>
      <label>Client<select required value={draft.client_id} onChange={event => setDraft({ ...draft, client_id: event.target.value })}><option value="">Choose a client</option>{clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}</select></label>
      <label>Job title<input required minLength={2} maxLength={200} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} /></label>
      <div className="modal-fields"><label>Location<input required minLength={2} maxLength={120} value={draft.location} onChange={event => setDraft({ ...draft, location: event.target.value })} /></label><label>Openings<input required type="number" min="1" max="100" value={draft.openings} onChange={event => setDraft({ ...draft, openings: event.target.value })} /></label></div>
      <label>Job description<textarea required minLength={20} value={draft.jd_text} onChange={event => setDraft({ ...draft, jd_text: event.target.value })} /></label>
      {createError && <ErrorState message={createError} retry={() => void createRequisition()} />}
      <button type="submit" disabled={creating || !clients.length}>{creating ? 'Creating…' : 'Create requisition'}</button>
    </form></div>}
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

type CandidateRow = { id: string; candidate_id: string; candidate_code: string; name: string; current_role: string; experience: number | null; skills: string[]; score: number | null; band: string | null; score_summary: ScoreSummaryData | null; needs_review: boolean; review_reasons: string[]; stage: string; criteria: any[]; duplicate_of_id?: string | null };
function CandidateList({ id }: { id: string }) {
  const [items, setItems] = useState<CandidateRow[]>([]); const [q, setQ] = useState(''); const [band, setBand] = useState(''); const [needsReview, setNeedsReview] = useState(''); const [stage, setStage] = useState('');
  const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = () => {
    setLoading(true); setError('');
    const params = new URLSearchParams(); if (q.trim()) params.set('q', q.trim()); if (band) params.set('band', band); if (needsReview) params.set('needs_review', needsReview); if (stage) params.set('stage', stage);
    void api<{ items: CandidateRow[] }>(`/requisitions/${id}/applications?${params.toString()}`).then(result => setItems(result.items)).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load candidates')).finally(() => setLoading(false));
  };
  const clearFilters = () => {
    setQ(''); setBand(''); setNeedsReview(''); setStage(''); setLoading(true); setError('');
    void api<{ items: CandidateRow[] }>(`/requisitions/${id}/applications`).then(result => setItems(result.items)).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load candidates')).finally(() => setLoading(false));
  };
  useEffect(load, [id, band, needsReview, stage]);
  const open = (applicationId: string) => window.location.assign(`/recruiter/applications/${applicationId}`);
  return <main><PageHeader title="Candidates" description="Ranks are suggestions. Nobody is rejected automatically." />
    <div className="filters"><input placeholder="Search all candidates, including low matches" value={q} onChange={event => setQ(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') load(); }} />
      <select value={band} onChange={event => setBand(event.target.value)}><option value="">All bands</option><option value="strong">Strong match</option><option value="possible">Possible match</option><option value="low">Low match</option></select>
      <select value={needsReview} onChange={event => setNeedsReview(event.target.value)}><option value="">All review states</option><option value="true">Needs review</option><option value="false">No review flag</option></select>
      <select value={stage} onChange={event => setStage(event.target.value)}><option value="">All stages</option>{['sourced','screened','submitted','shortlisted','interview','offered','joined','client_rejected','withdrawn'].map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select>
      <button type="button" className="secondary" onClick={load}>Search</button></div>
    {loading ? <Skeleton rows={6} /> : error ? <ErrorState message={error} retry={load} /> : items.length === 0 ? <EmptyState title="No candidates match these filters" action={<button type="button" onClick={clearFilters}>Clear filters</button>} /> : <div className="candidate-table" role="table" aria-label="Candidates">
      <div className="candidate-head" role="row"><span>Candidate</span><span>Role · experience</span><span>Score</span><span>Evidence fit</span><span>Stage</span><span>Action</span></div>
      {items.map(item => <div className="candidate-row" role="row" key={item.id}>
        <span><b>{item.candidate_code}</b><br />{item.name}{item.needs_review && <small className="review-tag">Needs review</small>}{item.duplicate_of_id && <small className="review-tag">Possible duplicate</small>}</span>
        <span>{item.current_role || '—'}<small>{item.experience ?? '—'} years</small></span>
        <span className="score-cell"><ScoreSummary summary={item.score_summary} />{item.score !== null && <div className="score-track"><div style={{ width: `${item.score}%` }} /></div>}</span>
        <span className="criteria-chips">{item.criteria?.map(c => <StatusBadge key={c.criterion_id} status={c.verdict} />)}</span>
        <span><StatusBadge status={item.stage} /></span><span><button type="button" className="secondary" onClick={() => open(item.id)}>Review</button></span>
      </div>)}
    </div>}
  </main>;
}

type PipelineCard = { id: string; candidate_id: string; candidate_code: string; name: string; current_role: string; experience: number | null; score: number | null; band: string | null; score_summary: ScoreSummaryData | null; needs_review: boolean; allowed_transitions: string[]; proposed_slots: string[] };
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
          <div className="pipeline-card-score">{card.score !== null ? <ScoreSummary summary={card.score_summary} /> : <span className="muted">Not scored</span>}</div>
          <button type="button" className="secondary review-card" onClick={() => window.location.assign(`/recruiter/applications/${card.id}`)}>Review candidate</button>
          {card.allowed_transitions.length > 0 && <label className="stage-menu">Move stage<select value="" disabled={busyId === card.id} onChange={event => selectStage(card, event.target.value)}><option value="">Choose stage</option>{card.allowed_transitions.map(stage => <option key={stage} value={stage}>{stage.replaceAll('_', ' ')}</option>)}</select></label>}
          {pending[card.id]?.stage === 'interview' && <div className="slot-confirm"><label>Confirm a proposed time<select value={pending[card.id].slot} onChange={event => setPending(current => ({ ...current, [card.id]: { stage: 'interview', slot: event.target.value } }))}><option value="">Choose a slot</option>{card.proposed_slots.map(slot => <option key={slot} value={slot}>{new Date(slot).toLocaleString()}</option>)}</select></label><div><button type="button" disabled={busyId === card.id || !pending[card.id].slot} onClick={() => void move(card.id, 'interview', { confirmed_slot: pending[card.id].slot })}>Confirm</button><button type="button" className="link" onClick={() => setPending(current => { const next = { ...current }; delete next[card.id]; return next; })}>Cancel</button></div></div>}
          {errors[card.id] && <ErrorState message={errors[card.id]} retry={() => { const target = retryMoves[card.id]; if (target) void move(card.id, target.stage, target.details); }} />}
        </article>)}
      </section>)}
    </div>
  </main>;
}

type PortalRequisition = { id: string; title: string; location: string; candidate_count: number };
type PortalCandidate = { application_id: string; candidate_code: string; name: string; current_role: string; experience_years: number | null; skills: string[]; notice_days: number | null; expected_ctc_lpa: number | null; score_summary: ScoreSummaryData | null; top_evidence: { label: string; verdict: string; quote: string }[]; recruiter_note: string | null; status: string; band: string | null; redacted_cv_text?: string };

function PortalShell({ children }: { children: React.ReactNode }) {
  return <div className="portal-shell"><header><button type="button" className="portal-brand" onClick={() => window.location.assign('/portal')}>Shortlist<span>AI</span></button><div className="header-actions"><AIStatusBadge /><button type="button" className="link" onClick={() => { logout(); window.location.assign('/login'); }}>Sign out</button></div></header>{children}</div>;
}

function PortalRequisitions() {
  const [rows, setRows] = useState<PortalRequisition[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = () => { setLoading(true); setError(''); void api<PortalRequisition[]>('/portal/requisitions').then(setRows).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load requisitions')).finally(() => setLoading(false)); };
  useEffect(load, []);
  return <PortalShell><main className="portal-main"><PageHeader title="Your open roles" description="Review candidates submitted by your recruiting team." />
    {loading ? <Skeleton rows={4} /> : error ? <ErrorState message={error} retry={load} /> : rows.length === 0 ? <EmptyState title="No roles have candidates ready yet" action={<button type="button" onClick={load}>Check again</button>} /> : <div className="portal-req-list">{rows.map(req => <button type="button" className="portal-req-card" key={req.id} onClick={() => window.location.assign(`/portal/requisitions/${req.id}/candidates`)}><span className="portal-req-copy"><b>{req.title}</b><small>{req.location}</small></span><span className="portal-count">{req.candidate_count}<small>{req.candidate_count === 1 ? 'candidate' : 'candidates'}</small></span></button>)}</div>}
  </main></PortalShell>;
}

function PortalCandidates({ requisitionId }: { requisitionId: string }) {
  const [rows, setRows] = useState<PortalCandidate[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = () => { setLoading(true); setError(''); void api<PortalCandidate[]>(`/portal/requisitions/${requisitionId}/candidates`).then(setRows).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load candidates')).finally(() => setLoading(false)); };
  useEffect(load, [requisitionId]);
  return <PortalShell><main className="portal-main"><button type="button" className="link portal-back" onClick={() => window.location.assign('/portal')}>← Roles</button><PageHeader title="Candidates" description="Names and contact details are masked in this portal." />
    {loading ? <Skeleton rows={4} /> : error ? <ErrorState message={error} retry={load} /> : rows.length === 0 ? <EmptyState title="No submitted candidates yet" action={<button type="button" onClick={() => window.location.assign('/portal')}>Back to roles</button>} /> : <div className="portal-cards">{rows.map(candidate => <article className="portal-candidate-card" key={candidate.application_id}><div className="portal-candidate-heading"><div><b>{candidate.name}</b><small>{candidate.candidate_code}</small></div><StatusBadge status={candidate.status} /></div><h2>{candidate.current_role || 'Candidate'}</h2><p>{candidate.experience_years ?? '—'} years · {candidate.skills.slice(0, 5).join(' · ')}</p><div className="portal-summary"><ScoreSummary summary={candidate.score_summary} /></div>{candidate.top_evidence.slice(0, 2).map((item, index) => <div className="portal-list-evidence" key={`${item.label}-${index}`}><div className="portal-evidence-heading"><b>{item.label}</b><StatusBadge status={item.verdict} /></div><blockquote>{item.quote}</blockquote></div>)}<button type="button" className="secondary portal-review" onClick={() => window.location.assign(`/portal/applications/${candidate.application_id}`)}>Review candidate</button></article>)}</div>}
  </main></PortalShell>;
}

type PortalAction = 'shortlist' | 'reject' | 'propose_interview';
function localDateTime(value: Date) { const adjusted = new Date(value.getTime() - value.getTimezoneOffset() * 60000); return adjusted.toISOString().slice(0, 16); }
function PortalDetail({ applicationId }: { applicationId: string }) {
  const [data, setData] = useState<PortalCandidate>(); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [sheet, setSheet] = useState<PortalAction | null>(null);
  const [busy, setBusy] = useState(false); const [toast, setToast] = useState(''); const [feedbackStatus, setFeedbackStatus] = useState(''); const [reason, setReason] = useState(''); const [note, setNote] = useState('');
  const [slots, setSlots] = useState([localDateTime(new Date(Date.now() + 2 * 86400000))]); const [retryAction, setRetryAction] = useState<() => void>(() => () => {});
  const load = () => { setLoading(true); setError(''); void api<PortalCandidate>(`/portal/applications/${applicationId}`).then(setData).catch(reason => { setError(reason instanceof Error ? reason.message : 'Unable to load candidate'); setRetryAction(() => () => load()); }).finally(() => setLoading(false)); };
  useEffect(load, [applicationId]);
  async function sendFeedback(action: PortalAction) {
    setBusy(true); setError('');
    const payload: Record<string, unknown> = { action };
    if (action === 'reject') { payload.reason_code = reason; payload.note = note; }
    if (action === 'shortlist') payload.note = note;
    if (action === 'propose_interview') payload.proposed_slots = slots.filter(Boolean).map(slot => new Date(slot).toISOString());
    try {
      const response = await api<{ status: string }>(`/portal/applications/${applicationId}/feedback`, { method: 'POST', body: JSON.stringify(payload) });
      setFeedbackStatus(response.status); setToast(action === 'shortlist' ? 'Candidate added to your shortlist.' : action === 'reject' ? 'Feedback sent to the recruiting team.' : 'Interview times sent to the recruiting team.'); setSheet(null); setReason(''); setNote(''); await load();
      window.setTimeout(() => setToast(''), 4000);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to send feedback'); setRetryAction(() => () => { void sendFeedback(action); }); }
    finally { setBusy(false); }
  }
  if (loading) return <PortalShell><main className="portal-main"><Skeleton rows={5} /></main></PortalShell>;
  if (error && !data) return <PortalShell><main className="portal-main"><ErrorState message={error} retry={retryAction} /></main></PortalShell>;
  if (!data) return null;
  const canReview = data.status === 'submitted' || data.status === 'shortlisted';
  return <PortalShell><main className="portal-main portal-detail-main"><button type="button" className="link portal-back" onClick={() => window.history.back()}>← Candidates</button>
    <div className="portal-detail-heading"><div><h1>{data.name}</h1><p>{data.candidate_code} · {data.current_role || 'Candidate'}</p></div><StatusBadge status={feedbackStatus || data.status} /></div>
    {toast && <div className="portal-toast" role="status">{toast}</div>}{error && <ErrorState message={error} retry={retryAction} />}
    <section className="portal-detail-card"><h2>Summary</h2><ScoreSummary summary={data.score_summary} /><div className="portal-facts"><span><small>Experience</small><b>{data.experience_years ?? '—'} years</b></span><span><small>Notice period</small><b>{data.notice_days == null ? 'Not provided' : `${data.notice_days} days`}</b></span><span><small>Expected CTC</small><b>{data.expected_ctc_lpa == null ? 'Not provided' : `${data.expected_ctc_lpa} LPA`}</b></span></div><div className="portal-skills">{data.skills.map(skill => <span key={skill}>{skill}</span>)}</div></section>
    <section className="portal-detail-card"><h2>Top evidence</h2>{data.top_evidence.length ? data.top_evidence.map((item, index) => <div className="portal-evidence" key={`${item.label}-${index}`}><div className="portal-evidence-heading"><b>{item.label}</b><StatusBadge status={item.verdict} /></div><blockquote>{item.quote}</blockquote></div>) : <p className="muted">No verified evidence quotes are available.</p>}</section>
    <section className="portal-detail-card"><h2>Recruiter note</h2><p>{data.recruiter_note || 'No recruiter note was provided.'}</p></section>
    <details className="portal-detail-card portal-redacted-cv"><summary>View redacted CV text</summary><pre>{data.redacted_cv_text}</pre></details>
    {!canReview && <p className="portal-status-note">This candidate is now <StatusBadge status={feedbackStatus || data.status} />.</p>}
  </main>
  {canReview && <div className="portal-action-bar"><div className="portal-action-inner">{data.status === 'submitted' && <><button type="button" disabled={busy} onClick={() => { setNote(''); setSheet('shortlist'); }}>Shortlist</button><button type="button" className="secondary" disabled={busy} onClick={() => setSheet('reject')}>Reject</button></>}{data.status === 'shortlisted' && <button type="button" disabled={busy} onClick={() => setSheet('propose_interview')}>Propose interview</button>}</div></div>}
  {sheet && <div className="bottom-sheet-backdrop" onClick={() => !busy && setSheet(null)}><section className="bottom-sheet" role="dialog" aria-modal="true" aria-label={sheet === 'shortlist' ? 'Shortlist candidate' : sheet === 'reject' ? 'Reject candidate' : 'Propose interview'} onClick={event => event.stopPropagation()}><div className="sheet-handle" /><div className="sheet-heading"><h2>{sheet === 'shortlist' ? 'Shortlist candidate' : sheet === 'reject' ? 'Share a rejection reason' : 'Propose interview times'}</h2><button type="button" className="link" disabled={busy} onClick={() => setSheet(null)}>Close</button></div>
    {sheet === 'reject' && <><label>Reason<select value={reason} onChange={event => setReason(event.target.value)}><option value="">Choose a reason</option><option value="skills_gap">Skills gap</option><option value="experience">Experience</option><option value="notice_period">Notice period</option><option value="ctc">CTC</option><option value="location">Location</option><option value="culture_fit">Culture fit</option><option value="other">Other</option></select></label>{reason === 'other' && <label>Note<textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Tell the recruiting team more" /></label>}</>}
    {sheet === 'shortlist' && <label>Optional note<textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add a note for the recruiting team" /></label>}
    {sheet === 'propose_interview' && <div className="slot-list"><p className="muted">Offer one to three future times. The recruiter will confirm one.</p>{slots.map((slot, index) => <div className="slot-input" key={index}><label>Option {index + 1}<input type="datetime-local" value={slot} min={localDateTime(new Date())} onChange={event => setSlots(current => current.map((item, i) => i === index ? event.target.value : item))} /></label>{slots.length > 1 && <button type="button" className="link" onClick={() => setSlots(current => current.filter((_, i) => i !== index))}>Remove</button>}</div>)}{slots.length < 3 && <button type="button" className="secondary" onClick={() => setSlots(current => [...current, localDateTime(new Date(Date.now() + (current.length + 2) * 86400000))])}>Add another time</button>}</div>}
    {error && <ErrorState message={error} retry={retryAction} />}
    <button type="button" disabled={busy || (sheet === 'reject' && (!reason || (reason === 'other' && !note.trim()))) || (sheet === 'propose_interview' && (slots.some(slot => !slot) || slots.length < 1))} onClick={() => void sendFeedback(sheet)}>{busy ? 'Sending…' : sheet === 'shortlist' ? 'Confirm shortlist' : sheet === 'reject' ? 'Send feedback' : 'Send proposed times'}</button>
  </section></div>}
  </PortalShell>;
}

type CalibrationCandidate = { candidate_id: string; candidate_code: string; name: string; current_role: string; score: number | null; band: string | null; score_summary: ScoreSummaryData | null; stage: string; needs_review: boolean };
type CalibrationRole = { requisition_id: string; title: string; client_name: string; submitted_count: number; top_n: number; overlap_percent: number; submitted_but_ranked_low: CalibrationCandidate[]; ranked_high_not_submitted: CalibrationCandidate[]; client_acceptance_rate: number; needs_review_count: number; overrides: number };
type AccessEvent = { action: string; created_at: string; user: string; role: string | null; ip?: string | null; user_agent?: string | null };
function currentIsoWeek() {
  const today = new Date(); const date = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()));
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}
function Insights() {
  const [week, setWeek] = useState(currentIsoWeek()); const [roles, setRoles] = useState<CalibrationRole[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const [logCandidate, setLogCandidate] = useState(''); const [logEvents, setLogEvents] = useState<AccessEvent[]>([]); const [logError, setLogError] = useState(''); const [logLoading, setLogLoading] = useState(false);
  const load = () => { setLoading(true); setError(''); void api<{ week: string; requisitions: CalibrationRole[] }>(`/insights/calibration?week=${encodeURIComponent(week)}`).then(response => setRoles(response.requisitions)).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load calibration')).finally(() => setLoading(false)); };
  useEffect(load, [week]);
  async function showLog(candidateId: string) {
    setLogCandidate(candidateId); setLogLoading(true); setLogError('');
    try { const response = await api<{ events: AccessEvent[] }>(`/candidates/${candidateId}/access-log`); setLogEvents(response.events); }
    catch (reason) { setLogError(reason instanceof Error ? reason.message : 'Unable to load access history'); }
    finally { setLogLoading(false); }
  }
  const totalSubmitted = roles.reduce((sum, role) => sum + role.submitted_count, 0);
  const averageOverlap = roles.length ? Math.round(roles.reduce((sum, role) => sum + role.overlap_percent, 0) / roles.length) : 0;
  const needsReview = roles.reduce((sum, role) => sum + role.needs_review_count, 0);
  return <Shell><main className="insights-main"><PageHeader title="Delivery insights" description="Weekly comparison of submitted candidates with the AI ranked list." action={<label className="week-picker">Week<input type="week" value={week} onChange={event => setWeek(event.target.value.toUpperCase())} /></label>} />
    {loading ? <Skeleton rows={5} /> : error ? <ErrorState message={error} retry={load} /> : roles.length === 0 ? <EmptyState title={`No submissions for ${week}`} action={<button type="button" onClick={load}>Check this week again</button>} /> : <>
      <div className="insight-metrics"><div><small>Submitted</small><b>{totalSubmitted}</b></div><div><small>Average overlap</small><b>{averageOverlap}%</b></div><div><small>Needs review</small><b>{needsReview}</b></div></div>
      {roles.map(role => <section className="calibration-card" key={role.requisition_id}><header><div><h2>{role.title}</h2><p>{role.client_name} · AI top {role.top_n} of {role.submitted_count} submitted</p></div><span className="overlap-value">{role.overlap_percent}%<small>overlap</small></span></header>
        <div className="calibration-stats"><span>Client acceptance <b>{role.client_acceptance_rate}%</b></span><span>Needs review <b>{role.needs_review_count}</b></span><span>Overrides <b>{role.overrides}</b></span></div>
        <div className="calibration-lists"><CandidateCalibrationList title="Submitted but ranked low" candidates={role.submitted_but_ranked_low} onAccessLog={showLog} /><CandidateCalibrationList title="AI ranked high but not submitted" candidates={role.ranked_high_not_submitted} onAccessLog={showLog} /></div>
      </section>)}
    </>}
    {logCandidate && <><button type="button" className="drawer-backdrop" aria-label="Close access log" onClick={() => setLogCandidate('')} /><aside className="drawer access-drawer"><div className="drawer-title"><h2>Candidate access history</h2><button type="button" className="secondary" onClick={() => setLogCandidate('')}>Close</button></div>{logLoading ? <Skeleton rows={4} /> : logError ? <ErrorState message={logError} retry={() => void showLog(logCandidate)} /> : logEvents.length === 0 ? <EmptyState title="No profile or CV views logged" action={<button type="button" onClick={() => setLogCandidate('')}>Close access log</button>} /> : <div className="access-events">{logEvents.map((event, index) => <article key={`${event.created_at}-${index}`}><b>{event.action.replaceAll('_', ' ')}</b><span>{event.user} · {event.role || 'user'}</span><time>{new Date(event.created_at).toLocaleString()}</time>{event.ip && <small>IP {event.ip}</small>}</article>)}</div>}</aside></>}
  </main></Shell>;
}
function CandidateCalibrationList({ title, candidates, onAccessLog }: { title: string; candidates: CalibrationCandidate[]; onAccessLog: (id: string) => void }) {
  return <section className="calibration-list"><h3>{title}</h3>{candidates.length === 0 ? <p className="muted">None</p> : candidates.map(candidate => <article key={candidate.candidate_id}><div><b>{candidate.candidate_code} · {candidate.name}</b><small>{candidate.current_role || 'Candidate'} · {candidate.stage.replaceAll('_', ' ')}</small></div><ScoreSummary summary={candidate.score_summary} /><button type="button" className="secondary" onClick={() => onAccessLog(candidate.candidate_id)}>Access log</button></article>)}</section>;
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
    <button type="button" className="link candidate-back" onClick={() => nav(-1)}>← Back to previous screen</button>
    <PageHeader title={`${data.candidate_code} · ${data.name}`} description={`${data.current_role || 'Candidate'} · ${data.experience ?? '—'} years`} action={<div className="review-summary">{data.score !== null && <ScoreSummary summary={data.score_summary} />}<StatusBadge status={data.stage} /></div>} />
    <p className="consent-status">Consent status <StatusBadge status={data.consent_status || 'pending'} />{data.deleted && <span className="muted">Personal data deleted</span>}</p>
    {data.duplicate_of && <div className="duplicate-banner"><div><b>Possible duplicate</b><p>{data.name} may match {data.duplicate_of.candidate_code} · {data.duplicate_of.name}.</p></div><div><button type="button" className="secondary" disabled={busy} onClick={() => void action(`/candidates/${data.candidate_id}/merge`, {}, 'Candidate merged.')}>Merge</button><button type="button" className="secondary" disabled={busy} onClick={() => void action(`/candidates/${data.candidate_id}/not-duplicate`, {}, 'Marked as a different candidate.')}>Not a duplicate</button></div></div>}
    {message && <p className="success-message">{message}</p>}{error && <ErrorState message={error} retry={retryAction} />}
    <div className="review-grid"><section className="card cv-panel"><div className="panel-heading"><h2>CV</h2><button type="button" className="secondary" disabled={busy || !!data.recruiter_opened_at || data.deleted} onClick={() => void openCv()}>{data.deleted ? 'CV data deleted' : data.recruiter_opened_at ? 'CV opened' : busy ? 'Opening…' : 'Open CV'}</button></div><p className="muted">Contact details are hidden from the scoring model.</p><pre>{data.raw_text || 'CV text is unavailable.'}</pre></section>
      <section className="card evidence-panel"><h2>Evidence and review</h2>{data.review_reasons?.length > 0 && <div className="review-reasons"><b>Review reasons</b>{data.review_reasons.map((reason: string) => <p key={reason}>{reason}</p>)}</div>}
        <div className="hidden-note"><b>Hidden from AI</b><span>Name, gender, age, photo, marital status, contact details, address, and profile URLs.</span><button type="button" className="link" onClick={() => setShowModelInput(value => !value)}>{showModelInput ? 'Hide what the AI saw' : 'See what the AI saw'}</button>{showModelInput && <pre className="model-input">{data.scoring_input || data.redacted_text}</pre>}</div>
        <div className="evidence-list">{data.criteria?.length ? data.criteria.map((criterion: any) => <article className="evidence-item" key={criterion.criterion_id}><div className="evidence-title"><b>{criterion.label}</b><StatusBadge status={criterion.verdict} /><span className="muted">{criterion.points ?? 0}/{criterion.max_points ?? 0} pts</span></div><p>{criterion.reason}</p>{criterion.evidence?.map((evidence: any, index: number) => <button type="button" className={`quote ${evidence.verified ? '' : 'unverified'}`} key={`${evidence.quote}-${index}`} onClick={() => setActiveQuote(evidence.quote)}>{evidence.quote || 'No evidence quote'}{evidence.verified ? '' : ' · unverified'}</button>)}</article>) : <EmptyState title="No score evidence available" action={<button type="button" onClick={() => nav(-1)}>Back to previous screen</button>} />}</div>
      </section>
    </div>
    {roleFromStorage() === 'recruiter' && <section className="card review-actions"><label>Recruiter note<textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add context for the client" /></label><div className="action-row"><button type="button" disabled={busy || !data.recruiter_opened_at || data.deleted} onClick={() => void action(`/applications/${id}/submit`, { note }, 'Submitted to the client.')}>Submit to client</button><button type="button" className="secondary" disabled={busy || data.deleted} onClick={() => { const reason = window.prompt('Why are you withdrawing this candidate?'); if (reason?.trim()) void action(`/applications/${id}/withdraw`, { note: reason.trim() }, 'Candidate withdrawn.'); }}>Withdraw</button><button type="button" className="secondary destructive-action" disabled={busy || data.deleted} onClick={() => { if (window.confirm('Delete this candidate’s personal data and CV files? This cannot be undone.')) void action(`/candidates/${data.candidate_id}/deletion`, {}, 'Candidate personal data deleted.'); }}>{data.deleted ? 'Data deleted' : 'Delete candidate data'}</button></div>{!data.recruiter_opened_at && <small className="muted">Open the CV before submitting.</small>}</section>}
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
  const { pathname } = useLocation();
  if (pathname === '/insights') return <Insights />;
  const portalApplicationMatch = pathname.match(/^\/portal\/applications\/([^/]+)$/);
  if (portalApplicationMatch) return <PortalDetail applicationId={portalApplicationMatch[1]} />;
  const portalRequisitionMatch = pathname.match(/^\/portal\/requisitions\/([^/]+)\/candidates$/);
  if (portalRequisitionMatch) return <PortalCandidates requisitionId={portalRequisitionMatch[1]} />;
  if (pathname === '/portal') return <PortalRequisitions />;
  const reviewMatch = pathname.match(/^\/recruiter\/applications\/([^/]+)$/);
  if (reviewMatch) return <CandidateReview id={reviewMatch[1]} />;
  const hubMatch = pathname.match(/^\/recruiter\/requisitions\/([^/]+)\/(scorecard|upload|candidates|pipeline)$/);
  if (hubMatch) return <HubRoute id={hubMatch[1]} tab={hubMatch[2]} />;
  if (pathname === '/recruiter') return <Shell><Recruiter /></Shell>;
  return <Login />;
}

createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>);
