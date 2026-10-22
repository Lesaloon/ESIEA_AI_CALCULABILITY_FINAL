import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { DecimalPipe, JsonPipe, NgTemplateOutlet } from '@angular/common';
import { HlmButton } from '@spartan-ng/helm/button';
import { EnvironmentStore } from '../environment/environment-store';
import { GridSearchReport, MainAlgoReport, SimulationStore } from '../simulation-store';
import { SimulationGrid } from '../simulation-grid';

@Component({
  selector: 'app-agent-panel',
  imports: [HlmButton, SimulationGrid, DecimalPipe, JsonPipe, NgTemplateOutlet],
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
  readonly searchMode = signal<'grid' | 'random' | 'main'>('grid');
  readonly searchLow = signal(1);
  readonly searchHigh = signal(10);
  readonly searchStep = signal(1);
  readonly report = signal<GridSearchReport | null>(null);
  readonly randomLow = signal(1);
  readonly randomHigh = signal(50);
  readonly randomCount = signal(10);
  readonly randomReport = signal<GridSearchReport | null>(null);
  readonly mainReport = signal<MainAlgoReport | null>(null);
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
  readonly configValid = computed(() => Number.isInteger(this.interval()) && this.interval() >= 50 && this.interval() <= 5000
    && Number.isInteger(this.maxTurns()) && this.maxTurns() >= 1 && this.maxTurns() <= 10000
    && (this.algorithm() !== 'weighted_astar' || (Number.isFinite(this.weight()) && this.weight() >= 1)));
  readonly searchValid = computed(() => {
    const low = this.searchLow(), high = this.searchHigh(), step = this.searchStep();
    return [low, high, step].every(Number.isFinite) && low >= 1 && high >= low && step > 0 && (high - low) / step <= 200;
  });
  readonly randomValid = computed(() => {
    const low = this.randomLow(), high = this.randomHigh(), count = this.randomCount();
    return [low, high].every(Number.isFinite) && Number.isInteger(count) && count >= 1 && count <= 200 && low >= 1 && high >= low;
  });
  readonly selectedAlgorithm = computed(() => this.sim.algorithms().find(a => a.id === this.algorithm()));
  readonly scoreChart = computed(() => this.buildScoreChart(this.mainReport()));

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
          if (typeof state.config.w === 'number') this.weight.set(state.config.w);
          this.interval.set(state.config.interval_ms); this.maxTurns.set(state.config.max_turns);
        }
      }
    });
  }

  async create() {
    this.replay.set(null);
    await this.sim.create({ algorithm: this.algorithm(), heuristic: this.heuristic(),
      w: this.algorithm() === 'weighted_astar' ? this.weight() : 1,
      interval_ms: this.interval(), max_turns: this.maxTurns() });
  }

  async compareWeights() {
    const target = this.searchTarget();
    if (!target) return;
    const report = await this.sim.gridSearch({
      ...target, low: this.searchLow(), high: this.searchHigh(), step: this.searchStep(),
    });
    if (report) this.report.set(report);
  }

  async drawWeights() {
    const target = this.searchTarget();
    if (!target) return;
    const report = await this.sim.randomSearch({
      ...target, low: this.randomLow(), high: this.randomHigh(), count: this.randomCount(),
    });
    if (report) this.randomReport.set(report);
  }

  async runMainAlgo() {
    const target = this.searchTarget();
    if (!target) return;
    const report = await this.sim.mainAlgo(target);
    if (report) this.mainReport.set(report);
  }

  private buildScoreChart(report: MainAlgoReport | null) {
    if (!report) return null;
    const scored = report.trials.filter(trial => trial.score !== null);
    if (!scored.length || report.best.score === null) return null;
    const width = 640;
    const height = 300;
    const pad = { left: 72, right: 28, top: 16, bottom: 48 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const minW = Math.min(...scored.map(trial => trial.w));
    const maxW = Math.max(...scored.map(trial => trial.w));
    const minS = Math.min(...scored.map(trial => trial.score as number));
    const maxS = Math.max(...scored.map(trial => trial.score as number));
    const xOf = (w: number) => pad.left + (maxW === minW ? plotW / 2 : ((w - minW) / (maxW - minW)) * plotW);
    const yOf = (score: number) => pad.top + (maxS === minS ? plotH / 2 : (1 - (score - minS) / (maxS - minS)) * plotH);
    const points = scored.map(trial => ({
      w: trial.w,
      score: trial.score as number,
      source: trial.source,
      cx: xOf(trial.w),
      cy: yOf(trial.score as number),
      best: trial.score === report.best.score && trial.w === report.best.w,
    }));
    const lowestByW = new Map<number, (typeof points)[number]>();
    for (const point of [...points].sort((a, b) => b.score - a.score)) lowestByW.set(point.w, point);
    const line = [...lowestByW.values()].sort((a, b) => a.w - b.w).map(point => `${point.cx},${point.cy}`).join(' ');
    const marked = points.find(point => point.best) ?? points[0];
    const anchor = marked.cx > width - 80 ? 'end' : 'start';
    return {
      width, height, pad, line, points: [
        ...points.filter(point => !point.best && point.source === 'grid'),
        ...points.filter(point => !point.best && point.source === 'climb'),
        ...points.filter(point => point.best),
      ],
      minW: this.formatChart(minW), maxW: this.formatChart(maxW),
      minS: this.formatChart(minS), maxS: this.formatChart(maxS),
      bestY: yOf(report.best.score),
      label: { x: anchor === 'end' ? marked.cx - 12 : marked.cx + 12, y: Math.max(pad.top + 12, marked.cy - 14), anchor },
    };
  }

  private formatChart(value: number) {
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
  }

  private searchTarget() {
    const grid = this.sim.runGrid() ?? this.env.grid();
    const { start, goal } = this.sim.scenario();
    if (!grid || !start || !goal) return null;
    return { heuristic: this.heuristic(), start, goal, weights: grid.weights };
  }
}
