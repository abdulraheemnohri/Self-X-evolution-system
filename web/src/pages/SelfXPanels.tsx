import type { FormEvent } from "react";
import { Activity, AlertTriangle, CheckCircle2, Clock3, ListChecks, RotateCcw, ShieldCheck, Target } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";

export type SelfXGoal = { id:string; title:string; description:string; status:"active"|"paused"|"completed"|"cancelled"; success_criteria:string[]; created_at:number; updated_at:number };
export type SelfXTask = { id:string; goal_id:string; title:string; status:string; attempts:number; max_attempts:number; last_error:string; updated_at:number };
export type SelfXFinding = { id:string; category:string; severity:string; summary:string; evidence:string; suggested_action:string; timestamp:number };
export type SelfXDetail = { goal:SelfXGoal; progress:{task_total:number;task_counts:Record<string,number>;task_completion_ratio:number;milestone_total:number;milestone_counts:Record<string,number>}; milestones:Array<{id:string;title:string;status:string}>; tasks:SelfXTask[] };
export type SelfXEvent = { id:number;event_type:string;from_status:string|null;to_status:string;detail:string;created_at:number };

function dateLabel(value:number):string { return value ? new Date(value*1000).toLocaleString() : "—"; }
function tone(value:string):string {
  if (["active","completed","success","ok","available"].includes(value)) return "text-emerald-500";
  if (["failed","cancelled","CRITICAL","HIGH","unavailable"].includes(value)) return "text-red-400";
  if (["paused","pending","running","MEDIUM"].includes(value)) return "text-amber-400";
  return "text-muted-foreground";
}

export function GoalRegistryPanel({goals,selectedId,onSelect}:{goals:SelfXGoal[];selectedId:string;onSelect:(id:string)=>void}) {
  return <Card><CardContent className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Goal registry</h2><span className="text-xs text-muted-foreground">{goals.length} total</span></div>
    {goals.length ? <div className="space-y-2">{goals.map(g=><button key={g.id} onClick={()=>onSelect(g.id)} className={"w-full rounded-md border p-3 text-left transition-colors hover:bg-muted/40 "+(selectedId===g.id?"border-primary/60 bg-muted/30":"border-border")}>
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{g.title}</span><span className={"text-xs uppercase "+tone(g.status)}>{g.status}</span></div>
      {g.description&&<p className="mt-1 text-sm text-muted-foreground">{g.description}</p>}
      <div className="mt-2 text-xs text-muted-foreground">{g.success_criteria.length} criteria · Updated {dateLabel(g.updated_at)}</div>
    </button>)}</div> : <p className="rounded-md border border-dashed border-border p-5 text-sm text-muted-foreground">No goals yet. Create one to track measurable work.</p>}
  </CardContent></Card>;
}

export function GoalDetailPanel({detail,busy,taskTitle,setTaskTitle,milestoneTitle,setMilestoneTitle,onStatus,onAddTask,onAddMilestone}:{
  detail:SelfXDetail|null;busy:boolean;taskTitle:string;setTaskTitle:(v:string)=>void;milestoneTitle:string;setMilestoneTitle:(v:string)=>void;
  onStatus:(status:SelfXGoal["status"])=>void;onAddTask:(e:FormEvent)=>void;onAddMilestone:(e:FormEvent)=>void;
}) {
  const goal=detail?.goal;
  const completion=Math.round((detail?.progress.task_completion_ratio||0)*100);
  return <Card><CardContent className="p-4 sm:p-5">{goal?<><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">{goal.title}</h2><p className="mt-1 break-all text-xs text-muted-foreground">ID: {goal.id}</p></div><span className={"text-xs uppercase "+tone(goal.status)}>{goal.status}</span></div>
    <div className="mt-4"><div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>Task completion</span><span>{completion}%</span></div><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{width:completion+"%"}}/></div></div>
    <div className="mt-4 grid grid-cols-3 gap-2">{["pending","running","completed"].map(k=><div key={k} className="rounded-md border border-border p-2"><div className="text-xs capitalize text-muted-foreground">{k}</div><div className="text-xl font-semibold">{detail.progress.task_counts[k]||0}</div></div>)}</div>
    <div className="mt-4 flex flex-wrap gap-2">{goal.status==="active"&&<Button size="sm" variant="outline" onClick={()=>onStatus("paused")} disabled={busy}>Pause</Button>}{goal.status==="paused"&&<Button size="sm" variant="outline" onClick={()=>onStatus("active")} disabled={busy}>Resume</Button>}{!["completed","cancelled"].includes(goal.status)&&<Button size="sm" variant="outline" onClick={()=>onStatus("completed")} disabled={busy}><CheckCircle2 className="mr-1 size-4"/>Complete</Button>}{!["completed","cancelled"].includes(goal.status)&&<Button size="sm" variant="outline" onClick={()=>{if(window.confirm("Cancel this goal?"))onStatus("cancelled");}} disabled={busy}>Cancel</Button>}</div>
    <div className="mt-5 border-t border-border pt-4"><h3 className="mb-2 text-sm font-semibold">Add task record</h3><form onSubmit={onAddTask} className="flex gap-2"><Input aria-label="Task title" value={taskTitle} onChange={e=>setTaskTitle(e.target.value)} maxLength={500} required placeholder="Describe a task (not executed)"/><Button type="submit" size="sm" disabled={busy||!taskTitle.trim()}><ListChecks className="mr-1 size-4"/>Add</Button></form></div>
    <div className="mt-4 border-t border-border pt-4"><h3 className="mb-2 text-sm font-semibold">Milestones</h3><form onSubmit={onAddMilestone} className="flex gap-2"><Input aria-label="Milestone title" value={milestoneTitle} onChange={e=>setMilestoneTitle(e.target.value)} maxLength={500} required placeholder="Milestone title"/><Button type="submit" size="sm" variant="outline" disabled={busy||!milestoneTitle.trim()}>Add</Button></form>{detail.milestones.map(m=><div key={m.id} className="mt-2 flex justify-between gap-2 text-sm"><span>{m.title}</span><span className={tone(m.status)}>{m.status}</span></div>)}</div>
  </>:<div className="flex min-h-48 flex-col items-center justify-center text-center"><Target className="mb-2 size-8 text-muted-foreground"/><h2 className="font-semibold">Select a goal</h2><p className="mt-1 text-sm text-muted-foreground">Choose a goal or create one.</p></div>}</CardContent></Card>;
}

export function TaskJournalPanel({detail,events,onHistory,onClear}:{detail:SelfXDetail|null;events:SelfXEvent[]|null;onHistory:(id:string)=>void;onClear:()=>void}) {
  return <Card><CardContent className="p-4 sm:p-5"><h2 className="mb-3 font-semibold">Task journal</h2>{detail?.tasks.length?detail.tasks.map(t=><div key={t.id} className="mb-2 rounded-md border border-border p-3"><div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{t.title}</span><span className={"text-xs uppercase "+tone(t.status)}>{t.status}</span></div><div className="mt-1 text-xs text-muted-foreground">Attempts {t.attempts}/{t.max_attempts} · Updated {dateLabel(t.updated_at)}</div>{t.last_error&&<p className="mt-1 text-xs text-red-400">{t.last_error}</p>}<Button size="sm" variant="ghost" onClick={()=>onHistory(t.id)}>View history</Button></div>):<p className="text-sm text-muted-foreground">No tasks recorded for this goal.</p>}
    {events&&<div className="mt-4 rounded-md border border-border p-3"><div className="mb-2 flex justify-between"><h3 className="text-sm font-semibold">Task lifecycle history</h3><Button size="sm" variant="ghost" onClick={onClear}>Close</Button></div>{events.map(ev=><div key={ev.id} className="mb-2 border-l-2 border-border pl-3"><div className="flex justify-between gap-2 text-xs"><span>{ev.event_type}</span><span className="text-muted-foreground">{dateLabel(ev.created_at)}</span></div><p className="text-xs text-muted-foreground">{ev.from_status||"—"} → {ev.to_status} {ev.detail}</p></div>)}</div>}
  </CardContent></Card>;
}

export function HealthRecoveryPanel({busy,findings,identity,onDiagnostics,onRecovery}:{busy:boolean;findings:SelfXFinding[]|null;identity:Record<string,unknown>|null;onDiagnostics:()=>void;onRecovery:(apply:boolean)=>void}) {
  return <Card><CardContent className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Health & recovery</h2><ShieldCheck className="size-4 text-muted-foreground"/></div><p className="mb-3 text-sm text-muted-foreground">Health checks are read-only. Recovery changes journal state only; it never starts tasks.</p>
    <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={onDiagnostics}><Activity className="mr-2 size-4"/>Run diagnostics</Button><Button variant="outline" disabled={busy} onClick={()=>onRecovery(false)}><RotateCcw className="mr-2 size-4"/>Preview recovery</Button><Button variant="outline" disabled={busy} onClick={()=>onRecovery(true)}>Apply recovery state</Button></div>
    {findings!==null&&<div className="mt-4"><h3 className="mb-2 text-sm font-semibold">Diagnostic findings ({findings.length})</h3>{findings.length?findings.map(f=><div key={f.id} className="mb-2 rounded-md border border-border p-3"><div className="flex items-center gap-2"><AlertTriangle className={"size-4 "+tone(f.severity)}/><span className="font-medium">{f.summary}</span><span className={"ml-auto text-xs "+tone(f.severity)}>{f.severity}</span></div><p className="mt-1 text-xs text-muted-foreground">{f.evidence}</p><p className="mt-1 text-xs">{f.suggested_action}</p></div>):<p className="text-sm text-emerald-500">No findings reported.</p>}</div>}
    {identity&&<details className="mt-4"><summary className="cursor-pointer text-sm font-medium">Runtime identity snapshot</summary><pre className="mt-2 max-h-64 overflow-auto rounded-md bg-muted/40 p-3 text-xs">{JSON.stringify(identity,null,2)}</pre></details>}
  </CardContent></Card>;
}
