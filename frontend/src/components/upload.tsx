import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { EmptyState, ErrorState, PageHeader, Skeleton, StatusBadge } from './shared';

type Row = { id: string; filename: string; status: string; candidate_id?: string | null; error_message?: string; error_code?: string; duplicate_of?: { filename?: string; candidate_code?: string; application_id?: string } };
type Batch = { batch_id: string; status: string; total: number; processed: number; failed: number; duplicates: number; needs_review: number; parsed: number; files: Row[] };

export function UploadScreen({ requisitionId, onBack }: { requisitionId: string; onBack: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState('');
  const [redacted, setRedacted] = useState<string>();
  const [drawerError, setDrawerError] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyFile, setBusyFile] = useState('');
  const [retryAction, setRetryAction] = useState<() => void>(() => () => {});
  const [activeFileId, setActiveFileId] = useState('');

  async function loadLatest() {
    setError('');
    try { setBatch(await api<Batch | null>(`/uploads/latest?requisition_id=${requisitionId}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load the latest upload batch'); setRetryAction(() => () => { void loadLatest(); }); }
  }
  async function send(files: FileList | File[]) {
    const selected = Array.from(files);
    if (selected.length === 0) return;
    if (selected.length > 500) { setError('A batch can contain up to 500 files.'); return; }
    const invalid = selected.find(file => !/\.(pdf|docx)$/i.test(file.name) || file.size > 10 * 1024 * 1024);
    if (invalid) { setError(`${invalid.name}: choose a PDF or DOCX file no larger than 10 MB.`); return; }
    setBusy(true); setError('');
    const form = new FormData(); selected.forEach(file => form.append('files', file));
    try { setBatch(await api<Batch>(`/requisitions/${requisitionId}/uploads`, { method: 'POST', body: form, headers: {} })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Upload failed'); setRetryAction(() => () => { void send(selected); }); }
    finally { setBusy(false); if (input.current) input.current.value = ''; }
  }
  async function showRedacted(id: string) {
    setActiveFileId(id); setDrawerError(''); setRedacted(undefined);
    try { const result = await api<{ redacted_text: string }>(`/cv-files/${id}/redacted`); setRedacted(result.redacted_text); }
    catch (reason) { setDrawerError(reason instanceof Error ? reason.message : 'Unable to load redacted text'); }
  }
  async function retryFile(id: string) {
    setBusyFile(id); setError('');
    try { await api(`/cv-files/${id}/retry`, { method: 'POST' }); await loadLatest(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Retry failed'); setRetryAction(() => () => { void retryFile(id); }); }
    finally { setBusyFile(''); }
  }
  async function retryFailed() {
    if (!batch) return;
    setBusy(true); setError('');
    try { await api(`/uploads/${batch.batch_id}/retry-failed`, { method: 'POST' }); await loadLatest(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Retry failed'); setRetryAction(() => () => { void retryFailed(); }); }
    finally { setBusy(false); }
  }
  useEffect(() => { void loadLatest(); }, [requisitionId]);
  useEffect(() => {
    if (!batch || batch.status === 'done') return;
    const timer = window.setInterval(() => {
      void api<Batch>(`/uploads/${batch.batch_id}`).then(setBatch).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to refresh upload progress'));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [batch?.batch_id, batch?.status]);

  return <main className="upload-screen">
    <button type="button" className="link" onClick={onBack}>← Scorecard</button>
    <PageHeader title="Upload CVs" description="Upload up to 500 PDF or DOCX files. Each file can be up to 10 MB." />
    <div className={`dropzone ${busy ? 'disabled' : ''}`} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); void send(event.dataTransfer.files); }} onClick={() => !busy && input.current?.click()} role="button" tabIndex={0} onKeyDown={event => { if ((event.key === 'Enter' || event.key === ' ') && !busy) input.current?.click(); }}>
      <strong>{busy ? 'Uploading…' : 'Drop files here or choose files'}</strong><span>PDF and DOCX · up to 10 MB each</span>
      <input ref={input} hidden type="file" multiple accept=".pdf,.docx" onChange={event => event.target.files && void send(event.target.files)} />
    </div>
    {error && <ErrorState message={error} retry={retryAction} />}
    {batch && <>
      <div className="upload-summary"><div className="progress"><div style={{ width: `${batch.total ? (batch.processed / batch.total) * 100 : 0}%` }} /></div><p>{batch.processed} of {batch.total} processed</p><div className="summary-chips"><span>Parsed {batch.parsed}</span><span>Duplicates {batch.duplicates}</span><span>Needs review {batch.needs_review}</span><span>Failed {batch.failed}</span></div></div>
      {batch.failed > 0 && <button type="button" className="secondary retry-all" disabled={busy} onClick={() => void retryFailed()}>{busy ? 'Retrying…' : 'Retry all failed'}</button>}
      <div className="upload-table" role="table" aria-label="Uploaded CV files"><div className="upload-head" role="row"><span>File</span><span>Status</span><span>Reason</span><span>Action</span></div>
        {batch.files.map(file => <div className="upload-row" role="row" key={file.id}><span className="filename">{file.filename}</span><span><StatusBadge status={file.status} /></span><small>{file.error_message || file.error_code || (file.duplicate_of ? `Same file as ${file.duplicate_of.filename || file.duplicate_of.candidate_code || 'another CV'}` : '')}</small><span className="upload-actions">{file.status === 'failed' ? <button type="button" className="secondary" disabled={busyFile === file.id} onClick={() => void retryFile(file.id)}>{busyFile === file.id ? 'Retrying…' : 'Retry'}</button> : file.status === 'duplicate' ? file.duplicate_of?.application_id ? <button type="button" className="secondary" onClick={() => window.location.assign(`/recruiter/applications/${file.duplicate_of?.application_id}`)}>Original {file.duplicate_of?.candidate_code}</button> : <span className="muted">{file.duplicate_of?.candidate_code || 'Linked to original'}</span> : file.candidate_id != null && <button type="button" className="secondary" onClick={() => void showRedacted(file.id)}>View redacted text</button>}</span></div>)}
        {batch.files.length === 0 && <EmptyState title="No files in this batch" action={<button type="button" onClick={() => input.current?.click()}>Choose CV files</button>} />}
      </div>
    </>}
    {!batch && !error && <EmptyState title="No uploads yet" action={<button type="button" onClick={() => input.current?.click()}>Choose CV files</button>} />}
    {(redacted !== undefined || drawerError) && <><button type="button" className="drawer-backdrop" aria-label="Close redacted text" onClick={() => { setRedacted(undefined); setDrawerError(''); }} /><aside className="drawer"><div className="drawer-title"><h2>Redacted text</h2><button type="button" className="secondary" onClick={() => { setRedacted(undefined); setDrawerError(''); }}>Close</button></div>{drawerError ? <ErrorState message={drawerError} retry={() => { if (activeFileId) void showRedacted(activeFileId); }} /> : <pre>{redacted}</pre>}</aside></>}
  </main>;
}
