import {useEffect,useRef,useState,type ReactNode} from 'react';
import {ArrowRight, CircleHelp, X} from 'lucide-react';

export function PageHeader({title,description,action,breadcrumb}:{title:string;description?:string;action?:ReactNode;breadcrumb?:ReactNode}){
  return <div className="page-heading">
    {breadcrumb && <nav className="breadcrumb" aria-label="Breadcrumb">{breadcrumb}</nav>}
    <div className="page-header"><div><h1>{title}</h1>{description&&<p className="muted">{description}</p>}</div>{action&&<div className="page-header-action">{action}</div>}</div>
  </div>;
}

export function EmptyState({title,description,action,icon}:{title:string;description?:string;action?:ReactNode;icon?:ReactNode}){
  return <div className="state empty-state"><span className="empty-icon" aria-hidden="true">{icon||<CircleHelp size={22}/>}</span><h2>{title}</h2>{description&&<p>{description}</p>}{action&&<div className="empty-action">{action}</div>}</div>;
}

export function ErrorState({message='Something went wrong',retry}:{message?:string;retry:()=>void}){
  return <div className="state error" role="alert"><p>{message}</p><button type="button" className="secondary" onClick={retry}>Retry</button></div>;
}

export function Skeleton({rows=3,variant='row'}:{rows?:number;variant?:'row'|'card'|'candidate'}){
  return <div className={`skeleton-list skeleton-${variant}`} aria-label="Loading" aria-busy="true">{Array.from({length:rows},(_,i)=><div className="skeleton" key={i}/>)}</div>;
}

export function Toast({message,onDismiss,action}:{message:string;onDismiss?:()=>void;action?:{label:string;onClick:()=>void}}){
  const [visible,setVisible]=useState(Boolean(message));
  const dismissRef=useRef(onDismiss);
  useEffect(()=>{dismissRef.current=onDismiss;},[onDismiss]);
  useEffect(()=>{
    setVisible(Boolean(message));
    if(!message)return;
    const timer=window.setTimeout(()=>{setVisible(false);dismissRef.current?.();},action?5000:3500);
    return ()=>window.clearTimeout(timer);
  },[message,action?.label]);
  if(!message||!visible)return null;
  return <div className="toast" role="status" aria-live="polite"><span>{message}</span>{action&&<button type="button" className="link toast-action" onClick={action.onClick}>{action.label}<ArrowRight size={14}/></button>}{onDismiss&&<button type="button" className="toast-dismiss" aria-label="Dismiss notification" onClick={onDismiss}><X size={16}/></button>}</div>;
}

const labels:Record<string,string>={strong:'Strong match',possible:'Possible match',low:'Low match',met:'Met',partial:'Partial',not_met:'Not met',unknown:'Not stated',unverified:'Needs review',needs_review:'Needs review',client_rejected:'Client rejected',ocr_ai:'Scanned CV',sourced:'Sourced',screened:'Screened',submitted:'Submitted',shortlisted:'Shortlisted',interview:'Interview',offered:'Offered',joined:'Joined',withdrawn:'Withdrawn',open:'Open',on_hold:'On hold',closed:'Closed',granted:'Granted',pending:'Pending',withdrawn_consent:'Withdrawn'};
export function StatusBadge({status}:{status:string}){return <span className={`badge ${status.replaceAll('_','-')}`}>{labels[status]||status.replaceAll('_',' ')}</span>}
export type ScoreSummaryData = {score:number;band:string;met:number;partial:number;not_met:number;not_stated:number};
export function ScoreSummary({summary}:{summary:ScoreSummaryData|null|undefined}){
  if(!summary)return <span className="muted">Score summary unavailable.</span>;
  const bandLabel=labels[summary.band]||summary.band.replaceAll('_',' ');
  return <span className="score-summary"><strong>{summary.score} · {bandLabel}</strong><small>{summary.met} met · {summary.partial} partial · {summary.not_met} not met · {summary.not_stated} not stated in CV</small></span>;
}
