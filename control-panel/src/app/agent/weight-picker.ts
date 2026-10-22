import { ChangeDetectionStrategy, Component, computed, inject, input, model, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { HlmButton } from '@spartan-ng/helm/button';
import { GridRender } from '../environment-api';
import { Position } from '../simulation-store';

interface Evaluation { w: number; f: number; time_ratio: number; cost_ratio: number; heap_ratio: number; }
interface MapTuning { baseline: Evaluation; curve: Evaluation[]; best: Evaluation; }

// Chart geometry, in SVG user units.
const WIDTH = 560, HEIGHT = 200, LEFT = 40, RIGHT = 12, TOP = 12, BOTTOM = 28;

/** Grid search of w on the current map; clicking a point selects that w for the run. */
@Component({
  selector: 'app-weight-picker',
  imports: [HlmButton, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './weight-picker.html',
  styleUrl: './weight-picker.css',
})
export class WeightPicker {
  private readonly http = inject(HttpClient);
  readonly grid = input<GridRender | null>(null);
  readonly start = input<Position | null>(null);
  readonly goal = input<Position | null>(null);
  readonly heuristic = input('l1');
  readonly disabled = input(false);
  readonly weight = model(2);
  readonly wMax = signal(20);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly result = signal<MapTuning | null>(null);
  readonly width = WIDTH;
  readonly height = HEIGHT;

  readonly ready = computed(() => !!this.grid() && !!this.start() && !!this.goal()
    && Number.isInteger(this.wMax()) && this.wMax() >= 2 && this.wMax() <= 100);
  readonly selected = computed(() => this.result()?.curve.find(e => e.w === this.weight()) ?? null);

  readonly chart = computed(() => {
    const r = this.result();
    if (!r) return null;
    const fs = [...r.curve.map(e => e.f), r.baseline.f];
    const low = Math.min(...fs), high = Math.max(...fs), span = high - low || 1;
    const wMax = r.curve.at(-1)!.w;
    const x = (w: number) => LEFT + (w - 1) / (wMax - 1) * (WIDTH - LEFT - RIGHT);
    const y = (f: number) => TOP + (high - f) / span * (HEIGHT - TOP - BOTTOM);
    return {
      line: r.curve.map(e => `${x(e.w).toFixed(1)},${y(e.f).toFixed(1)}`).join(' '),
      points: r.curve.map(e => ({ ...e, cx: x(e.w), cy: y(e.f), best: e.w === r.best.w })),
      baselineY: y(r.baseline.f),
      selectedX: x(Math.min(Math.max(this.weight(), 1), wMax)),
      yTicks: [low, (low + high) / 2, high].map(f => ({ f, y: y(f) })),
      xTicks: [1, ...[0.25, 0.5, 0.75, 1].map(t => Math.round(1 + t * (wMax - 1)))].map(w => ({ w, x: x(w) })),
      left: LEFT, right: WIDTH - RIGHT, bottom: HEIGHT - BOTTOM,
    };
  });

  async search() {
    const grid = this.grid(), start = this.start(), goal = this.goal();
    if (!grid || !start || !goal) return;
    this.busy.set(true);
    this.error.set('');
    try {
      this.result.set(await firstValueFrom(this.http.post<MapTuning>('/api/agent/tuning/map', {
        cells: grid.cells, weights: grid.weights, start, goal, heuristic: this.heuristic(), w_max: this.wMax(),
      })));
    } catch (err) {
      const detail = err instanceof HttpErrorResponse ? err.error?.detail : null;
      this.error.set(typeof detail === 'string' ? detail : 'The grid search failed; check that the agent service is running.');
    } finally {
      this.busy.set(false);
    }
  }
}
