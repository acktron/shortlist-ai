import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, useNavigate } from 'react-router-dom';
import { api, login, logout } from './api/client';
import { EmptyState, ErrorState, PageHeader, StatusBadge } from './components/shared';
import { UploadScreen } from './components/upload';
import './styles.css';

type Req = { id: string; title: string; location: string; jd_text: string; status: string; client_name?: string };
type Draft = {
  title: string; location: string;
  experience: { min_years?: number; max_years?: number };
  must_have_skills: { name: string; aliases: string[] }[];
  nice_to_have_skills: { name: string; aliases: string[] }[];
  notice: { max_days?: number }; ctc: { max_lpa?: number };
  field_confidence: Record<string, string>; missing_fields: string[];
};
type Criterion = { id: string; kind: string; label: string; weight: number; params: Record<string, unknown> };
const accounts = [['Recruiter', 'recruiter@companya.demo'], ['Delivery head', 'head@companya.demo'], ['Meridian client', 'priya@meridianbank.demo'], ['Kestrel client', 'rahul@kestrelit.demo']];
const defaults: Record<string, number> = { must_skill: 3, nice_skill: 1, experience: 3, notice: 2, ctc: 1, location: 1 };

function Login() {
  const nav = useNavigate(); const [email, setEmail] = useState(''); const [password, setPassword] = useState('Demo@1234'); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  async function submit(e: React.FormEvent) { e.preventDefault(); setLoading(true); setError(''); try { const d = await login(email, password); localStorage.setItem('token', d.access_token); localStorage.setItem('user', JSON.stringify(d.user)); nav(d.user.role === 'client' ? '/portal' : '/recruiter'); } catch (e) { setError(e instanceof Error ? e.message : 'Unable to sign in'); } finally { setLoading(false); } }
  return <main className="login"><section><div className="brand">Shortlist<span>AI</span></div><h1>Sign in</h1><form onSubmit={submit}><label>Email<input value={email} onChange={e => setEmail(e.target.value)} type="email" required /></label><label>Password<input value={password} onChange={e => setPassword(e.target.value)} type="password" required /></label>{error && <ErrorState message={error} retry={() => setError('')} />}<button type="submit" disabled={loading}>{loading ? 'Signing in…' : 'Continue'}</button></form><div className="chips">{accounts.map(([label, address]) => <button type="button" className="chip" key={address} onClick={() => { setEmail(address); setPassword('Demo@1234'); }}>{label}</button>)}</div></section></main>;
}

function Scorecard({ req }: { req: Req }) {
  const nav = useNavigate(); const [draft, setDraft] = useState<Draft>(); const [criteria, setCriteria] = useState<Criterion[]>([]); const [error, setError] = useState(''); const [version, setVersion] = useState<number>(); const [busy, setBusy] = useState(false);
  const tab = window.location.pathname.split('/').pop(); const jd = req.jd_text.toLowerCase();
  const confirm = (field: string, value: unknown) => { const v = String(value || '').toLowerCase(); if (!v) return 'empty'; if (field === 'location') return jd.includes(v) ? 'ok' : 'low'; if (field === 'experience') return /\d+\s*[-–]\s*\d+\s*(?:yr|year|yrs)/.test(jd) ? 'ok' : 'low'; if (field === 'notice') return new RegExp(`notice[^\\d]{0,30}${value}`, 'i').test(req.jd_text) ? 'ok' : 'low'; if (field === 'ctc') return new RegExp(`(?:budget|up to)[^\\d]{0,30}${value}\\s*lpa`, 'i').test(req.jd_text) ? 'ok' : 'low'; return jd.includes(v) ? 'ok' : 'low'; };
  async function extract() { setBusy(true); setError(''); try { const x = await api<{ draft: Draft }>(`/requisitions/${req.id}/scorecard/extract`, { method: 'POST' }); setDraft(x.draft); setCriteria([...x.draft.must_have_skills.map((s, i) => ({ id: `m${i}`, kind: 'must_skill', label: s.name, weight: defaults.must_skill, params: {} })), ...x.draft.nice_to_have_skills.map((s, i) => ({ id: `n${i}`, kind: 'nice_skill', label: s.name, weight: defaults.nice_skill, params: {} })), { id: 'experience', kind: 'experience', label: 'Experience', weight: defaults.experience, params: x.draft.experience }, { id: 'notice', kind: 'notice', label: 'Notice', weight: defaults.notice, params: x.draft.notice }, { id: 'ctc', kind: 'ctc', label: 'CTC', weight: defaults.ctc, params: x.draft.ctc }, { id: 'location', kind: 'location', label: 'Location', weight: defaults.location, params: {} }]); } catch (e) { setError(e instanceof Error ? e.message : 'Extract failed'); } finally { setBusy(false); } }
  async function save() { if (!draft) return; setBusy(true); setError(''); try { const x = await api<{ version: number }>(`/requisitions/${req.id}/scorecard`, { method: 'PUT', body: JSON.stringify({ criteria, ai_draft: draft, ai_confidence: draft.field_confidence }) }); setVersion(x.version); } catch (e) { setError(e instanceof Error ? e.message : 'Save failed'); } finally { setBusy(false); } }
  if (tab === 'upload') return <><HubTabs req={req} /><UploadScreen requisitionId={req.id} onBack={() => nav(`/recruiter/requisitions/${req.id}/scorecard`)} /></>;
  if (tab === 'candidates' || tab === 'pipeline') return <><HubTabs req={req} /><main><EmptyState title="Coming next" /></main></>;
  return <><HubTabs req={req} /><main><div className="card"><textarea className="jd" value={req.jd_text} readOnly /><button type="button" onClick={() => void extract()}>Extract with AI</button>{error && <ErrorState message={error} retry={() => void extract()} />}{draft && <div className="scorecard"><Field label="Location" value={draft.location} state={confirm('location', draft.location)} /><Field label="Experience min" value={draft.experience.min_years || ''} state={confirm('experience', draft.experience.min_years)} /><Field label="Experience max" value={draft.experience.max_years || ''} state={confirm('experience', draft.experience.max_years)} /><Field label="Notice max days" value={draft.notice.max_days || ''} state={confirm('notice', draft.notice.max_days)} /><Field label="CTC max LPA" value={draft.ctc.max_lpa || ''} state={confirm('ctc', draft.ctc.max_lpa)} /><h3>Must-have skills <button type="button" onClick={() => setCriteria(c => [...c, { id: `m${Date.now()}`, kind: 'must_skill', label: window.prompt('Skill') || 'New skill', weight: defaults.must_skill, params: {} }])}>Add</button></h3><h3>Nice-to-have skills <button type="button" onClick={() => setCriteria(c => [...c, { id: `n${Date.now()}`, kind: 'nice_skill', label: window.prompt('Skill') || 'New skill', weight: defaults.nice_skill, params: {} }])}>Add</button></h3><div className="criteria">{criteria.map(c => <div className="criterion" key={c.id}><span>{c.label}</span><button type="button" onClick={() => setCriteria(x => x.map(y => y.id === c.id ? { ...y, weight: Math.max(1, y.weight - 1) } : y))}>−</button><b>{c.weight}</b><button type="button" onClick={() => setCriteria(x => x.map(y => y.id === c.id ? { ...y, weight: Math.min(5, y.weight + 1) } : y))}>+</button></div>)}</div><button type="button" onClick={() => void save()}>Save scorecard</button>{version !== undefined && <p className="muted">Saved version {version}</p>}</div>}</div></main></>;
}

function Field({ label, value, state }: { label: string; value: string | number; state: string }) { return <label className={state !== 'ok' ? 'amber-field' : ''}>{label}<input value={String(value)} readOnly />{state === 'empty' ? <small>Not in JD — please fill.</small> : state === 'low' && <small>Check this — couldn't confirm it in the JD.</small>}</label>; }

function HubTabs({ req }: { req: Req }) {
  const nav = useNavigate(); const key = window.location.pathname.split('/').pop(); const client = req.client_name || 'Client';
  return <><PageHeader title={req.title} description={`${client} · ${req.location}`} /><nav className="tabs">{[['scorecard', 'Scorecard'], ['upload', 'Upload CVs · 12'], ['candidates', 'Candidates'], ['pipeline', 'Pipeline']].map(([k, label]) => <button type="button" className={key === k ? 'active' : ''} onClick={() => nav(`/recruiter/requisitions/${req.id}/${k}`)} key={k}>{label}</button>)}</nav></>;
}

function Recruiter() {
  const [rows, setRows] = useState<Req[]>([]); const [error, setError] = useState('');
  const load = () => { setError(''); void api<Req[]>('/requisitions').then(setRows).catch(e => setError(e instanceof Error ? e.message : 'Unable to load requisitions')); }; useEffect(load, []);
  return <main><PageHeader title="Requisitions" />{error ? <ErrorState message={error} retry={load} /> : <div className="req-grid">{rows.map(r => <button type="button" className="req-card" key={r.id} onClick={() => window.location.assign(`/recruiter/requisitions/${r.id}/scorecard`)}><strong>{r.title}</strong><span>{r.client_name || 'Client'} · {r.location}</span><small>0 candidates · 0 submitted</small><StatusBadge status={r.status} /></button>)}</div>}</main>;
}

function Shell({ children }: { children: React.ReactNode }) { return <div className="shell"><header><div className="brand">Shortlist<span>AI</span></div><button type="button" className="link" onClick={() => { logout(); window.location.assign('/login'); }}>Sign out</button></header>{children}</div>; }
function HubRoute({ id }: { id: string }) { const [req, setReq] = useState<Req>(); const [error, setError] = useState(''); const load = () => { setError(''); void api<Req>(`/requisitions/${id}`).then(setReq).catch(e => setError(e instanceof Error ? e.message : 'Unable to load requisition')); }; useEffect(load, [id]); if (error) return <Shell><ErrorState message={error} retry={load} /></Shell>; return req ? <Shell><Scorecard req={req} /></Shell> : <p>Loading…</p>; }
function App() { const match = window.location.pathname.match(/^\/recruiter\/requisitions\/([^/]+)\/(scorecard|upload|candidates|pipeline)$/); if (match) return <HubRoute id={match[1]} />; if (window.location.pathname === '/recruiter') return <Shell><Recruiter /></Shell>; return <Login />; }
createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>);
