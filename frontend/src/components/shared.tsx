import type {ReactNode} from 'react';
export function PageHeader({title,description,action}:{title:string;description?:string;action?:ReactNode}){return <div className="page-header"><div><h1>{title}</h1>{description&&<p className="muted">{description}</p>}</div>{action}</div>}
export function EmptyState({title,action}:{title:string;action?:ReactNode}){return <div className="state"><h2>{title}</h2>{action}</div>}
export function ErrorState({message='Something went wrong',retry}:{message?:string;retry:()=>void}){return <div className="state error"><p>{message}</p><button type="button" className="secondary" onClick={retry}>Retry</button></div>}
export function Skeleton({rows=3}:{rows?:number}){return <div>{Array.from({length:rows},(_,i)=><div className="skeleton" key={i}/>)}</div>}
const labels:Record<string,string>={strong:'Strong match',possible:'Possible match',low:'Low match',met:'Met',partial:'Partial',not_met:'Not met',unknown:'Unknown',unverified:'Unverified',needs_review:'Needs review',client_rejected:'Client rejected',ocr_ai:'Scanned CV'};
export function StatusBadge({status}:{status:string}){return <span className={`badge ${status.replaceAll('_','-')}`}>{labels[status]||status.replaceAll('_',' ')}</span>}
export type ScoreSummaryData = {score:number;band:string;met:number;partial:number;not_met:number;not_stated:number};
export function ScoreSummary({summary}:{summary:ScoreSummaryData|null|undefined}){
  if(!summary)return <span className="muted">Score summary unavailable.</span>;
  const bandLabel=labels[summary.band]||summary.band.replaceAll('_',' ');
  return <span className="score-summary"><strong>{summary.score} · {bandLabel}</strong><small>{summary.met} met · {summary.partial} partial · {summary.not_met} not met · {summary.not_stated} not stated in CV</small></span>;
}
