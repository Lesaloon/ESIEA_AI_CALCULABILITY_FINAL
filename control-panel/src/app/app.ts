import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { AgentPanel } from './agent/agent-panel';
import { EnvironmentPanel } from './environment/environment-panel';
import { ExperimentsPanel } from './experiments/experiments-panel';

type WorkspaceTab = 'environment' | 'agent' | 'experiments';

const TABS: WorkspaceTab[] = ['environment', 'agent', 'experiments'];

@Component({
  selector: 'app-root',
  imports: [EnvironmentPanel, AgentPanel, ExperimentsPanel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly activeTab = signal<WorkspaceTab>('environment');

  navigateTabs(event: KeyboardEvent) {
    const index = TABS.indexOf(this.activeTab());
    let tab: WorkspaceTab;
    switch (event.key) {
      case 'ArrowLeft':
        tab = TABS[(index + TABS.length - 1) % TABS.length];
        break;
      case 'ArrowRight':
        tab = TABS[(index + 1) % TABS.length];
        break;
      case 'Home':
        tab = TABS[0];
        break;
      case 'End':
        tab = TABS[TABS.length - 1];
        break;
      default:
        return;
    }
    event.preventDefault();
    this.activeTab.set(tab);
    const tabList = event.currentTarget as HTMLElement;
    tabList.querySelector<HTMLButtonElement>(`#${tab}-tab`)?.focus();
  }
}
