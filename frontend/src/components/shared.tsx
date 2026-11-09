import type {ReactNode} from 'react';
export function PageHeader({title,description,action}:{title:string;description?:string;action?:ReactNode}){return <div className="page-header"><div><h1>{title}</h1>{description&&<p className="muted">{description}</p>}</div>{action}</div>}
export function EmptyState({title,action}:{title:string;action?:ReactNode}){return <div className="state"><h2>{title}</h2>{action}</div>}
export function ErrorState({message='Something went wrong',retry}:{message?:string;retry:()=>void}){return <div className="state error"><p>{message}</p><button onClick={retry}>Retry</button></div>}
export function Skeleton({rows=3}:{rows?:number}){return <div>{Array.from({length:rows},(_,i)=><div className="skeleton" key={i}/>)}</div>}
export function StatusBadge({status}:{status:string}){return <span className={`badge ${status.replaceAll('_','-')}`}>{status.replaceAll('_',' ')}</span>}
