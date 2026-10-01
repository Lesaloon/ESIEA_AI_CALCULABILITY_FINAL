import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { HlmButton } from '@spartan-ng/helm/button';
import { EnvironmentStore } from './environment-store';

@Component({
  selector: 'app-grid-controls',
  imports: [HlmButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './grid-controls.html',
  styleUrl: './grid-controls.css',
})
export class GridControls {
  readonly store = inject(EnvironmentStore);
}
