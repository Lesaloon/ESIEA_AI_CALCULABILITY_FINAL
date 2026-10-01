import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom, timeout } from 'rxjs';
import { EnvironmentApi, GridRender } from '../environment-api';
import { SimulationStore } from '../simulation-store';

@Injectable({ providedIn: 'root' })
export class EnvironmentStore {
  private readonly api = inject(EnvironmentApi);
  readonly simulation = inject(SimulationStore);
  readonly grid = signal<GridRender | null>(null);
  readonly selectedSize = signal(10);
  readonly editMode = signal<'obstacles' | 'weights' | 'start' | 'goal'>('obstacles');
  readonly selectedWeight = signal(3);
  readonly painting = signal(false);
  private stroke: {
    pointerId: number;
    mode: 'obstacles' | 'weights';
    obstacle: boolean;
    weight: number;
    original: GridRender;
    cells: Map<string, { x: number; y: number }>;
    last: { x: number; y: number } | null;
  } | null = null;
  readonly validWeight = computed(() => Number.isInteger(this.selectedWeight())
    && this.selectedWeight() >= 1 && this.selectedWeight() <= 9);
  readonly changedWeights = computed(() =>
    this.grid()?.weights.some(row => row.some(weight => weight !== null && weight !== 1)) ?? false,
  );
  readonly walkableCells = computed(() => {
    const grid = this.grid();
    return grid ? grid.width * grid.height - this.obstacles() : 0;
  });
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly obstacles = computed(() =>
    this.grid()?.cells.flat().filter(cell => cell === 'obstacle').length ?? 0,
  );

  constructor() {
    void this.refresh();
  }

  async refresh() {
    await this.run(async () => {
      this.setGrid(await firstValueFrom(this.api.render().pipe(timeout(8000))));
      this.message.set('Grid is up to date.');
    });
  }

  async toggleObstacle(x: number, y: number) {
    const cell = this.grid()?.cells[y][x];
    if (!cell) return;
    await this.run(async () => {
      const request = cell === 'obstacle'
        ? this.api.removeObstacle(x, y)
        : this.api.placeObstacle(x, y);
      await firstValueFrom(request.pipe(timeout(8000)));
      this.setGrid(await firstValueFrom(this.api.render().pipe(timeout(8000))));
      this.message.set(`Obstacle ${cell === 'obstacle' ? 'removed' : 'placed'} at (${x}, ${y}).`);
    });
  }

  async editCell(x: number, y: number) {
    if (this.simulation.locked() || this.simulation.busy() || this.busy()) return;
    const mode = this.editMode();
    if (mode === 'start' || mode === 'goal') {
      await this.simulation.place(mode, { x, y });
      return;
    }
    if (this.editMode() === 'obstacles') {
      await this.toggleObstacle(x, y);
      return;
    }
    const grid = this.grid();
    const weight = this.selectedWeight();
    if (!this.validWeight() || grid?.cells[y][x] !== 'empty' || grid.weights[y][x] === weight) return;
    await this.run(async () => {
      this.setGrid(await firstValueFrom(this.api.setWeight(x, y, weight).pipe(timeout(8000))));
      this.message.set(`Weight at (${x}, ${y}) set to ${weight}.`);
    });
  }

  clickCell(event: MouseEvent, x: number, y: number) {
    // Mouse edits are handled on pointerdown; retain keyboard/touch clicks.
    if (event.detail > 0 && (event as PointerEvent).pointerType === 'mouse'
      && (this.editMode() === 'obstacles' || this.editMode() === 'weights')) return;
    void this.editCell(x, y);
  }

  startBrush(event: PointerEvent, x: number, y: number) {
    const grid = this.grid();
    const mode = this.editMode();
    if (this.simulation.locked() || this.simulation.busy()) return;
    if (mode === 'start' || mode === 'goal') return;
    if (event.pointerType !== 'mouse' || event.button !== 0 || this.busy()
      || !grid || (mode === 'weights' && (!this.validWeight() || grid.cells[y][x] !== 'empty'))) return;
    event.preventDefault();
    (event.currentTarget as HTMLElement).focus();
    this.stroke = {
      pointerId: event.pointerId, weight: this.selectedWeight(), original: grid,
      mode, obstacle: grid.cells[y][x] === 'empty',
      cells: new Map(), last: null,
    };
    this.busy.set(true);
    this.painting.set(true);
    this.error.set('');
    this.message.set('');
    this.paintThrough(x, y);
  }

  continueBrush(event: PointerEvent, x: number, y: number) {
    if (!this.stroke || event.pointerId !== this.stroke.pointerId) return;
    if (!(event.buttons & 1)) {
      void this.finishBrush(event);
      return;
    }
    this.paintThrough(x, y);
  }

  leaveBrushBoard() {
    if (this.stroke) this.stroke.last = null;
  }

  private paintThrough(x: number, y: number) {
    const stroke = this.stroke;
    const grid = this.grid();
    if (!stroke || !grid) return;
    const from = stroke.last ?? { x, y };
    const steps = Math.max(Math.abs(x - from.x), Math.abs(y - from.y), 1);
    const weights = grid.weights.map(row => [...row]);
    const cells = grid.cells.map(row => [...row]);
    // Fill between pointer samples so quick drags do not leave holes.
    for (let step = 0; step <= steps; step++) {
      const cx = Math.round(from.x + (x - from.x) * step / steps);
      const cy = Math.round(from.y + (y - from.y) * step / steps);
      if (stroke.mode === 'weights') {
        if (cells[cy][cx] !== 'empty' || weights[cy][cx] === stroke.weight) continue;
        weights[cy][cx] = stroke.weight;
      } else {
        const target = stroke.obstacle ? 'obstacle' : 'empty';
        if (cells[cy][cx] === target) continue;
        cells[cy][cx] = target;
        // Restored weights come from the server when the stroke is saved.
        weights[cy][cx] = null;
      }
      stroke.cells.set(`${cx},${cy}`, { x: cx, y: cy });
    }
    stroke.last = { x, y };
    this.grid.set({ ...grid, cells, weights });
  }

  async finishBrush(event?: PointerEvent) {
    const stroke = this.stroke;
    if (!stroke || (event && event.pointerId !== stroke.pointerId)) return;
    this.stroke = null;
    this.painting.set(false);
    this.busy.set(false);
    if (!stroke.cells.size) return;
    await this.run(async () => {
      try {
        const cells = [...stroke.cells.values()];
        const request = stroke.mode === 'weights'
          ? this.api.paintWeights(cells, stroke.weight)
          : this.api.paintObstacles(cells, stroke.obstacle);
        this.setGrid(await firstValueFrom(request.pipe(timeout(8000))));
        this.message.set(stroke.mode === 'weights'
          ? `Painted ${cells.length} cell${cells.length === 1 ? '' : 's'} with weight ${stroke.weight}.`
          : `${stroke.obstacle ? 'Placed' : 'Removed'} ${cells.length} obstacle${cells.length === 1 ? '' : 's'}.`);
      } catch (error) {
        this.grid.set(stroke.original);
        throw error;
      }
    });
  }

  async applyWeightToAll() {
    if (!this.validWeight() || !this.walkableCells()) return;
    const weight = this.selectedWeight();
    await this.run(async () => {
      this.setGrid(await firstValueFrom(this.api.setAllWeights(weight).pipe(timeout(8000))));
      this.message.set(`All walkable cell weights set to ${weight}.`);
    });
  }

  async resetWeights() {
    await this.run(async () => {
      this.setGrid(await firstValueFrom(this.api.resetWeights().pipe(timeout(8000))));
      this.message.set('All weights reset to 1, including saved weights beneath obstacles.');
    });
  }

  async reset() {
    await this.run(async () => {
      this.setGrid(await firstValueFrom(this.api.reset().pipe(timeout(8000))));
      this.message.set('Grid reset: obstacles cleared and weights set to 1.');
    });
  }

  async resize() {
    const size = this.selectedSize();
    if (size === this.grid()?.width) return;
    await this.run(async () => {
      this.setGrid(await firstValueFrom(this.api.resize(size).pipe(timeout(8000))));
      await this.simulation.refresh();
      this.message.set(`Grid resized to ${size} × ${size}.`);
    });
  }

  private setGrid(grid: GridRender) {
    this.grid.set(grid);
    this.selectedSize.set(grid.width);
  }

  private async run(action: () => Promise<void>) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await action();
    } catch (error) {
      const detail = error instanceof HttpErrorResponse ? error.error?.detail : null;
      this.error.set(typeof detail === 'string'
        ? `${detail}. Refresh to get the latest grid.`
        : 'Could not reach the environment. Check that the environment service is running, then refresh.');
    } finally {
      this.busy.set(false);
    }
  }
}
