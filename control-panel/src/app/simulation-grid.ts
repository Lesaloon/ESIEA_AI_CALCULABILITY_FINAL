import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { GridRender } from './environment-api';
import { KnownCell, Position, Trace } from './simulation-store';

@Component({
  selector: 'app-simulation-grid',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './simulation-grid.html',
  styleUrl: './simulation-grid.css',
})
export class SimulationGrid {
  readonly grid = input.required<GridRender>();
  readonly start = input<Position | null>(null);
  readonly goal = input<Position | null>(null);
  readonly agent = input<Position | null>(null);
  readonly knowledge = input<KnownCell[] | null>(null);
  readonly trail = input<Position[]>([]);
  readonly trace = input<Trace | null>(null);
  readonly disabled = input(false);
  readonly editable = input(false);
  readonly label = input('Simulation cells');
  readonly actionLabel = input('');
  readonly cellClick = output<{ event: MouseEvent; x: number; y: number }>();
  readonly cellDown = output<{ event: PointerEvent; x: number; y: number }>();
  readonly cellEnter = output<{ event: PointerEvent; x: number; y: number }>();
  readonly boardLeave = output<void>();
  readonly known = computed(() => new Map(this.knowledge()?.map(cell => [`${cell.x},${cell.y}`, cell])));
  readonly visits = computed(() => {
    const result = new Map<string, number>();
    for (const cell of this.trail()) {
      const key = `${cell.x},${cell.y}`;
      result.set(key, (result.get(key) ?? 0) + 1);
    }
    return result;
  });
  readonly expanded = computed(() => new Set(this.trace()?.expanded.map(p => `${p.x},${p.y}`)));
  readonly frontier = computed(() => new Set(this.trace()?.frontier.map(p => `${p.x},${p.y}`)));
  readonly path = computed(() => new Set(this.trace()?.candidate_path.map(p => `${p.x},${p.y}`)));

  at(point: Position | null, x: number, y: number) { return point?.x === x && point.y === y; }
  unknown(x: number, y: number) { return this.knowledge() !== null && !this.known().has(`${x},${y}`); }
  weight(x: number, y: number) {
    return this.knowledge() === null ? this.grid().weights[y][x] : this.known().get(`${x},${y}`)?.weight ?? null;
  }
  color(x: number, y: number) {
    const weight = this.weight(x, y);
    return weight === null ? null : `hsl(214 90% ${97 - (weight - 1) * 3}%)`;
  }
  cellLabel(x: number, y: number) {
    const unknown = this.unknown(x, y);
    const obstacle = !unknown && this.grid().cells[y][x] === 'obstacle';
    const roles = [this.at(this.start(), x, y) ? 'start' : '', this.at(this.goal(), x, y) ? 'goal' : '',
      this.at(this.agent(), x, y) ? 'agent' : ''].filter(Boolean).join(', ');
    return `Cell (${x}, ${y}): ${unknown ? 'unknown' : obstacle ? 'obstacle' : 'weight ' + (this.weight(x, y) ?? 'restoring')}. ${roles}. Visits: ${this.visits().get(`${x},${y}`) ?? 0}. ${this.actionLabel()}`;
  }
}
