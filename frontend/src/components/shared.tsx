import {useEffect,useRef,useState,type ReactNode} from 'react';
import {ArrowRight, ChevronDown, CircleHelp, Moon, Sun, X} from 'lucide-react';
import {logout} from '../api/client';

export function PageHeader({title,description,action,breadcrumb}:{title:string;description?:string;action?:ReactNode;breadcrumb?:ReactNode}){
  return <div className="page-heading">
    {breadcrumb && <nav className="breadcrumb" aria-label="Breadcrumb">{breadcrumb}</nav>}
    <div className="page-header"><div><h1>{title}</h1>{description&&<p className="muted">{description}</p>}</div>{action&&<div className="page-header-action">{action}</div>}</div>
  </div>;
}

export function EmptyState({title,description,action,icon}:{title:string;description?:string;action?:ReactNode;icon?:ReactNode}){
  return <div className="state empty-state"><span className="empty-icon" aria-hidden="true">{icon||<CircleHelp size={22}/>}</span><p>{description||title}</p>{action&&<div className="empty-action">{action}</div>}</div>;
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
export function StatusBadge({status}:{status:string}){return <span className={`badge status-${status.replaceAll('_','-')}`}>{labels[status]||status.replaceAll('_',' ')}</span>}
export type ScoreSummaryData = {score:number;band:string;met:number;partial:number;not_met:number;not_stated:number};
export function ScoreSummary({summary}:{summary:ScoreSummaryData|null|undefined}){
  if(!summary)return <span className="muted">Score summary unavailable.</span>;
  const bandLabel=labels[summary.band]||summary.band.replaceAll('_',' ');
  return <span className="score-summary"><strong><span className="mono">{summary.score}</span><span className="band-label">{bandLabel}</span></strong><small><span className="mono">{summary.met}</span> met · <span className="mono">{summary.partial}</span> partial · <span className="mono">{summary.not_met}</span> not met · <span className="mono">{summary.not_stated}</span> not stated in CV</small></span>;
}

export function ContentsNav({sections}:{sections:{id:string;label:string}[]}){
  return <nav className="contents-nav" aria-label="Contents"><span>Contents</span>{sections.map(section=><a key={section.id} href={`#${section.id}`}>{section.label}</a>)}</nav>;
}

function ThemeToggle(){
  const [dark,setDark]=useState(()=>{try{return localStorage.getItem('shortlist-theme')==='dark'}catch{return false}});
  useEffect(()=>{document.documentElement.dataset.theme=dark?'dark':'light';try{localStorage.setItem('shortlist-theme',dark?'dark':'light')}catch{}},[dark]);
  return <button type="button" className="icon-button theme-toggle" aria-label={`Switch to ${dark?'light':'dark'} theme`} title={`Switch to ${dark?'light':'dark'} theme`} onClick={()=>setDark(value=>!value)}>{dark?<Sun size={17}/>:<Moon size={17}/>}</button>;
}

function UserMenu({roleLabel,onSignOut}:{roleLabel:string;onSignOut:()=>void}){
  let user:{full_name?:string;email?:string}={};try{user=JSON.parse(localStorage.getItem('user')||'{}')}catch{}
  const name=user.full_name||user.email||'Account';
  const initials=name.split(/\s+/).slice(0,2).map(part=>part[0]?.toUpperCase()||'').join('');
  return <details className="user-menu"><summary aria-label="Open user menu"><span className="user-avatar">{initials}</span><span className="user-menu-copy"><b>{name}</b><small>{roleLabel}</small></span><ChevronDown size={14}/></summary><div className="user-menu-popover"><span>{user.email||name}</span><button type="button" className="link" onClick={onSignOut}>Sign out <ArrowRight size={14}/></button></div></details>;
}

export function AppTopBar({home,roleLabel,identity,showInsights,provider}:{home:string;roleLabel:string;identity?:string;showInsights?:boolean;provider?:ReactNode}){
  return <header className="app-topbar"><button type="button" className="brand-lockup" aria-label="ShortlistAI home" onClick={()=>window.location.assign(home)}><span className="brand-mark" aria-hidden="true"/><span>ShortlistAI</span></button>{identity&&<div className="topbar-identity"><b>{identity}</b><small>{roleLabel}</small></div>}<nav className="topbar-nav" aria-label="Primary navigation"><button type="button" className="link" onClick={()=>window.location.assign(home)}>Requisitions</button>{showInsights&&<button type="button" className="link" onClick={()=>window.location.assign('/insights')}>Insights</button>}</nav><div className="topbar-tools">{provider}{<ThemeToggle/>}<UserMenu roleLabel={roleLabel} onSignOut={()=>{logout();window.location.assign('/login')}}/></div></header>;
}
