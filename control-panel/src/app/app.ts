import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { AgentPanel } from './agent/agent-panel';
import { EnvironmentPanel } from './environment/environment-panel';

type WorkspaceTab = 'environment' | 'agent';

@Component({
  selector: 'app-root',
  imports: [EnvironmentPanel, AgentPanel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly activeTab = signal<WorkspaceTab>('environment');

  navigateTabs(event: KeyboardEvent) {
    let tab: WorkspaceTab;
    switch (event.key) {
      case 'ArrowLeft':
      case 'ArrowRight':
        tab = this.activeTab() === 'environment' ? 'agent' : 'environment';
        break;
      case 'Home':
        tab = 'environment';
        break;
      case 'End':
        tab = 'agent';
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
