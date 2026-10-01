import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-agent-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-panel.html',
  styleUrl: './agent-panel.css',
})
export class AgentPanel {}
