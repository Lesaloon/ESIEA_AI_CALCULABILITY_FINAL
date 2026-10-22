import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { DecimalPipe, JsonPipe } from '@angular/common';
import { HlmButton } from '@spartan-ng/helm/button';
import { EnvironmentStore } from '../environment/environment-store';
import { OptimizerParam, SimulationStore } from '../simulation-store';
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
  readonly algorithm = signal('astar');
  readonly heuristic = signal('l1');
  readonly weight = signal(1);
  readonly optimizer = signal('none');
  readonly optimizerParams = signal<Record<string, number>>({});
  readonly interval = signal(300);
  readonly maxTurns = signal(1000);
  readonly replay = signal<number | null>(null);
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
  // First invalid setting, or '' when the run can be created.
  readonly configProblem = computed(() => {
    const inRange = (value: number, min: number, max: number) => Number.isFinite(value) && value >= min && value <= max;
    if (this.showWeight() && !inRange(this.weight(), 1, 20)) return 'Weight w must be between 1 and 20.';
    const tuned = this.tuned();
    if (tuned) {
      for (const p of tuned.params) {
        if (!inRange(this.paramValue(p.id, p.default), p.min, p.max)) return `${p.label} must be between ${p.min} and ${p.max}.`;
      }
      const min = tuned.params.find(p => p.id === 'weight_min');
      const max = tuned.params.find(p => p.id === 'weight_max');
      if (min && max && this.paramValue(min.id, min.default) > this.paramValue(max.id, max.default)) return 'Weight min must not exceed weight max.';
    }
    if (!Number.isInteger(this.interval()) || !inRange(this.interval(), 50, 5000)) return 'Turn interval must be a whole number between 50 and 5000 ms.';
    if (!Number.isInteger(this.maxTurns()) || !inRange(this.maxTurns(), 1, 10000)) return 'Maximum turns must be a whole number between 1 and 10000.';
    return '';
  });
  readonly configValid = computed(() => !this.configProblem());
  readonly selectedAlgorithm = computed(() => this.sim.algorithms().find(a => a.id === this.algorithm()));
  readonly selectedOptimizer = computed(() => this.sim.optimizers().find(o => o.id === this.optimizer()) ?? null);
  readonly tuning = computed(() => this.sim.history()[0]?.trace.tuning ?? null);
  // Optimizer in use; only A* can be tuned.
  readonly tuned = computed(() => this.algorithm() === 'astar' ? this.selectedOptimizer() : null);
  readonly locked = computed(() => !!this.tuned() && this.paramValue('lock_heuristic', 0) === 1);
  // The configured heuristic and weight matter only when nothing tunes them: a locked heuristic
  // is used as is, and hill climbing starts from them.
  readonly showHeuristic = computed(() => this.algorithm() === 'greedy'
    || (this.algorithm() === 'astar' && (!this.tuned() || this.locked() || !!this.tuned()?.uses_start)));
  readonly showWeight = computed(() => this.algorithm() === 'astar' && (!this.tuned() || !!this.tuned()?.uses_start));
  readonly paramGroups = computed(() => {
    const groups = new Map<string, OptimizerParam[]>();
    for (const param of this.tuned()?.params ?? []) groups.set(param.group, [...groups.get(param.group) ?? [], param]);
    return [...groups].map(([name, params]) => ({ name, params }));
  });

  constructor() {
    let runId: string | undefined;
    effect(() => {
      const state = this.sim.state();
      if (state?.run?.run_id !== runId) {
        runId = state?.run?.run_id;
        this.replay.set(null);
        if (state?.config) {
          this.algorithm.set(state.config.algorithm);
          this.heuristic.set(state.config.heuristic);
          this.weight.set(state.config.weight);
          this.optimizer.set(state.config.optimizer);
          this.optimizerParams.set({ ...state.config.optimizer_params });
          this.interval.set(state.config.interval_ms); this.maxTurns.set(state.config.max_turns);
        }
      }
    });
  }

  delta(value: number | null, reference: number | null) {
    if (value === null || !reference) return '';
    const percent = Math.round((value / reference - 1) * 100);
    return percent === 0 ? '±0%' : `${percent > 0 ? '+' : ''}${percent}%`;
  }

  paramValue(id: string, fallback: number) { return this.optimizerParams()[id] ?? fallback; }

  setParam(id: string, value: number) { this.optimizerParams.update(params => ({ ...params, [id]: value })); }

  setOptimizer(id: string) {
    this.optimizer.set(id);
    this.optimizerParams.set({});
  }

  async create() {
    this.replay.set(null);
    const tuned = this.tuned();
    await this.sim.create({ algorithm: this.algorithm(), heuristic: this.heuristic(), weight: this.showWeight() ? this.weight() : 1,
      optimizer: tuned ? this.optimizer() : 'none',
      optimizer_params: tuned ? Object.fromEntries(tuned.params.map(p => [p.id, this.paramValue(p.id, p.default)])) : {},
      interval_ms: this.interval(), max_turns: this.maxTurns() });
  }
}
