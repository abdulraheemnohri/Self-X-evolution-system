import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Activity, Clock3, ListChecks, Plus, RefreshCw, Sparkles, Target } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { fetchJSON, getManagementProfile } from "@/lib/api";
import { GoalRegistryPanel, GoalDetailPanel, TaskJournalPanel, HealthRecoveryPanel } from "@/pages/SelfXPanels";
import type { SelfXGoal, SelfXTask, SelfXDetail, SelfXFinding, SelfXEvent } from "@/pages/SelfXPanels";

type Goal = SelfXGoal;
type Task = SelfXTask;
type Finding = SelfXFinding;
type Detail = SelfXDetail;
type Event = SelfXEvent;
type Status = { goal_count:number; goal_status_counts:Record<string,number>; task_count:number; task_status_counts:Record<string,number>; goals:Goal[]; recent_tasks:Task[]; execution_enabled:boolean };

function selfxFetchJSON<T>(url:string, init?:RequestInit):Promise<T> {
  const profile = getManagementProfile();
  const separator = url.includes("?") ? "&" : "?";
  return fetchJSON<T>(profile ? url + separator + "profile=" + encodeURIComponent(profile) : url, init);
}
async function postJSON<T>(url:string, body?:unknown):Promise<T> {
  return selfxFetchJSON<T>(url,{method:"POST",headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
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
      const next = await selfxFetchJSON<Status>("/api/selfx/status");
      setData(next);
      const chosen = preferredId || (next.goals.some(g=>g.id===selectedId)?selectedId:(next.goals[0]?.id||""));
      setSelectedId(chosen);
      setDetail(chosen ? await selfxFetchJSON<Detail>("/api/selfx/goals/"+encodeURIComponent(chosen)) : null);
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
    try { const result=await selfxFetchJSON<{events:Event[]}>("/api/selfx/tasks/"+encodeURIComponent(id)+"/history");setEvents(result.events); }
    catch(e) {setError(e instanceof Error?e.message:String(e));}
  }
  async function diagnostics() {
    setBusy(true);setError("");
    try {
      const results=await Promise.all([selfxFetchJSON<Record<string,unknown>>("/api/selfx/identity"),selfxFetchJSON<{findings:Finding[]}>("/api/selfx/diagnostics")]);
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
      <GoalRegistryPanel goals={data?.goals || []} selectedId={selectedId} onSelect={id=>{setSelectedId(id);void load(id);setEvents(null);}} />
      <GoalDetailPanel detail={detail} busy={busy} taskTitle={taskTitle} setTaskTitle={setTaskTitle} milestoneTitle={milestoneTitle} setMilestoneTitle={setMilestoneTitle} onStatus={status=>void changeStatus(status)} onAddTask={addTask} onAddMilestone={addMilestone} />
    </div>
    <div className="grid min-w-0 gap-4 xl:grid-cols-2">
      <TaskJournalPanel detail={detail} events={events} onHistory={id=>void taskHistory(id)} onClear={()=>setEvents(null)} />
      <HealthRecoveryPanel busy={busy} findings={findings} identity={identity} onDiagnostics={()=>void diagnostics()} onRecovery={apply=>void recovery(apply)} />
    </div>
    <p className="text-xs text-muted-foreground">Safety boundary: goal management, diagnostics and recovery are integrated; autonomous execution remains disabled until a dedicated adapter is connected to Hermes authorization and approvals.</p>
  </div>;
}
