import { ChangeDetectionStrategy, Component, computed, inject, signal, WritableSignal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom, timeout } from 'rxjs';
import { HlmButton } from '@spartan-ng/helm/button';
import { SimulationStore } from '../simulation-store';

export interface BenchmarkRow {
  size: number; connectivity: number; obstacle: string; algorithm: string; label: string; heuristic: string;
  admissible: boolean; time_ms: number; memory_kb: number; expanded: number; depth: number | null;
  cost: number | null; cost_ratio: number | null; optimal: boolean; expanded_vs_dijkstra: number | null;
}
export interface BenchmarkMap { label: string; preview: string[]; optimal_cost: number; }
export interface BenchmarkResult { rows: BenchmarkRow[]; maps: BenchmarkMap[]; weight: number; repeat: number; }
export interface StrategyResult {
  score: number | null; cost: number | null; cost_ratio: number | null; time_ms: number; memory_kb: number;
  expanded: number; heuristic?: string; weight?: number; regret?: number | null;
}
export interface TransferRow {
  label: string; optimal_cost: number; evaluations: number;
  fixed: StrategyResult; reference: StrategyResult; robust: StrategyResult; retuned: StrategyResult;
}
export interface StrategySummary {
  mean_score: number | null; mean_cost_ratio: number | null; worst_cost_ratio: number | null; mean_expanded: number | null;
  mean_regret?: number | null; heuristic?: string; weight?: number; evaluations?: number;
}
export interface TransferResult {
  solution: { heuristic: string; weight: number }; rows: TransferRow[];
  summary: Record<'fixed' | 'reference' | 'robust' | 'retuned', StrategySummary>;
  grid: { weight_min: number; weight_max: number; weight_step: number; heuristics: string[] };
}

const OBSTACLES = [
  { id: 'none', label: 'No obstacle' }, { id: 'u', label: 'U trap' },
  { id: 'wall', label: 'Vertical wall' }, { id: 'random', label: 'Random walls' },
];
const HEURISTICS = [
  { id: 'l1', label: 'L1' }, { id: 'l2', label: 'L2' }, { id: 'linf', label: 'L∞' },
  { id: 'squared_l2', label: 'Squared L2' }, { id: 'mse', label: 'MSE' },
];
const ALGORITHMS = [
  { id: 'dijkstra', label: 'Dijkstra' }, { id: 'astar', label: 'A*' },
  { id: 'weighted_astar', label: 'Weighted A*' }, { id: 'greedy', label: 'Greedy' },
];

@Component({
  selector: 'app-experiments-panel',
  imports: [HlmButton, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './experiments-panel.html',
  styleUrl: './experiments-panel.css',
})
export class ExperimentsPanel {
  private readonly http = inject(HttpClient);
  readonly sim = inject(SimulationStore);
  readonly obstacles = OBSTACLES;
  readonly heuristics = HEURISTICS;
  readonly algorithms = ALGORITHMS;
  readonly sizeChoices = [10, 20, 30, 40];

  // Algorithm comparison (morning instructions)
  readonly bSizes = signal<number[]>([20]);
  readonly bConnectivities = signal<number[]>([4, 8]);
  readonly bHeuristics = signal<string[]>(['l1', 'l2']);
  readonly bObstacles = signal<string[]>(['none', 'u', 'wall']);
  readonly bAlgorithms = signal<string[]>(['dijkstra', 'astar', 'weighted_astar', 'greedy']);
  readonly bWeight = signal(2);
  readonly bWeights = signal<'random' | 'uniform'>('random');
  readonly bSeed = signal(0);
  readonly bRepeat = signal(3);
  readonly benchmark = signal<BenchmarkResult | null>(null);
  readonly benchmarkBusy = signal(false);
  readonly benchmarkError = signal('');
  readonly obstacleFilter = signal('all');
  readonly shownRows = computed(() => (this.benchmark()?.rows ?? [])
    .filter(r => this.obstacleFilter() === 'all' || r.obstacle === this.obstacleFilter()));

  // Generalization (report questions 3 and 4)
  readonly tHeuristic = signal('linf');
  readonly tWeight = signal(2);
  readonly tSizes = signal<number[]>([10, 20, 30]);
  readonly tConnectivities = signal<number[]>([4, 8]);
  readonly tObstacles = signal<string[]>(['none', 'u', 'wall', 'random']);
  readonly tWeights = signal<'random' | 'uniform'>('random');
  readonly tSeed = signal(0);
  readonly tLock = signal(false);
  readonly tMin = signal(1);
  readonly tMax = signal(5);
  readonly tStep = signal(0.5);
  readonly tCost = signal(1);
  readonly tTime = signal(1);
  readonly tMemory = signal(1);
  readonly transfer = signal<TransferResult | null>(null);
  readonly transferBusy = signal(false);
  readonly transferError = signal('');
  readonly lastTuning = computed(() => this.sim.history()[0]?.trace.tuning ?? null);
  readonly strategies = [
    { id: 'fixed', label: 'Fixed solution', help: 'tuned once, reused as is' },
    { id: 'reference', label: 'Classic A*', help: 'L∞, w = 1' },
    { id: 'robust', label: 'Robust pair', help: 'best mean score over all these maps' },
    { id: 'retuned', label: 'Re-tuned per map', help: 'grid search redone on every map' },
  ] as const;

  toggle<T>(list: WritableSignal<T[]>, value: T) {
    list.update(items => items.includes(value) ? items.filter(item => item !== value) : [...items, value]);
  }

  useLastTuning() {
    const tuning = this.lastTuning();
    if (!tuning) return;
    this.tHeuristic.set(tuning.heuristic);
    this.tWeight.set(tuning.weight);
    for (const [key, target] of [['cost_weight', this.tCost], ['time_weight', this.tTime], ['memory_weight', this.tMemory]] as const) {
      if (tuning.params[key] !== undefined) target.set(tuning.params[key]);
    }
  }

  async runBenchmark() {
    this.benchmarkBusy.set(true);
    this.benchmarkError.set('');
    try {
      this.benchmark.set(await this.post<BenchmarkResult>('/api/agent/experiments/benchmark', {
        sizes: this.bSizes(), connectivities: this.bConnectivities(), heuristics: this.bHeuristics(),
        obstacles: this.bObstacles(), algorithms: this.bAlgorithms(), weight: this.bWeight(),
        weights: this.bWeights(), seed: this.bSeed(), repeat: this.bRepeat(),
      }));
      this.obstacleFilter.set('all');
    } catch (error) {
      this.benchmarkError.set(this.message(error));
    } finally {
      this.benchmarkBusy.set(false);
    }
  }

  async runTransfer() {
    this.transferBusy.set(true);
    this.transferError.set('');
    try {
      this.transfer.set(await this.post<TransferResult>('/api/agent/experiments/transfer', {
        heuristic: this.tHeuristic(), weight: this.tWeight(), sizes: this.tSizes(),
        connectivities: this.tConnectivities(), obstacles: this.tObstacles(), weights: this.tWeights(),
        seed: this.tSeed(), lock_heuristic: this.tLock(), weight_min: this.tMin(), weight_max: this.tMax(),
        weight_step: this.tStep(), cost_weight: this.tCost(), time_weight: this.tTime(), memory_weight: this.tMemory(),
      }));
    } catch (error) {
      this.transferError.set(this.message(error));
    } finally {
      this.transferBusy.set(false);
    }
  }

  obstacleLabel(id: string) { return OBSTACLES.find(o => o.id === id)?.label ?? id; }

  heuristicLabel(id: string | undefined) { return HEURISTICS.find(h => h.id === id)?.label ?? id ?? ''; }

  previewText(map: BenchmarkMap) { return map.preview.join('\n'); }

  percent(value: number | null) { return value === null ? 0 : Math.min(100, Math.max(2, value * 100)); }

  private post<T>(url: string, body: unknown) {
    return firstValueFrom(this.http.post<T>(url, body).pipe(timeout(180000)));
  }

  private message(error: unknown) {
    if (error instanceof HttpErrorResponse) {
      const detail = error.error?.detail;
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail)) return detail.map(d => d.msg).join(' · ');
      return error.status ? `Request failed (${error.status})` : 'The agent service is not reachable.';
    }
    return error instanceof Error ? error.message : 'Request failed';
  }
}
