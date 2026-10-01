import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';

export type CellType = 'empty' | 'obstacle';
export interface GridRender {
  width: number;
  height: number;
  cells: CellType[][];
  weights: (number | null)[][];
}

@Injectable({ providedIn: 'root' })
export class EnvironmentApi {
  private readonly http = inject(HttpClient);
  private readonly url = '/api/environment';

  render() {
    return this.http.get<GridRender>(`${this.url}/grid/render`);
  }

  placeObstacle(x: number, y: number) {
    return this.http.post<{ x: number; y: number }>(`${this.url}/grid/obstacles/${x}/${y}`, {});
  }

  reset() {
    return this.http.post<GridRender>(`${this.url}/grid/reset`, {});
  }

  resize(size: number) {
    return this.http.post<GridRender>(`${this.url}/grid/resize`, { size });
  }

  setWeight(x: number, y: number, weight: number) {
    return this.http.post<GridRender>(`${this.url}/grid/weights/${x}/${y}`, { weight });
  }

  setAllWeights(weight: number) {
    return this.http.post<GridRender>(`${this.url}/grid/weights`, { weight });
  }

  paintWeights(cells: { x: number; y: number }[], weight: number) {
    return this.http.post<GridRender>(`${this.url}/grid/weights/stroke`, { cells, weight });
  }

  paintObstacles(cells: { x: number; y: number }[], obstacle: boolean) {
    return this.http.post<GridRender>(`${this.url}/grid/obstacles/stroke`, { cells, obstacle });
  }

  resetWeights() {
    return this.http.post<GridRender>(`${this.url}/grid/weights/reset`, {});
  }

  removeObstacle(x: number, y: number) {
    return this.http.delete<{ x: number; y: number }>(`${this.url}/grid/obstacles/${x}/${y}`);
  }
}
