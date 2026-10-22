import { ChangeDetectionStrategy, Component, ElementRef, effect, inject, output, signal, viewChild } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { HlmButton } from '@spartan-ng/helm/button';
import { ExperimentsStore, SavedRun, heuristicName } from './experiments-store';

@Component({
  selector: 'app-experiments-panel',
  imports: [HlmButton, DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './experiments-panel.html',
  styleUrl: './experiments-panel.css',
})
export class ExperimentsPanel {
  readonly store = inject(ExperimentsStore);
  // Emitted after "Load" so the workspace can show the agent tab.
  readonly loaded = output<void>();
  readonly status = signal<{ ok: boolean; text: string } | null>(null);
  readonly renaming = signal<string | null>(null);
  readonly collapsed = signal<ReadonlySet<string>>(new Set());
  private readonly nameInput = viewChild<ElementRef<HTMLInputElement>>('nameInput');
  readonly heuristicName = heuristicName;

  constructor() {
    effect(() => {
      const input = this.nameInput()?.nativeElement;
      input?.focus();
      input?.select();
    });
  }

  save() { this.status.set(this.store.saveCurrent()); }

  load(run: SavedRun) {
    this.store.load(run);
    this.loaded.emit();
  }

  remove(run: SavedRun) {
    this.store.remove(run.id);
    this.status.set(null);
  }

  isCollapsed(key: string) { return this.collapsed().has(key); }

  toggle(key: string) {
    this.collapsed.update(keys => {
      const next = new Set(keys);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  }

  rename(key: string, name: string) {
    if (this.renaming() !== key) return;
    this.renaming.set(null);
    this.store.rename(key, name);
  }

  shortLabel(run: SavedRun) { return run.optimizerLabel.split(' ')[0]; }

  // Search parameters as they were set for the run, in the optimizer's own terms.
  describe(run: SavedRun) {
    const p = run.params;
    const range = `w from ${p['weight_min'] ?? 1} to ${p['weight_max']}`;
    const tested = new Set(run.trials.map(trial => trial.heuristic)).size;
    const heuristic = run.locked ? `heuristic locked (${heuristicName(run.heuristic)})` : `heuristic tuned (${tested} tested)`;
    switch (run.optimizer) {
      case 'grid': return `${range}, step ${p['weight_step']} · ${heuristic} · ${run.trials.length} trials`;
      case 'random': return `${p['trials']} trials · ${range} · seed ${p['seed']} · ${heuristic}`;
      case 'hill_climbing':
        return [`start ${heuristicName(run.startHeuristic)}, w = ${run.startWeight}`, `step ${p['step']}`, range,
          `${p['max_iterations']} iterations max`, ...(run.locked ? ['heuristic locked'] : [])].join(' · ');
      default: return heuristic;
    }
  }

  // Change of the best trial against the classic A* reference; lower is better for all three.
  metrics(run: SavedRun) {
    const change = (label: string, value: number | null, reference: number | null) => {
      if (value === null || !reference) return null;
      const percent = Math.round((value / reference - 1) * 100);
      return { label, text: `${label} ${percent > 0 ? '+' : percent < 0 ? '−' : '±'}${Math.abs(percent)} %`,
        kind: percent < 0 ? 'good' : percent > 0 ? 'worse' : '' };
    };
    return [change('cost', run.best.cost, run.reference.cost),
      change('time', run.best.time_ms, run.reference.time_ms),
      change('mem', run.best.memory_kb, run.reference.memory_kb)].filter(item => item !== null);
  }
}
