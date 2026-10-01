import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { HlmButton } from '@spartan-ng/helm/button';
import { EnvironmentStore } from './environment-store';
import { GridControls } from './grid-controls';
import { EnvironmentGrid } from './environment-grid';

@Component({
  selector: 'app-environment-panel',
  imports: [HlmButton, GridControls, EnvironmentGrid],
  providers: [EnvironmentStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './environment-panel.html',
  styleUrl: './environment-panel.css',
  host: {
    '(document:pointerup)': 'store.finishBrush($event)',
    '(document:pointercancel)': 'store.finishBrush($event)',
    '(window:blur)': 'store.finishBrush()',
  },
})
export class EnvironmentPanel {
  readonly store = inject(EnvironmentStore);
}
