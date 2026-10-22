import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { HlmButton } from '@spartan-ng/helm/button';
import { GridRender } from '../environment-api';
import { GlobalSearchReport, SimulationStore } from '../simulation-store';
import { SimulationGrid } from '../simulation-grid';

@Component({
  selector: 'app-global-search-panel',
  imports: [HlmButton, DecimalPipe, SimulationGrid],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './global-search-panel.html',
  styleUrl: './global-search-panel.css',
})
export class GlobalSearchPanel {
  readonly sim = inject(SimulationStore);
  readonly heuristic = signal('l1');
  readonly count = signal(5);
  readonly size = signal(10);
  readonly obstaclePercent = signal(8);
  readonly samples = signal(20);
  readonly seedText = signal('');
  readonly report = signal<GlobalSearchReport | null>(null);
  readonly selected = signal(0);
  readonly heuristics = [
    ['l1', 'L1 · Manhattan'], ['l2', 'L2 · Euclidean'], ['linf', 'L∞ · Chebyshev'],
    ['squared_l2', 'Squared L2'], ['mse', 'MSE'], ['zero', 'Zero · no estimate'],
  ] as const;
  readonly valid = computed(() => {
    const count = this.count(), size = this.size(), obstaclePercent = this.obstaclePercent(), samples = this.samples();
    const seed = this.seedText().trim();
    const seedOk = seed === '' || (Number.isInteger(Number(seed)) && Number(seed) >= 0 && Number(seed) <= 1_000_000_000);
    return Number.isInteger(count) && count >= 1 && count <= 100
      && Number.isInteger(size) && size >= 3 && size <= 15
      && Number.isInteger(obstaclePercent) && obstaclePercent >= 0 && obstaclePercent <= 100
      && Number.isInteger(samples) && samples >= 5 && samples <= 30
      && seedOk;
  });
  readonly preview = computed(() => {
    const map = this.report()?.maps[this.selected()];
    if (!map) return null;
    const grid: GridRender = {
      width: map.weights[0].length,
      height: map.weights.length,
      cells: map.weights.map(row => row.map(weight => weight === null ? 'obstacle' : 'empty')),
      weights: map.weights,
    };
    return { grid, start: map.start, goal: map.goal };
  });
  readonly chart = computed(() => {
    const report = this.report();
    const curve = report?.curve.filter(point => point.score !== null) ?? [];
    if (!report || !curve.length || report.best.score === null) return null;
    const width = 640, height = 300, pad = { left: 72, right: 28, top: 16, bottom: 48 };
    const minW = Math.min(...curve.map(point => point.w));
    const maxW = Math.max(...curve.map(point => point.w));
    const minS = Math.min(...curve.map(point => point.score as number));
    const maxS = Math.max(...curve.map(point => point.score as number));
    const xOf = (w: number) => pad.left + (maxW === minW ? (width - pad.left - pad.right) / 2 : ((w - minW) / (maxW - minW)) * (width - pad.left - pad.right));
    const yOf = (score: number) => pad.top + (maxS === minS ? (height - pad.top - pad.bottom) / 2 : (1 - (score - minS) / (maxS - minS)) * (height - pad.top - pad.bottom));
    const points = curve.map(point => ({
      w: point.w, score: point.score as number, cx: xOf(point.w), cy: yOf(point.score as number),
      best: point.w === report.best.w,
    }));
    const marked = points.find(point => point.best) ?? points[0];
    const anchor = marked.cx > width - 80 ? 'end' : 'start';
    return {
      width, height, pad, points,
      line: points.map(point => `${point.cx},${point.cy}`).join(' '),
      minW: this.format(minW), maxW: this.format(maxW), minS: this.format(minS), maxS: this.format(maxS),
      bestY: yOf(report.best.score),
      label: { x: anchor === 'end' ? marked.cx - 12 : marked.cx + 12, y: Math.max(pad.top + 12, marked.cy - 14), anchor },
    };
  });

  async compare() {
    const seed = this.seedText().trim();
    const report = await this.sim.globalSearch({
      heuristic: this.heuristic(), count: this.count(), size: this.size(),
      obstacle_percent: this.obstaclePercent(), samples: this.samples(),
      seed: seed === '' ? null : Number(seed),
    });
    if (report) {
      this.report.set(report);
      this.selected.set(0);
    }
  }

  private format(value: number) {
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
  }
}
