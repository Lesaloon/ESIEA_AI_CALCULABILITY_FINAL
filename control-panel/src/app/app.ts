import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { AgentPanel } from './agent/agent-panel';
import { EnvironmentPanel } from './environment/environment-panel';
import { ExperimentsPanel } from './experiments/experiments-panel';

type WorkspaceTab = 'environment' | 'agent' | 'experiments';

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
    const tabs: WorkspaceTab[] = ['environment', 'agent', 'experiments'];
    let tab: WorkspaceTab;
    switch (event.key) {
      case 'ArrowLeft':
      case 'ArrowRight':
        tab = tabs[(tabs.indexOf(this.activeTab()) + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
        break;
      case 'Home':
        tab = 'environment';
        break;
      case 'End':
        tab = 'experiments';
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
