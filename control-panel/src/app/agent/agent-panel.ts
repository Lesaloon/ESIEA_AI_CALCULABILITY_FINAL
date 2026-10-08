import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { DecimalPipe, JsonPipe } from '@angular/common';
import { HlmButton } from '@spartan-ng/helm/button';
import { EnvironmentStore } from '../environment/environment-store';
import { SimulationStore } from '../simulation-store';
import { SimulationGrid } from '../simulation-grid';

@Component({
  selector: 'app-agent-panel',
  imports: [HlmButton, SimulationGrid, DecimalPipe, JsonPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-panel.html',
  styleUrl: './agent-panel.css',
})
export class AgentPanel {
  readonly sim = inject(SimulationStore);
  readonly env = inject(EnvironmentStore);
  readonly algorithm = signal('example');
  readonly heuristic = signal('l1');
  readonly interval = signal(300);
  readonly maxTurns = signal(1000);
  readonly replay = signal<number | null>(null);
  readonly knowledgeOnly = signal(false);
  readonly showTrace = signal(true);
  readonly metrics = ['l1', 'l2', 'squared_l2', 'mse', 'linf'];
  readonly running = computed(() => this.sim.state()?.status === 'running');
  readonly paused = computed(() => this.sim.state()?.status === 'paused');
  readonly displayedEvent = computed(() => this.sim.history().find(e => e.turn === this.replay()) ?? null);
  readonly observation = computed(() => this.replay() === null ? this.sim.state()?.run?.observation ?? null
    : this.replay() === 0 ? this.sim.state()?.initial_observation ?? null : this.displayedEvent()?.observation ?? null);
  readonly knowledge = computed(() => this.replay() === null ? this.sim.state()?.knowledge ?? []
    : this.replay() === 0 ? this.sim.initialKnowledge() : this.displayedEvent()?.knowledge ?? []);
  readonly chosenPath = computed(() => {
    const state = this.sim.state();
    if (!state?.run || !['succeeded', 'stopped', 'limit_reached'].includes(state.status)) return [];
    return state.final_path;
  });
  readonly trace = computed(() => {
    if (!this.showTrace()) return null;
    if (this.replay() !== null) return this.displayedEvent()?.trace ?? null;
    const event = this.sim.history().at(-1);
    if (!event || event.turn !== this.observation()?.turn) return null;
    return this.chosenPath().length ? { ...event.trace, candidate_path: this.chosenPath() } : event.trace;
  });
  readonly trail = computed(() => {
    const start = this.sim.state()?.run?.start;
    const turn = this.observation()?.turn ?? 0;
    return start ? [start, ...this.sim.history().filter(e => e.turn <= turn && e.action === 'move').map(e => e.to)] : [];
  });
  readonly cost = computed(() => this.replay() === null ? this.sim.state()?.run?.cumulative_cost ?? 0
    : this.displayedEvent()?.cumulative_cost ?? 0);
  readonly configValid = computed(() => Number.isInteger(this.interval()) && this.interval() >= 50 && this.interval() <= 5000
    && Number.isInteger(this.maxTurns()) && this.maxTurns() >= 1 && this.maxTurns() <= 10000);
  readonly selectedAlgorithm = computed(() => this.sim.algorithms().find(a => a.id === this.algorithm()));

  constructor() {
    let runId: string | undefined;
    effect(() => {
      const state = this.sim.state();
      if (state?.run?.run_id !== runId) {
        runId = state?.run?.run_id;
        this.replay.set(null);
        if (state?.config) {
          this.algorithm.set(state.config.algorithm); this.heuristic.set(state.config.heuristic);
          this.interval.set(state.config.interval_ms); this.maxTurns.set(state.config.max_turns);
        }
      }
    });
  }

  async create() {
    this.replay.set(null);
    await this.sim.create({ algorithm: this.algorithm(), heuristic: this.heuristic(),
      interval_ms: this.interval(), max_turns: this.maxTurns() });
  }
}
