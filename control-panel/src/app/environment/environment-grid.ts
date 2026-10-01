import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { EnvironmentStore } from './environment-store';
import { SimulationGrid } from '../simulation-grid';

@Component({
  selector: 'app-environment-grid',
  imports: [SimulationGrid],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './environment-grid.html',
  styleUrl: './environment-grid.css',
})
export class EnvironmentGrid {
  readonly store = inject(EnvironmentStore);
}
