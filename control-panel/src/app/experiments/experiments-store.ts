import { Injectable, computed, inject, signal } from '@angular/core';
import { GridRender } from '../environment-api';
import { EnvironmentStore } from '../environment/environment-store';
import { Position, Reference, SimulationStore, Trial } from '../simulation-store';

const STORAGE_KEY = 'aic.saved-experiments.v1';

export const HEURISTIC_NAMES: Record<string, string> = {
  zero: 'Zero', l1: 'L1', l2: 'L2', linf: 'L∞', squared_l2: 'Squared L2', mse: 'MSE',
};

export interface SavedRun {
  id: string; runId: string; savedAt: string;
  grid: { key: string; width: number; height: number; start: Position; goal: Position };
  importances: { cost: number; time: number; memory: number };
  optimizer: string; optimizerLabel: string;
  heuristic: string; weight: number; score: number | null;
  startHeuristic: string; startWeight: number; locked: boolean;
  params: Record<string, number>;
  best: Trial; reference: Reference; trials: Trial[];
}

export interface FunctionGroup { key: string; formula: string; runs: SavedRun[]; best: SavedRun | null; latest: string; }
export interface GridGroup {
  key: string; name: string; start: Position; goal: Position; count: number;
  current: boolean; functions: FunctionGroup[]; latest: string;
}

export function heuristicName(id: string) { return HEURISTIC_NAMES[id] ?? id; }

// FNV-1a: identifies a grid (cells, weights) with its endpoints, so runs on the same problem group together.
function fingerprint(grid: GridRender, start: Position, goal: Position) {
  const text = JSON.stringify([grid.cells, grid.weights, start, goal]);
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) hash = Math.imul(hash ^ text.charCodeAt(i), 0x01000193);
  return (hash >>> 0).toString(16);
}

const number = (value: number) => String(Number(value.toFixed(2)));

@Injectable({ providedIn: 'root' })
export class ExperimentsStore {
  private readonly sim = inject(SimulationStore);
  private readonly env = inject(EnvironmentStore);
  private readonly stored = this.read();
  readonly runs = signal<SavedRun[]>(this.stored.runs);
  readonly names = signal<Record<string, string>>(this.stored.names);
  readonly storageError = signal('');
  // Set by "Load"; the agent panel applies it to its form and clears it.
  readonly pendingLoad = signal<SavedRun | null>(null);

  private readonly currentKey = computed(() => {
    const grid = this.env.grid();
    const { start, goal } = this.sim.scenario();
    return grid && start && goal ? fingerprint(grid, start, goal) : null;
  });

  readonly groups = computed<GridGroup[]>(() => {
    const names = this.names();
    const byGrid = new Map<string, SavedRun[]>();
    for (const run of [...this.runs()].sort((a, b) => a.savedAt.localeCompare(b.savedAt))) {
      byGrid.set(run.grid.key, [...byGrid.get(run.grid.key) ?? [], run]);
    }
    const sameSize = new Map<string, number>();
    const groups = [...byGrid].map(([key, runs]) => {
      const { width, height, start, goal } = runs[0].grid;
      const size = `${width}×${height}`;
      const rank = (sameSize.get(size) ?? 0) + 1;
      sameSize.set(size, rank);
      const byFunction = new Map<string, SavedRun[]>();
      for (const run of runs) {
        const id = `${run.importances.cost}|${run.importances.time}|${run.importances.memory}`;
        byFunction.set(id, [...byFunction.get(id) ?? [], run]);
      }
      const functions = [...byFunction].map(([id, functionRuns]): FunctionGroup => {
        const { cost, time, memory } = functionRuns[0].importances;
        const scored = functionRuns.filter(run => run.score !== null);
        return {
          key: id, runs: [...functionRuns].reverse(), latest: functionRuns.at(-1)!.savedAt,
          formula: `F = ${number(cost)} × cost + ${number(time)} × time + ${number(memory)} × memory`,
          best: scored.length ? scored.reduce((a, b) => (b.score! < a.score! ? b : a)) : null,
        };
      }).sort((a, b) => b.latest.localeCompare(a.latest));
      return {
        key, start, goal, functions, count: runs.length, latest: runs.at(-1)!.savedAt,
        name: names[key] || `Grid ${size}${rank > 1 ? ` (${rank})` : ''}`,
        current: key === this.currentKey(),
      };
    });
    return groups.sort((a, b) => b.latest.localeCompare(a.latest));
  });

  saveCurrent(): { ok: boolean; text: string } {
    const state = this.sim.state();
    const run = state?.run;
    const config = state?.config;
    const grid = this.sim.runGrid();
    if (!run || !config) return { ok: false, text: 'Create a run in the Agent tab first.' };
    const tuning = this.sim.history()[0]?.trace.tuning;
    if (!tuning) return { ok: false, text: 'Take a first step with a parameter optimizer selected, so there is a result to save.' };
    if (!grid) return { ok: false, text: 'The run grid is still loading. Try again in a moment.' };
    if (tuning.score === null) return { ok: false, text: 'The goal is unreachable, so there is nothing to save.' };
    if (this.runs().some(saved => saved.runId === run.run_id)) return { ok: false, text: 'This run is already saved.' };
    const goal = run.observation.goal;
    const params = tuning.params;
    const record: SavedRun = {
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
      runId: run.run_id, savedAt: new Date().toISOString(),
      grid: { key: fingerprint(grid, run.start, goal), width: grid.width, height: grid.height, start: run.start, goal },
      importances: { cost: params['cost_weight'], time: params['time_weight'], memory: params['memory_weight'] },
      optimizer: tuning.optimizer, optimizerLabel: tuning.label,
      heuristic: tuning.heuristic, weight: tuning.weight, score: tuning.score,
      startHeuristic: config.heuristic, startWeight: config.weight, locked: params['lock_heuristic'] === 1,
      params: { ...params }, best: tuning.best, reference: tuning.reference, trials: tuning.trials,
    };
    this.runs.update(runs => [...runs, record]);
    this.persist();
    return { ok: true, text: `Saved under ${this.groups().find(group => group.key === record.grid.key)?.name}.` };
  }

  remove(id: string) {
    this.runs.update(runs => runs.filter(run => run.id !== id));
    this.persist();
  }

  rename(key: string, name: string) {
    const { [key]: _previous, ...others } = this.names();
    this.names.set(name.trim() ? { ...others, [key]: name.trim() } : others);
    this.persist();
  }

  load(run: SavedRun) { this.pendingLoad.set(run); }

  exportCsv() {
    const names = new Map(this.groups().map(group => [group.key, group.name]));
    const cell = (value: unknown) => {
      const text = value === null || value === undefined ? '' : String(value);
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    const header = ['grid', 'start', 'goal', 'cost_importance', 'time_importance', 'memory_importance', 'optimizer',
      'search_parameters', 'saved_at', 'heuristic', 'weight', 'found', 'cost', 'time_ms', 'memory_kb', 'expanded', 'score', 'best'];
    const rows = [...this.runs()].sort((a, b) => a.savedAt.localeCompare(b.savedAt)).flatMap(run => {
      const search = Object.entries(run.params)
        .filter(([id]) => !id.endsWith('_weight') || id.startsWith('weight_')).map(([id, value]) => `${id}=${value}`).join(' ');
      return run.trials.map(trial => [
        names.get(run.grid.key), `${run.grid.start.x};${run.grid.start.y}`, `${run.grid.goal.x};${run.grid.goal.y}`,
        run.importances.cost, run.importances.time, run.importances.memory, run.optimizer, search, run.savedAt,
        trial.heuristic, trial.weight, trial.found, trial.cost, trial.time_ms, trial.memory_kb, trial.expanded, trial.score,
        trial.heuristic === run.heuristic && trial.weight === run.weight ? 1 : 0,
      ].map(cell).join(','));
    });
    const blob = new Blob(['﻿' + [header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'saved-experiments.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  private read(): { runs: SavedRun[]; names: Record<string, string> } {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');
      if (Array.isArray(saved?.runs)) return { runs: saved.runs, names: saved.names ?? {} };
    } catch { /* Storage can be blocked or hold unreadable data; start empty. */ }
    return { runs: [], names: {} };
  }

  private persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ runs: this.runs(), names: this.names() }));
      this.storageError.set('');
    } catch {
      this.storageError.set('Could not save to this browser. Your experiments stay available until you reload the page.');
    }
  }
}
