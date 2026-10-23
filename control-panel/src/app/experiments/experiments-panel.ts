import { ChangeDetectionStrategy, Component, computed, DestroyRef, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { HlmButton } from '@spartan-ng/helm/button';

type Objective = 'cost' | 'expanded' | 'time_ms' | 'memory_kib' | 'score';
type Metric = Objective | 'time_mean_raw_ms' | 'success_rate' | 'length' | 'gap_percent' | 'score_time' | 'score_memory' | 'score_quality' | 'score_expanded';
interface ScoreWeights { time: number; memory: number; quality: number; expanded: number; }
interface Result {
  method: string; trial: number; algorithm: string; heuristic: string; heuristic_weight: number;
  success_rate: number; maps: number; cost: number | null; length: number | null;
  gap_percent: number | null; expanded: number; time_ms: number;
  memory_kib: number; score: number; score_time: number; score_memory: number; score_quality: number; score_expanded: number;
  time_mean_raw_ms: number; timing_runs: number; timing_outliers: number;
}
interface CurvePoint { trial: number; best: number | null; success_rate: number; }
interface Experiment {
  id: string; status: string; error: string; completed: number; total: number; elapsed_ms: number;
  config: { objective: Objective; seed: number; map_source: string; map_count: number;
    weight_space: 'list' | 'range'; weight_start: number; weight_end: number; weight_step: number;
    score_weights: ScoreWeights; timing_repeats: number; };
  weight_values: number[];
  results: Result[]; curves: Record<string, CurvePoint[]>;
  method_summaries: { method: string; configurations: number; evaluations: number; search_ms: number; benchmark_ms: number;
    timing_runs: number; timing_outliers: number; best: Result | null }[];
  algorithm_summaries: { algorithm: string; label: string; configurations: number; best: Result }[];
}

@Component({
  selector: 'app-experiments-panel',
  imports: [FormsModule, DecimalPipe, HlmButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './experiments-panel.html',
  styleUrl: './experiments-panel.css',
})
export class ExperimentsPanel {
  private readonly http = inject(HttpClient);
  readonly job = signal<Experiment | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly sort = signal<Metric>('score');
  readonly descending = signal(true);
  readonly chartMode = signal<'weight' | 'trial' | 'best'>('weight');
  readonly chartMetric = signal<Metric>('score');
  readonly running = computed(() => this.job()?.status === 'running');
  readonly locked = computed(() => this.busy() || this.running());
  readonly metrics = ['zero', 'l1', 'l2', 'squared_l2', 'mse', 'linf'];
  readonly metricNames: Record<Metric, string> = {
    cost: 'Coût', expanded: 'Nœuds développés', time_ms: 'Temps lissé (ms)', time_mean_raw_ms: 'Temps brut moyen (ms)',
    success_rate: 'Réussite', length: 'Longueur', gap_percent: 'Écart optimal (%)',
    memory_kib: 'Mémoire (KiB)', score: 'Score global /100', score_time: 'Score temps /100',
    score_memory: 'Score mémoire /100', score_quality: 'Score qualité /100', score_expanded: 'Score nœuds /100',
  };
  readonly columns: Metric[] = ['score', 'success_rate', 'time_ms', 'time_mean_raw_ms', 'memory_kib', 'cost', 'gap_percent',
    'length', 'expanded', 'score_time', 'score_memory', 'score_quality', 'score_expanded'];
  readonly statuses: Record<string, string> = {
    running: 'En cours', completed: 'Terminée', cancelled: 'Annulée', failed: 'Échec',
  };
  useAstar = true;
  useDijkstra = true;
  useGrid = true;
  useRandom = true;
  selectedHeuristics = ['l1', 'l2', 'linf'];
  weightSpace: 'list' | 'range' = 'range';
  weightStart = 1;
  weightEnd = 50;
  weightStep = 1;
  weightsText = '0.5, 1, 1.5, 2';
  randomSpace = 'discrete';
  weightMin = 0;
  weightMax = 3;
  randomTrials = 8;
  seed = 42;
  mapSource = 'current';
  mapCount = 10;
  size = 10;
  density = 20;
  cellWeightMin = 1;
  cellWeightMax = 9;
  objective: Objective = 'score';
  scoreTime = 40;
  scoreMemory = 40;
  scoreQuality = 20;
  scoreExpanded = 0;
  timingRepeats = 3;
  private destroyed = false;
  private revision = 0;
  private refreshing = false;

  readonly rows = computed(() => {
    const metric = this.sort();
    const direction = this.descending() ? -1 : 1;
    return [...(this.job()?.results ?? [])].sort((a, b) => {
      const av = a[metric], bv = b[metric];
      if (av === null) return bv === null ? 0 : 1;
      if (bv === null) return -1;
      return direction * (av - bv);
    });
  });
  readonly chart = computed(() => {
    const metric = this.chartMetric();
    const cumulative = this.chartMode() === 'best';
    const byWeight = this.chartMode() === 'weight';
    const results = (this.job()?.results ?? []).filter(r => r.method !== 'baseline');
    const groupKey = (row: Result) => byWeight ? `${row.method}:${row.heuristic}` : row.method;
    const groups = [...new Set(results.map(groupKey))];
    const colors: Record<string, string> = {
      zero: '#536379', l1: '#285ea8', l2: '#a15816', squared_l2: '#8541a1', mse: '#b32d54', linf: '#056066',
    };
    const curves = groups.map(key => {
      const rows = results.filter(r => groupKey(r) === key)
        .sort((a, b) => byWeight ? a.heuristic_weight - b.heuristic_weight : a.trial - b.trial);
      const { method, heuristic } = rows[0];
      let best: Result | undefined;
      return { key, method, name: byWeight ? `${heuristic} · ${this.methodLabel(method)}` : this.methodLabel(method),
        color: byWeight ? colors[heuristic] : method === 'grid' ? '#285ea8' : '#a15816',
        points: rows.map(row => {
        const value = row[metric];
        if (value !== null && (!best || row.success_rate > best.success_rate
          || (row.success_rate === best.success_rate && (this.higherIsBetter(metric)
            ? value > best[metric]! : value < best[metric]!)))) best = row;
        const selected = cumulative ? best : row;
        const result = selected?.[metric] ?? null;
        return { axis: byWeight ? row.heuristic_weight : row.trial,
          value: result === null ? null : metric === 'success_rate' ? result * 100 : result,
          label: `${this.methodLabel(method)} · essai ${row.trial}${cumulative ? ' · meilleur jusque-là' : ''}`
            + (selected ? ` · ${selected.heuristic}, w=${selected.heuristic_weight.toFixed(4)} · réussite ${(selected.success_rate * 100).toFixed(0)}%` : '') };
      }) };
    });
    const values = curves.flatMap(curve => curve.points.flatMap(p => p.value === null ? [] : [p.value]));
    if (!values.length) return null;
    const baselineValue = this.job()?.results.find(row => row.method === 'baseline')?.[metric] ?? null;
    const reference = baselineValue === null ? null : metric === 'success_rate' ? baselineValue * 100 : baselineValue;
    const scaleValues = reference === null ? values : [...values, reference];
    const low = Math.min(...scaleValues), high = Math.max(...scaleValues);
    const padding = high === low ? Math.max(Math.abs(high) * .05, .1) : (high - low) * .08;
    const min = Math.max(0, low - padding), max = high + padding;
    const axes = curves.flatMap(curve => curve.points.map(p => p.axis));
    const config = this.job()?.config;
    if (byWeight && config?.weight_space === 'range') axes.push(config.weight_start, config.weight_end);
    const axisLow = Math.min(...axes), axisHigh = Math.max(...axes);
    const axisPadding = axisLow === axisHigh ? Math.max(.1, axisHigh * .05) : 0;
    const xMin = Math.max(0, axisLow - axisPadding), xMax = axisHigh + axisPadding;
    return { min, max, middle: (min + max) / 2, xMin, xMax, xMiddle: (xMin + xMax) / 2,
      flat: values.every(value => value === values[0]), reference,
      referenceY: reference === null ? null : 160 - (reference - min) / (max - min) * 132,
      series: curves.map(curve => {
        const points = curve.points.map(p => p.value === null ? null : ({
          x: 70 + (p.axis - xMin) / (xMax - xMin) * 506,
          y: 160 - (p.value - min) / (max - min) * 132,
          label: `${p.label} · ${this.metricNames[metric]} : ${p.value.toFixed(3)}`,
        }));
        // Missing results break the line rather than implying a successful trial.
        let penDown = false;
        const path = points.map(point => {
          if (!point) { penDown = false; return ''; }
          const command = penDown ? 'L' : 'M'; penDown = true;
          return `${command}${point.x},${point.y}`;
        }).join(' ');
        return { key: curve.key, method: curve.method, name: curve.name, color: curve.color,
          points: points.filter(p => p !== null), path };
      }),
    };
  });

  constructor() {
    void this.refresh();
    const timer = setInterval(() => { if (this.running()) void this.refresh(); }, 1000);
    inject(DestroyRef).onDestroy(() => { this.destroyed = true; clearInterval(timer); });
  }

  toggleHeuristic(value: string, selected: boolean) {
    this.selectedHeuristics = selected ? [...this.selectedHeuristics, value]
      : this.selectedHeuristics.filter(h => h !== value);
  }

  methodLabel(value: string) {
    return value === 'grid' ? 'Grid Search' : value === 'random' ? 'Random Search' : 'Référence';
  }

  sortBy(metric: Metric) {
    if (this.sort() === metric) this.descending.update(value => !value);
    else { this.sort.set(metric); this.descending.set(this.higherIsBetter(metric)); }
  }

  higherIsBetter(metric: Metric) {
    return metric === 'success_rate' || metric === 'score' || metric.startsWith('score_');
  }

  scoreWeights(): ScoreWeights {
    return { time: this.scoreTime, memory: this.scoreMemory, quality: this.scoreQuality, expanded: this.scoreExpanded };
  }

  weightsValid() {
    const values = Object.values(this.scoreWeights());
    const total = values.reduce((sum, value) => sum + value, 0);
    return values.every(value => Number.isFinite(value) && value >= 0) && Number.isFinite(total) && total > 0;
  }

  private acceptJob(job: Experiment | null) {
    if (job && job.id !== this.job()?.id) {
      const weights = job.config.score_weights;
      this.scoreTime = weights.time; this.scoreMemory = weights.memory;
      this.scoreQuality = weights.quality; this.scoreExpanded = weights.expanded;
      this.timingRepeats = job.config.timing_repeats;
    }
    this.job.set(job);
  }

  async applyScoring() {
    if (!this.weightsValid()) { this.error.set('Les pondérations doivent être positives ou nulles, avec un total supérieur à zéro.'); return; }
    this.busy.set(true); this.revision++;
    try {
      this.acceptJob(await firstValueFrom(this.http.post<Experiment>('/api/agent/experiments/scoring', this.scoreWeights())));
      this.sort.set('score'); this.descending.set(true); this.error.set('');
    } catch (error) { this.error.set(this.message(error)); }
    finally { this.busy.set(false); }
  }

  private message(error: unknown) {
    if (error instanceof HttpErrorResponse) {
      const detail = error.error?.detail;
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail)) return detail.map(d => `${d.loc?.slice(1).join('.')}: ${d.msg}`).join(' · ');
      return 'Le service Agent est inaccessible. Vérifiez qu’il est démarré.';
    }
    return error instanceof Error ? error.message : 'Une erreur est survenue.';
  }

  async refresh() {
    if (this.refreshing || this.busy()) return;
    this.refreshing = true;
    const revision = this.revision;
    try {
      const job = await firstValueFrom(this.http.get<Experiment | null>('/api/agent/experiments'));
      if (!this.destroyed && revision === this.revision) { this.acceptJob(job); this.error.set(''); }
    } catch (error) {
      if (!this.destroyed && revision === this.revision) this.error.set(this.message(error));
    } finally { this.refreshing = false; }
  }

  async start() {
    this.error.set('');
    if (!this.weightsValid()) { this.error.set('Les pondérations doivent être positives ou nulles, avec un total supérieur à zéro.'); return; }
    const weights = this.weightsText.split(',').map(w => w.trim());
    if (!this.useAstar && !this.useDijkstra) { this.error.set('Sélectionnez au moins un algorithme.'); return; }
    if (this.useAstar && ((!this.useGrid && !this.useRandom) || !this.selectedHeuristics.length)) {
      this.error.set('Sélectionnez au moins une méthode et une heuristique.'); return;
    }
    if (this.weightSpace === 'list' && weights.some(w => !w || !Number.isFinite(Number(w)))) {
      this.error.set('Saisissez les poids séparés par des virgules, avec un point décimal : 0.5, 1, 2.'); return;
    }
    if (this.weightSpace === 'range' && (!Number.isFinite(this.weightStart) || !Number.isFinite(this.weightEnd)
      || !Number.isFinite(this.weightStep) || this.weightStart < 0 || this.weightEnd < this.weightStart
      || this.weightEnd > 1000 || this.weightStep <= 0 || this.weightStep > 1000)) {
      this.error.set('Vérifiez A, B et C : 0 ≤ début ≤ fin ≤ 1000 et pas strictement positif.'); return;
    }
    this.busy.set(true);
    this.revision++;
    try {
      const job = await firstValueFrom(this.http.post<Experiment>('/api/agent/experiments', {
        algorithms: [...(this.useAstar ? ['astar'] : []), ...(this.useDijkstra ? ['dijkstra'] : [])],
        methods: [...(this.useGrid ? ['grid'] : []), ...(this.useRandom ? ['random'] : [])],
        heuristics: this.selectedHeuristics,
        weight_space: this.weightSpace,
        ...(this.weightSpace === 'list' ? { weights: weights.map(Number) }
          : { weight_start: this.weightStart, weight_end: this.weightEnd, weight_step: this.weightStep }),
        random_space: this.randomSpace,
        weight_min: this.weightMin, weight_max: this.weightMax, random_trials: this.randomTrials,
        seed: this.seed, map_source: this.mapSource, map_count: this.mapCount, size: this.size,
        obstacle_density: this.density / 100, cell_weight_min: this.cellWeightMin,
        cell_weight_max: this.cellWeightMax, objective: this.objective,
        score_weights: this.scoreWeights(), timing_repeats: this.timingRepeats,
      }));
      this.acceptJob(job); this.sort.set(this.objective); this.descending.set(this.higherIsBetter(this.objective));
    } catch (error) { this.error.set(this.message(error)); }
    finally { this.busy.set(false); }
  }

  async cancel() {
    this.busy.set(true);
    this.revision++;
    try { this.acceptJob(await firstValueFrom(this.http.post<Experiment>('/api/agent/experiments/cancel', {}))); }
    catch (error) { this.error.set(this.message(error)); }
    finally { this.busy.set(false); }
  }
}
