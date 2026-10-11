import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Activity, AlertTriangle, CheckCircle2, Clock3, ListChecks, Plus, RefreshCw, RotateCcw, ShieldCheck, Sparkles, Target } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { fetchJSON } from "@/lib/api";

type Goal = { id:string; title:string; description:string; status:"active"|"paused"|"completed"|"cancelled"; success_criteria:string[]; created_at:number; updated_at:number };
type Task = { id:string; goal_id:string; title:string; status:string; attempts:number; max_attempts:number; last_error:string; updated_at:number };
type Finding = { id:string; category:string; severity:string; summary:string; evidence:string; suggested_action:string; timestamp:number };
type Status = { goal_count:number; goal_status_counts:Record<string,number>; task_count:number; task_status_counts:Record<string,number>; goals:Goal[]; recent_tasks:Task[]; execution_enabled:boolean };
type Detail = { goal:Goal; progress:{task_total:number;task_counts:Record<string,number>;task_completion_ratio:number;milestone_total:number;milestone_counts:Record<string,number>}; milestones:Array<{id:string;title:string;status:string}>; tasks:Task[] };
type Event = { id:number;event_type:string;from_status:string|null;to_status:string;detail:string;created_at:number };

async function postJSON<T>(url:string, body?:unknown):Promise<T> {
  return fetchJSON<T>(url,{method:"POST",headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
}
function dateLabel(value:number):string { return value ? new Date(value*1000).toLocaleString() : "—"; }
function statusTone(value:string):string {
  if (["active","completed","success","ok","available"].includes(value)) return "text-emerald-500";
  if (["failed","cancelled","CRITICAL","HIGH","unavailable"].includes(value)) return "text-red-400";
  if (["paused","pending","running","MEDIUM"].includes(value)) return "text-amber-400";
  return "text-muted-foreground";
}
function Metric({label,value,icon:Icon}:{label:string;value:number;icon:typeof Activity}) {
  return <Card><CardContent className="flex items-center gap-3 p-4"><div className="rounded-md border border-border p-2"><Icon className="size-4 text-muted-foreground"/></div><div><div className="text-xs text-muted-foreground">{label}</div><div className="text-2xl font-semibold tabular-nums">{value}</div></div></CardContent></Card>;
}

export default function SelfXPage() {
  const [data,setData] = useState<Status|null>(null);
  const [selectedId,setSelectedId] = useState("");
  const [detail,setDetail] = useState<Detail|null>(null);
  const [findings,setFindings] = useState<Finding[]|null>(null);
  const [identity,setIdentity] = useState<Record<string,unknown>|null>(null);
  const [events,setEvents] = useState<Event[]|null>(null);
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [notice,setNotice] = useState("");
  const [showGoalForm,setShowGoalForm] = useState(false);
  const [goalTitle,setGoalTitle] = useState("");
  const [goalDescription,setGoalDescription] = useState("");
  const [goalCriteria,setGoalCriteria] = useState("");
  const [taskTitle,setTaskTitle] = useState("");
  const [milestoneTitle,setMilestoneTitle] = useState("");

  const load = useCallback(async (preferredId?:string) => {
    setError("");
    try {
      const next = await fetchJSON<Status>("/api/selfx/status");
      setData(next);
      const chosen = preferredId || (next.goals.some(g=>g.id===selectedId)?selectedId:(next.goals[0]?.id||""));
      setSelectedId(chosen);
      setDetail(chosen ? await fetchJSON<Detail>("/api/selfx/goals/"+encodeURIComponent(chosen)) : null);
    } catch(e) { setError(e instanceof Error?e.message:String(e)); }
    finally { setLoading(false); }
  },[selectedId]);
  useEffect(()=>{ void load(); },[load]);
  const act = async (work:()=>Promise<unknown>, success:string, goalId?:string) => {
    setBusy(true);setError("");setNotice("");
    try { await work();setNotice(success);await load(goalId||selectedId); }
    catch(e) { setError(e instanceof Error?e.message:String(e)); }
    finally { setBusy(false); }
  };
  const goal = detail?.goal;

  async function createGoal(e:FormEvent) {
    e.preventDefault();
    const title=goalTitle.trim(); if(!title)return;
    setBusy(true);setError("");setNotice("");
    try {
      const created=await postJSON<Goal>("/api/selfx/goals",{title,description:goalDescription.trim(),success_criteria:goalCriteria.split("\n").map(s=>s.trim()).filter(Boolean)});
      setGoalTitle("");setGoalDescription("");setGoalCriteria("");setShowGoalForm(false);setNotice("Goal created.");
      await load(created.id);
    } catch(err) { setError(err instanceof Error?err.message:String(err)); }
    finally { setBusy(false); }
  }
  async function changeStatus(next:"active"|"paused"|"completed"|"cancelled") {
    if(!goal)return;
    await act(()=>postJSON("/api/selfx/goals/"+encodeURIComponent(goal.id)+"/status",{status:next}),"Goal marked "+next+".",goal.id);
  }
  async function addTask(e:FormEvent) {
    e.preventDefault();if(!goal||!taskTitle.trim())return;
    await act(async()=>{await postJSON("/api/selfx/goals/"+encodeURIComponent(goal.id)+"/tasks",{title:taskTitle.trim(),max_attempts:3});setTaskTitle("");},"Task recorded; it has not been executed.",goal.id);
  }
  async function addMilestone(e:FormEvent) {
    e.preventDefault();if(!goal||!milestoneTitle.trim())return;
    await act(async()=>{await postJSON("/api/selfx/goals/"+encodeURIComponent(goal.id)+"/milestones",{title:milestoneTitle.trim()});setMilestoneTitle("");},"Milestone added.",goal.id);
  }
  async function taskHistory(id:string) {
    setEvents(null);
    try { const result=await fetchJSON<{events:Event[]}>("/api/selfx/tasks/"+encodeURIComponent(id)+"/history");setEvents(result.events); }
    catch(e) {setError(e instanceof Error?e.message:String(e));}
  }
  async function diagnostics() {
    setBusy(true);setError("");
    try {
      const results=await Promise.all([fetchJSON<Record<string,unknown>>("/api/selfx/identity"),fetchJSON<{findings:Finding[]}>("/api/selfx/diagnostics")]);
      setIdentity(results[0]);setFindings(results[1].findings);setNotice("Read-only diagnostics completed.");
    } catch(e) {setError(e instanceof Error?e.message:String(e));}
    finally {setBusy(false);}
  }
  async function recovery(apply:boolean) {
    if(apply&&!window.confirm("Persist recovery transitions? This does not execute tasks."))return;
    await act(async()=>{
      const result=await postJSON<{interrupted_task_count?:number;recovered?:unknown[]}>(apply?"/api/selfx/recovery/apply":"/api/selfx/recovery/preview");
      setNotice(apply?"Recovery state updated; no tasks were executed.":"Recovery preview found "+(result.interrupted_task_count||0)+" interrupted tasks.");
    },apply?"Recovery state saved.":"Recovery preview ready.");
  }

  if(loading)return <div className="flex flex-1 items-center justify-center gap-2 p-8"><Spinner/><span className="text-sm text-muted-foreground">Loading Self-X…</span></div>;
  const activeCount=(data?.task_status_counts.pending||0)+(data?.task_status_counts.running||0);
  const completion=Math.round((detail?.progress.task_completion_ratio||0)*100);
  return <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col gap-5 overflow-y-auto p-4 sm:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div>
      <div className="mb-1 flex items-center gap-2 text-sm text-muted-foreground"><Sparkles className="size-4"/> SELF-X EVOLUTION SYSTEM</div>
      <h1 className="text-2xl font-semibold tracking-tight">Goals, health & recovery</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted-foreground">Local-first self-management. Tasks are journal entries only; execution and approval controls remain with Hermes.</p>
    </div><div className="flex flex-wrap gap-2">
      <Button variant="outline" disabled={busy} onClick={()=>void diagnostics()}><Activity className="mr-2 size-4"/>Run diagnostics</Button>
      <Button variant="outline" disabled={busy} onClick={()=>void load(selectedId)}><RefreshCw className="mr-2 size-4"/>Refresh</Button>
      <Button onClick={()=>setShowGoalForm(v=>!v)}><Plus className="mr-2 size-4"/>New goal</Button>
    </div></header>
    {error&&<div role="alert" className="rounded-md border border-red-500/40 p-3 text-sm text-red-400">{error}</div>}
    {notice&&<div role="status" className="rounded-md border border-emerald-500/30 p-3 text-sm text-emerald-500">{notice}</div>}
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <Metric label="Goals" value={data?.goal_count||0} icon={Target}/>
      <Metric label="Active goals" value={data?.goal_status_counts.active||0} icon={Activity}/>
      <Metric label="Task records" value={data?.task_count||0} icon={ListChecks}/>
      <Metric label="Pending / running" value={activeCount} icon={Clock3}/>
    </div>
    {showGoalForm&&<Card><CardContent className="p-4 sm:p-5"><form onSubmit={createGoal} className="grid gap-3">
      <h2 className="font-semibold">Create a measurable goal</h2>
      <div className="grid gap-1"><Label htmlFor="selfx-title">Title</Label><Input id="selfx-title" value={goalTitle} onChange={e=>setGoalTitle(e.target.value)} maxLength={500} required placeholder="Improve diagnostics reliability"/></div>
      <div className="grid gap-1"><Label htmlFor="selfx-description">Description</Label><textarea id="selfx-description" value={goalDescription} onChange={e=>setGoalDescription(e.target.value)} maxLength={4000} rows={2} className="rounded-md border border-border bg-background p-2 text-sm"/></div>
      <div className="grid gap-1"><Label htmlFor="selfx-criteria">Success criteria (one per line)</Label><textarea id="selfx-criteria" value={goalCriteria} onChange={e=>setGoalCriteria(e.target.value)} rows={2} className="rounded-md border border-border bg-background p-2 text-sm" placeholder={"Regression tests pass\nNo secrets exposed"}/></div>
      <div className="flex gap-2"><Button type="submit" disabled={busy||!goalTitle.trim()}>Create goal</Button><Button type="button" variant="outline" onClick={()=>setShowGoalForm(false)}>Cancel</Button></div>
    </form></CardContent></Card>}
    <div className="grid min-w-0 gap-4 xl:grid-cols-2">
      <Card><CardContent className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Goal registry</h2><span className="text-xs text-muted-foreground">{data?.goals.length||0} total</span></div>
        {data?.goals.length?<div className="space-y-2">{data.goals.map(g=><button key={g.id} onClick={()=>{setSelectedId(g.id);void load(g.id);setEvents(null);}} className={"w-full rounded-md border p-3 text-left transition-colors hover:bg-muted/40 "+(selectedId===g.id?"border-primary/60 bg-muted/30":"border-border")}>
          <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{g.title}</span><span className={"text-xs uppercase "+statusTone(g.status)}>{g.status}</span></div>
          {g.description&&<p className="mt-1 text-sm text-muted-foreground">{g.description}</p>}
          <div className="mt-2 text-xs text-muted-foreground">{g.success_criteria.length} criteria · Updated {dateLabel(g.updated_at)}</div>
        </button>)}</div>:<p className="rounded-md border border-dashed border-border p-5 text-sm text-muted-foreground">No goals yet. Create one to track measurable work.</p>}
      </CardContent></Card>
      <Card><CardContent className="p-4 sm:p-5">{goal?<><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">{goal.title}</h2><p className="mt-1 break-all text-xs text-muted-foreground">ID: {goal.id}</p></div><span className={"text-xs uppercase "+statusTone(goal.status)}>{goal.status}</span></div>
        <div className="mt-4"><div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>Task completion</span><span>{completion}%</span></div><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{width:completion+"%"}}/></div></div>
        <div className="mt-4 grid grid-cols-3 gap-2">{["pending","running","completed"].map(k=><div key={k} className="rounded-md border border-border p-2"><div className="text-xs capitalize text-muted-foreground">{k}</div><div className="text-xl font-semibold">{detail?.progress.task_counts[k]||0}</div></div>)}</div>
        <div className="mt-4 flex flex-wrap gap-2">{goal.status==="active"&&<Button size="sm" variant="outline" onClick={()=>void changeStatus("paused")} disabled={busy}>Pause</Button>}{goal.status==="paused"&&<Button size="sm" variant="outline" onClick={()=>void changeStatus("active")} disabled={busy}>Resume</Button>}{!["completed","cancelled"].includes(goal.status)&&<Button size="sm" variant="outline" onClick={()=>void changeStatus("completed")} disabled={busy}><CheckCircle2 className="mr-1 size-4"/>Complete</Button>}{!["completed","cancelled"].includes(goal.status)&&<Button size="sm" variant="outline" onClick={()=>{if(window.confirm("Cancel this goal?"))void changeStatus("cancelled");}} disabled={busy}>Cancel</Button>}</div>
        <div className="mt-5 border-t border-border pt-4"><h3 className="mb-2 text-sm font-semibold">Add task record</h3><form onSubmit={addTask} className="flex gap-2"><Input aria-label="Task title" value={taskTitle} onChange={e=>setTaskTitle(e.target.value)} maxLength={500} required placeholder="Describe a task (not executed)"/><Button type="submit" size="sm" disabled={busy||!taskTitle.trim()}><Plus className="mr-1 size-4"/>Add</Button></form></div>
        <div className="mt-4 border-t border-border pt-4"><h3 className="mb-2 text-sm font-semibold">Milestones</h3><form onSubmit={addMilestone} className="flex gap-2"><Input aria-label="Milestone title" value={milestoneTitle} onChange={e=>setMilestoneTitle(e.target.value)} maxLength={500} required placeholder="Milestone title"/><Button type="submit" size="sm" variant="outline" disabled={busy||!milestoneTitle.trim()}>Add</Button></form>{detail?.milestones.map(m=><div key={m.id} className="mt-2 flex justify-between gap-2 text-sm"><span>{m.title}</span><span className={statusTone(m.status)}>{m.status}</span></div>)}</div>
      </>:<div className="flex min-h-48 flex-col items-center justify-center text-center"><Target className="mb-2 size-8 text-muted-foreground"/><h2 className="font-semibold">Select a goal</h2><p className="mt-1 text-sm text-muted-foreground">Choose a goal or create one.</p></div>}</CardContent></Card>
    </div>
    <div className="grid min-w-0 gap-4 xl:grid-cols-2">
      <Card><CardContent className="p-4 sm:p-5"><h2 className="mb-3 font-semibold">Task journal</h2>{detail?.tasks.length?detail.tasks.map(t=><div key={t.id} className="mb-2 rounded-md border border-border p-3"><div className="flex flex-wrap justify-between gap-2"><span className="font-medium">{t.title}</span><span className={"text-xs uppercase "+statusTone(t.status)}>{t.status}</span></div><div className="mt-1 text-xs text-muted-foreground">Attempts {t.attempts}/{t.max_attempts} · Updated {dateLabel(t.updated_at)}</div>{t.last_error&&<p className="mt-1 text-xs text-red-400">{t.last_error}</p>}<Button size="sm" variant="ghost" onClick={()=>void taskHistory(t.id)}>View history</Button></div>):<p className="text-sm text-muted-foreground">No tasks recorded for this goal.</p>}
        {events&&<div className="mt-4 rounded-md border border-border p-3"><div className="mb-2 flex justify-between"><h3 className="text-sm font-semibold">Task lifecycle history</h3><Button size="sm" variant="ghost" onClick={()=>setEvents(null)}>Close</Button></div>{events.map(ev=><div key={ev.id} className="mb-2 border-l-2 border-border pl-3"><div className="flex justify-between gap-2 text-xs"><span>{ev.event_type}</span><span className="text-muted-foreground">{dateLabel(ev.created_at)}</span></div><p className="text-xs text-muted-foreground">{ev.from_status||"—"} → {ev.to_status} {ev.detail}</p></div>)}</div>}
      </CardContent></Card>
      <Card><CardContent className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Health & recovery</h2><ShieldCheck className="size-4 text-muted-foreground"/></div><p className="mb-3 text-sm text-muted-foreground">Health checks are read-only. Recovery changes journal state only; it never starts tasks.</p><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={()=>void recovery(false)}><RotateCcw className="mr-2 size-4"/>Preview recovery</Button><Button variant="outline" disabled={busy} onClick={()=>void recovery(true)}>Apply recovery state</Button></div>
        {findings!==null&&<div className="mt-4"><h3 className="mb-2 text-sm font-semibold">Diagnostic findings ({findings.length})</h3>{findings.length?findings.map(f=><div key={f.id} className="mb-2 rounded-md border border-border p-3"><div className="flex items-center gap-2"><AlertTriangle className={"size-4 "+statusTone(f.severity)}/><span className="font-medium">{f.summary}</span><span className={"ml-auto text-xs "+statusTone(f.severity)}>{f.severity}</span></div><p className="mt-1 text-xs text-muted-foreground">{f.evidence}</p><p className="mt-1 text-xs">{f.suggested_action}</p></div>):<p className="text-sm text-emerald-500">No findings reported.</p>}</div>}
        {identity&&<details className="mt-4"><summary className="cursor-pointer text-sm font-medium">Runtime identity snapshot</summary><pre className="mt-2 max-h-64 overflow-auto rounded-md bg-muted/40 p-3 text-xs">{JSON.stringify(identity,null,2)}</pre></details>}
      </CardContent></Card>
    </div>
    <p className="text-xs text-muted-foreground">Safety boundary: goal management, diagnostics and recovery are integrated; autonomous execution remains disabled until a dedicated adapter is connected to Hermes authorization and approvals.</p>
  </div>;
}
