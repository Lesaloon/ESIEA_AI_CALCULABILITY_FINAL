import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, OnDestroy, computed, inject, signal } from '@angular/core';
import { firstValueFrom, timeout } from 'rxjs';
import { GridRender } from './environment-api';

export interface Position { x: number; y: number; }
export interface KnownCell extends Position { weight: number; visited: boolean; }
export interface Scenario { start: Position | null; goal: Position | null; locked: boolean; }
export interface Observation {
  run_id: string; turn: number; position: Position; goal: Position;
  goal_distances: Record<string, number>; goal_reached: boolean;
  neighbors: { position: Position; movement_cost: number; goal_distances: Record<string, number> }[];
}
export interface Trace { expanded: Position[]; frontier: Position[]; candidate_path: Position[]; scores: Record<string, unknown>[]; }
export interface TurnEvent {
  sequence: number; turn: number; from: Position; to: Position; action: string;
  step_cost: number; cumulative_cost: number; observation: Observation;
  reason: string; explanation: string; trace: Trace; knowledge: KnownCell[];
}
export interface RunConfig { algorithm: string; heuristic: string; interval_ms: number; max_turns: number; }
export interface AgentState {
  status: string; error: string; config: RunConfig | null; knowledge: KnownCell[]; history_count: number;
  initial_observation: Observation | null; final_path: Position[];
  run: { run_id: string; status: string; observation: Observation; cumulative_cost: number; start: Position } | null;
}
export interface Algorithm { id: string; label: string; description: string; enabled: boolean; }

@Injectable({ providedIn: 'root' })
export class SimulationStore implements OnDestroy {
  private readonly http = inject(HttpClient);
  readonly scenario = signal<Scenario>({ start: null, goal: null, locked: false });
  readonly state = signal<AgentState | null>(null);
  readonly algorithms = signal<Algorithm[]>([]);
  readonly history = signal<TurnEvent[]>([]);
  readonly initialKnowledge = signal<KnownCell[]>([]);
  readonly runGrid = signal<GridRender | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly connectionError = signal('');
  readonly locked = computed(() => this.scenario().locked || ['running', 'paused'].includes(this.state()?.status ?? ''));
  private timer?: ReturnType<typeof setTimeout>;
  private destroyed = false;
  private epoch = 0;

  constructor() { void this.poll(); }

  private async get<T>(url: string): Promise<T> {
    return firstValueFrom(this.http.get<T>(url).pipe(timeout(12000)));
  }

  async refresh() {
    const epoch = this.epoch;
    // Scenario updates remain available even if the agent service is offline.
    try {
      const scenario = await this.get<Scenario>('/api/environment/scenario');
      if (epoch === this.epoch && JSON.stringify(scenario) !== JSON.stringify(this.scenario())) this.scenario.set(scenario);
    } catch { /* The environment editor reports its own connection errors. */ }
    try {
      const state = await this.get<AgentState>('/api/agent/state');
      if (epoch !== this.epoch) return;
      if (state.run?.run_id !== this.state()?.run?.run_id) {
        this.history.set([]);
        this.initialKnowledge.set([]);
        this.runGrid.set(null);
      }
      this.state.set(state);
      this.connectionError.set('');
      if (!this.algorithms().length) {
        this.algorithms.set(await this.get<Algorithm[]>('/api/agent/algorithms'));
      }
      if (state.run) {
        const runId = state.run.run_id;
        if (!this.runGrid()) {
          const grid = await this.get<GridRender>(`/api/environment/runs/${runId}/grid`);
          if (epoch === this.epoch && runId === this.state()?.run?.run_id) this.runGrid.set(grid);
        }
        const cursor = this.history().at(-1)?.sequence ?? 0;
        const history = await this.get<{ run_id: string; events: TurnEvent[]; initial_knowledge: KnownCell[] }>(
          `/api/agent/history?run_id=${runId}&after_sequence=${cursor}`);
        if (epoch === this.epoch && history.run_id === this.state()?.run?.run_id) {
          this.initialKnowledge.set(history.initial_knowledge);
          this.history.update(previous => [...previous, ...history.events.filter(e => e.sequence > (previous.at(-1)?.sequence ?? 0))]);
        }
      }
    } catch (error) {
      if (epoch === this.epoch) this.connectionError.set(this.errorMessage(error));
    }
  }

  private async poll() {
    if (!this.busy()) await this.refresh();
    if (!this.destroyed) this.timer = setTimeout(() => void this.poll(), 750);
  }

  async configure(start: Position | null, goal: Position | null) {
    await this.command(async () => {
      this.scenario.set(await firstValueFrom(this.http.post<Scenario>('/api/environment/scenario', { start, goal }).pipe(timeout(12000))));
    });
  }

  async place(kind: 'start' | 'goal', position: Position) {
    const current = this.scenario();
    await this.configure(kind === 'start' ? position : current.start, kind === 'goal' ? position : current.goal);
  }

  async control(action: 'step' | 'run' | 'pause' | 'stop') {
    await this.command(async () => {
      this.state.set(await firstValueFrom(this.http.post<AgentState>(`/api/agent/${action}`, {}).pipe(timeout(15000))));
    });
  }

  async create(config: RunConfig) {
    await this.command(async () => {
      const state = await firstValueFrom(this.http.post<AgentState>('/api/agent/runs', config).pipe(timeout(15000)));
      this.state.set(state);
      this.history.set([]);
      this.runGrid.set(null);
      this.initialKnowledge.set(state.knowledge);
    });
  }

  private async command(action: () => Promise<void>) {
    if (this.busy()) return;
    this.busy.set(true);
    this.epoch++;
    this.error.set('');
    try { await action(); }
    catch (error) { this.error.set(this.errorMessage(error)); }
    finally {
      await this.refresh();
      this.busy.set(false);
    }
  }

  private errorMessage(error: unknown) {
    const detail = error instanceof HttpErrorResponse ? error.error?.detail : null;
    return typeof detail === 'string' ? detail : 'Could not reach the service. Check the environment and agent servers.';
  }

  ngOnDestroy() {
    this.destroyed = true;
    clearTimeout(this.timer);
  }
}
