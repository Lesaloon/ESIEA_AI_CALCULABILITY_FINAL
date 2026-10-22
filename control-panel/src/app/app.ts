import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { AgentPanel } from './agent/agent-panel';
import { EnvironmentPanel } from './environment/environment-panel';
import { GlobalSearchPanel } from './global-search/global-search-panel';

type WorkspaceTab = 'environment' | 'agent' | 'global';

@Component({
  selector: 'app-root',
  imports: [EnvironmentPanel, AgentPanel, GlobalSearchPanel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly activeTab = signal<WorkspaceTab>('environment');

  navigateTabs(event: KeyboardEvent) {
    const tabs: WorkspaceTab[] = ['environment', 'agent', 'global'];
    const index = tabs.indexOf(this.activeTab());
    let tab: WorkspaceTab;
    switch (event.key) {
      case 'ArrowRight':
        tab = tabs[(index + 1) % tabs.length];
        break;
      case 'ArrowLeft':
        tab = tabs[(index - 1 + tabs.length) % tabs.length];
        break;
      case 'Home':
        tab = 'environment';
        break;
      case 'End':
        tab = 'global';
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
