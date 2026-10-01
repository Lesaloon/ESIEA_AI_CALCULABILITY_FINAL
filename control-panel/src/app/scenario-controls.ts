import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { HlmButton } from '@spartan-ng/helm/button';
import { EnvironmentStore } from './environment/environment-store';
import { SimulationStore } from './simulation-store';

@Component({
  selector: 'app-scenario-controls',
  imports: [HlmButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './scenario-controls.html',
  styles: `
    :host { display: block; margin-top: 20px; }
    fieldset { display: flex; flex-wrap: wrap; align-items: end; gap: 14px; border: 0; padding: 0; }
    legend { font-weight: 600; font-size: 14px; margin-bottom: 12px; }
    .coordinate-inputs { display: flex; gap: 8px; }
    label { display: grid; gap: 5px; font-size: 12px; }
    input { width: 68px; padding: 6px; border: 1px solid var(--border); border-radius: 4px; background: white; }
    p { font-size: 12px; color: var(--muted-foreground); margin-top: 10px; }
  `,
})
export class ScenarioControls {
  readonly sim = inject(SimulationStore);
  readonly env = inject(EnvironmentStore);
  readonly sx = signal(0);
  readonly sy = signal(0);
  readonly gx = signal(9);
  readonly gy = signal(9);
  readonly valid = computed(() => {
    const grid = this.env.grid();
    return !!grid && [this.sx(), this.gx()].every(v => Number.isInteger(v) && v >= 0 && v < grid.width)
      && [this.sy(), this.gy()].every(v => Number.isInteger(v) && v >= 0 && v < grid.height);
  });
  constructor() {
    effect(() => {
      const { start, goal } = this.sim.scenario();
      const grid = this.env.grid();
      this.sx.set(start?.x ?? 0); this.sy.set(start?.y ?? 0);
      this.gx.set(goal?.x ?? (grid?.width ?? 10) - 1); this.gy.set(goal?.y ?? (grid?.height ?? 10) - 1);
    });
  }
  async apply() { await this.sim.configure({ x: this.sx(), y: this.sy() }, { x: this.gx(), y: this.gy() }); }
}
