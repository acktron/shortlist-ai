export type Role = 'recruiter' | 'delivery_head' | 'client';
export type User = { id:string; email:string; full_name:string; role:Role; client_id:string|null };
const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
export function logout(){ localStorage.removeItem('token'); window.location.assign('/'); }
export async function api<T>(path:string, init:RequestInit = {}):Promise<T>{const headers=new Headers(init.headers);headers.set('Content-Type','application/json');const token=localStorage.getItem('token');if(token)headers.set('Authorization',`Bearer ${token}`);const response=await fetch(`${base}${path}`,{...init,headers});if(response.status===401){logout();throw new Error('Session expired');}if(!response.ok)throw new Error((await response.json().catch(()=>null))?.error?.message||'Request failed');return response.json() as Promise<T>}
export function login(email:string,password:string){return api<{access_token:string;user:User}>('/auth/login',{method:'POST',body:JSON.stringify({email,password})});}
