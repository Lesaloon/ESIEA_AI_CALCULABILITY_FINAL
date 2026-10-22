import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { HlmButton } from '@spartan-ng/helm/button';

export interface TuningSettings {
  size: number; connectivity: 4 | 8; heuristic: string; alpha: number; beta: number; gamma: number;
  max_cost_ratio: number | null; w_max: number; start: number; repeat: number; seed: number;
}
export interface Evaluation { w: number; f: number; time_ratio: number; cost_ratio: number; heap_ratio: number; }
export interface MethodResult { id: string; label: string; best: Evaluation; evaluations: number; evaluated: number[]; }
export interface TuningResult { settings: TuningSettings; baseline: Evaluation; methods: MethodResult[]; curve: Evaluation[]; }

// Chart geometry, in SVG user units.
const WIDTH = 640, HEIGHT = 240, LEFT = 44, RIGHT = 12, TOP = 12, BOTTOM = 30;
const COLORS: Record<string, string> = {
  grid: '#285ea8', random: '#8a5a00', hill: '#a32323', annealing: '#6b3fa0', tabu: '#056066', hybrid: '#c2410c',
};

@Component({
  selector: 'app-tuning-panel',
  imports: [HlmButton, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tuning-panel.html',
  styleUrl: './tuning-panel.css',
})
export class TuningPanel {
  private readonly http = inject(HttpClient);
  readonly size = signal(30);
  readonly connectivity = signal<4 | 8>(8);
  readonly heuristic = signal('l1');
  readonly alpha = signal(1);
  readonly beta = signal(1);
  readonly gamma = signal(1);
  readonly maxCostRatio = signal<number | null>(null);
  readonly wMax = signal(50);
  readonly start = signal(2.4);
  readonly seed = signal(0);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly result = signal<TuningResult | null>(null);
  readonly width = WIDTH;
  readonly height = HEIGHT;

  readonly valid = computed(() => [this.size(), this.alpha(), this.beta(), this.gamma(), this.wMax(), this.start(), this.seed()]
      .every(Number.isFinite)
    && this.size() >= 10 && this.size() <= 40 && this.wMax() >= 2 && this.wMax() <= 100
    && this.start() >= 1 && this.start() <= this.wMax()
    && (this.maxCostRatio() === null || this.maxCostRatio()! >= 1));
  readonly bestF = computed(() => Math.min(...(this.result()?.methods.map(m => m.best.f) ?? [])));

  /** Scales for the F(w) chart, fitted to the curve and the baseline. */
  private readonly scale = computed(() => {
    const r = this.result();
    if (!r) return null;
    const fs = [...r.curve.map(e => e.f), r.baseline.f, ...r.methods.map(m => m.best.f)];
    const low = Math.min(...fs), high = Math.max(...fs), span = high - low || 1;
    const wMax = r.settings.w_max;
    return {
      x: (w: number) => LEFT + (w - 1) / (wMax - 1) * (WIDTH - LEFT - RIGHT),
      y: (f: number) => TOP + (high - f) / span * (HEIGHT - TOP - BOTTOM),
      low, high, wMax,
    };
  });
  readonly chart = computed(() => {
    const r = this.result(), s = this.scale();
    if (!r || !s) return null;
    return {
      line: r.curve.map(e => `${s.x(e.w).toFixed(1)},${s.y(e.f).toFixed(1)}`).join(' '),
      baselineY: s.y(r.baseline.f),
      points: r.methods.map(m => ({ id: m.id, label: m.label, x: s.x(m.best.w), y: s.y(m.best.f), color: this.color(m.id) })),
      xTicks: [1, ...[0.25, 0.5, 0.75, 1].map(t => Math.round(1 + t * (s.wMax - 1)))].map(w => ({ w, x: s.x(w) })),
      yTicks: [s.low, (s.low + s.high) / 2, s.high].map(f => ({ f, y: s.y(f) })),
      bottom: HEIGHT - BOTTOM, left: LEFT, right: WIDTH - RIGHT,
    };
  });

  color(id: string) { return COLORS[id] ?? '#536379'; }

  number(input: HTMLInputElement) { return input.valueAsNumber; }

  async run() {
    this.busy.set(true);
    this.error.set('');
    try {
      this.result.set(await firstValueFrom(this.http.post<TuningResult>('/api/agent/tuning', {
        size: this.size(), connectivity: this.connectivity(), heuristic: this.heuristic(),
        alpha: this.alpha(), beta: this.beta(), gamma: this.gamma(), max_cost_ratio: this.maxCostRatio(),
        w_max: this.wMax(), start: this.start(), seed: this.seed(),
      })));
    } catch (err) {
      const detail = err instanceof HttpErrorResponse ? err.error?.detail : null;
      this.error.set(typeof detail === 'string' ? detail : 'The tuning request failed; check that the agent service is running.');
    } finally {
      this.busy.set(false);
    }
  }
}
