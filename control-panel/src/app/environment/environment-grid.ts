import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { EnvironmentStore } from './environment-store';

@Component({
  selector: 'app-environment-grid',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './environment-grid.html',
  styleUrl: './environment-grid.css',
})
export class EnvironmentGrid {
  readonly store = inject(EnvironmentStore);

  weightColor(weight: number | null) {
    return weight === null ? null : `hsl(214 90% ${97 - (weight - 1) * 3}%)`;
  }

  cellLabel(x: number, y: number) {
    const grid = this.store.grid();
    if (!grid) return '';
    const obstacle = grid.cells[y][x] === 'obstacle';
    const action = this.store.editMode() === 'obstacles'
      ? (obstacle ? 'Remove obstacle' : 'Add obstacle')
      : (obstacle ? 'Switch to Obstacles mode to unblock' : `Set weight to ${this.store.selectedWeight()}`);
    return `Cell (${x}, ${y}): ${obstacle ? 'obstacle' : 'weight ' + (grid.weights[y][x] ?? 'restoring')}. ${action}`;
  }
}
