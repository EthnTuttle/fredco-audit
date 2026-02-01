/**
 * ChartEngine - Chart.js wrapper for data visualization
 * 
 * Provides unified interface for creating charts from query results.
 * Supports bar, line, pie, scatter chart types with theme support.
 */

import { Chart, registerables, ChartConfiguration, ChartType as ChartJsType } from 'chart.js';
import type { QueryResult } from './data';

// Register all Chart.js components
Chart.register(...registerables);

/**
 * Supported chart types
 */
export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'doughnut' | 'radar' | 'polarArea';

/**
 * Chart options configuration
 */
export interface ChartOptions {
  title?: string;
  xAxisLabel?: string;
  yAxisLabel?: string;
  showLegend?: boolean;
  stacked?: boolean;
  beginAtZero?: boolean;
  colors?: string[];
  horizontal?: boolean;
}

/**
 * Default color palette (dark theme friendly)
 */
const DEFAULT_COLORS = [
  '#e94560', // Accent red
  '#00d9ff', // Cyan
  '#ffd700', // Gold
  '#00ff88', // Green
  '#ff6b6b', // Light red
  '#4ecdc4', // Teal
  '#a855f7', // Purple
  '#f97316', // Orange
  '#06b6d4', // Sky
  '#84cc16', // Lime
];

/**
 * ChartEngine class for managing Chart.js visualizations
 */
export class ChartEngine {
  private chartInstances: Map<string, Chart> = new Map();
  private colors: string[] = DEFAULT_COLORS;

  /**
   * Get color for dataset index
   */
  private getColor(index: number): string {
    return this.colors[index % this.colors.length];
  }

  /**
   * Get all colors for multiple data points (e.g., pie chart)
   */
  private getColors(count: number): string[] {
    return Array.from({ length: count }, (_, i) => this.getColor(i));
  }

  /**
   * Render a chart from query results
   * 
   * @param containerId - DOM element ID to render into
   * @param type - Chart type (bar, line, pie, scatter)
   * @param data - Query result from DuckDB
   * @param options - Optional chart configuration
   */
  renderChart(
    containerId: string,
    type: ChartType,
    data: QueryResult,
    options?: ChartOptions
  ): void {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error(`[ChartEngine] Container not found: ${containerId}`);
      return;
    }

    // Validate data
    if (data.columns.length < 2) {
      console.error('[ChartEngine] Query result needs at least 2 columns (labels and values)');
      container.innerHTML = '<div style="color: var(--accent); padding: 1rem;">Chart requires at least 2 columns (labels and values)</div>';
      return;
    }

    if (data.rows.length === 0) {
      console.error('[ChartEngine] Query result has no rows');
      container.innerHTML = '<div style="color: var(--text-secondary); padding: 1rem;">No data to display</div>';
      return;
    }

    // Destroy existing chart
    this.destroyChart(containerId);

    // Clear container and create canvas
    container.innerHTML = '';
    const canvas = document.createElement('canvas');
    canvas.id = `chart-canvas-${containerId}`;
    container.appendChild(canvas);

    // Convert query result to chart data
    const chartData = this.convertQueryResultToChartData(type, data, options);

    // Create chart configuration
    const config = this.createChartConfig(type, chartData, options);

    // Create chart
    const chart = new Chart(canvas, config);
    this.chartInstances.set(containerId, chart);

    console.log(`[ChartEngine] Rendered ${type} chart in ${containerId}`);
  }

  /**
   * Convert QueryResult to Chart.js data format
   */
  private convertQueryResultToChartData(
    type: ChartType,
    data: QueryResult,
    options?: ChartOptions
  ): { labels: string[]; datasets: Chart['data']['datasets'] } {
    const valueColumns = data.columns.slice(1);

    // Extract labels from first column
    const labels = data.rows.map(row => String(row[0] ?? ''));

    // Handle scatter chart differently (needs x,y pairs)
    if (type === 'scatter') {
      if (data.columns.length < 2) {
        return { labels: [], datasets: [] };
      }
      
      const points = data.rows.map(row => ({
        x: Number(row[0]) || 0,
        y: Number(row[1]) || 0,
      }));

      return {
        labels: [],
        datasets: [{
          label: options?.title || `${data.columns[0]} vs ${data.columns[1]}`,
          data: points,
          backgroundColor: this.getColor(0),
          borderColor: this.getColor(0),
        }],
      };
    }

    // Handle pie/doughnut (single dataset)
    if (type === 'pie' || type === 'doughnut' || type === 'polarArea') {
      const values = data.rows.map(row => Number(row[1]) || 0);
      return {
        labels,
        datasets: [{
          label: valueColumns[0] || 'Value',
          data: values,
          backgroundColor: this.getColors(labels.length),
          borderColor: 'rgba(0,0,0,0.1)',
          borderWidth: 1,
        }],
      };
    }

    // Handle bar/line/radar (can have multiple datasets)
    const datasets = valueColumns.map((col, i) => {
      const values = data.rows.map(row => Number(row[i + 1]) || 0);
      const color = options?.colors?.[i] || this.getColor(i);
      
      return {
        label: col,
        data: values,
        backgroundColor: type === 'line' ? 'transparent' : color,
        borderColor: color,
        borderWidth: 2,
        fill: type === 'line' ? false : undefined,
        tension: type === 'line' ? 0.1 : undefined,
      };
    });

    return { labels, datasets };
  }

  /**
   * Create Chart.js configuration object
   */
  private createChartConfig(
    type: ChartType,
    data: { labels: string[]; datasets: Chart['data']['datasets'] },
    options?: ChartOptions
  ): ChartConfiguration {
    const isPolar = ['pie', 'doughnut', 'radar', 'polarArea'].includes(type);

    return {
      type: type as ChartJsType,
      data: {
        labels: data.labels,
        datasets: data.datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: options?.horizontal ? 'y' : 'x',
        plugins: {
          title: {
            display: !!options?.title,
            text: options?.title || '',
            color: '#eee',
            font: { size: 14, weight: 'bold' },
          },
          legend: {
            display: options?.showLegend ?? true,
            position: 'top',
            labels: {
              color: '#aaa',
              padding: 10,
            },
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            titleColor: '#fff',
            bodyColor: '#ddd',
            padding: 10,
            cornerRadius: 4,
          },
        },
        scales: isPolar ? {} : {
          x: {
            display: true,
            title: {
              display: !!options?.xAxisLabel,
              text: options?.xAxisLabel || '',
              color: '#aaa',
            },
            ticks: { color: '#888' },
            grid: { color: 'rgba(255,255,255,0.1)' },
            stacked: options?.stacked ?? false,
          },
          y: {
            display: true,
            title: {
              display: !!options?.yAxisLabel,
              text: options?.yAxisLabel || '',
              color: '#aaa',
            },
            ticks: { color: '#888' },
            grid: { color: 'rgba(255,255,255,0.1)' },
            stacked: options?.stacked ?? false,
            beginAtZero: options?.beginAtZero ?? true,
          },
        },
      },
    };
  }

  /**
   * Destroy a chart by container ID
   */
  destroyChart(containerId: string): void {
    const chart = this.chartInstances.get(containerId);
    if (chart) {
      chart.destroy();
      this.chartInstances.delete(containerId);
      console.log(`[ChartEngine] Destroyed chart: ${containerId}`);
    }
  }

  /**
   * Update an existing chart with new data
   */
  updateChart(containerId: string, data: QueryResult): void {
    const chart = this.chartInstances.get(containerId);
    if (!chart) {
      console.error(`[ChartEngine] Chart not found: ${containerId}`);
      return;
    }

    // Get current chart type from the chart configuration
    const chartConfig = chart.config as ChartConfiguration;
    const type = chartConfig.type as ChartType;
    
    // Convert new data
    const chartData = this.convertQueryResultToChartData(type, data);

    // Update chart data
    chart.data.labels = chartData.labels;
    chart.data.datasets = chartData.datasets;
    chart.update('active');

    console.log(`[ChartEngine] Updated chart: ${containerId}`);
  }

  /**
   * Export chart as PNG data URL
   */
  exportAsPng(containerId: string): string | null {
    const chart = this.chartInstances.get(containerId);
    if (!chart) {
      console.error(`[ChartEngine] Chart not found: ${containerId}`);
      return null;
    }
    return chart.toBase64Image('image/png', 1.0);
  }

  /**
   * Download chart as PNG
   */
  downloadAsPng(containerId: string, filename?: string): void {
    const dataUrl = this.exportAsPng(containerId);
    if (!dataUrl) return;

    const link = document.createElement('a');
    link.download = filename || `chart-${containerId}.png`;
    link.href = dataUrl;
    link.click();

    console.log(`[ChartEngine] Downloaded chart: ${containerId}`);
  }

  /**
   * Get chart instance
   */
  getChart(containerId: string): Chart | undefined {
    return this.chartInstances.get(containerId);
  }

  /**
   * Destroy all charts
   */
  destroyAll(): void {
    this.chartInstances.forEach((chart, id) => {
      chart.destroy();
      console.log(`[ChartEngine] Destroyed chart: ${id}`);
    });
    this.chartInstances.clear();
  }

  /**
   * Set custom color palette
   */
  setColors(colors: string[]): void {
    this.colors = colors;
  }

  /**
   * Reset to default colors
   */
  resetColors(): void {
    this.colors = DEFAULT_COLORS;
  }
}

// Singleton instance for easy access
let chartEngineInstance: ChartEngine | null = null;

/**
 * Get the singleton ChartEngine instance
 */
export function getChartEngine(): ChartEngine {
  if (!chartEngineInstance) {
    chartEngineInstance = new ChartEngine();
  }
  return chartEngineInstance;
}

// Re-export for backward compatibility with existing code
export const renderChart = (containerId: string, config: {
  id: string;
  type: ChartType;
  labels: string[];
  datasets: {
    label: string;
    data: number[] | { x: number; y: number }[];
    backgroundColor?: string | string[];
    borderColor?: string | string[];
    borderWidth?: number;
    fill?: boolean;
    tension?: number;
  }[];
  title?: string;
  xAxisLabel?: string;
  yAxisLabel?: string;
  showLegend?: boolean;
  stacked?: boolean;
}) => {
  const engine = getChartEngine();
  
  // Convert to QueryResult-like format
  const mockResult: QueryResult = {
    columns: ['label', ...config.datasets.map(d => d.label)],
    rows: config.labels.map((label, i) => {
      const row: unknown[] = [label];
      config.datasets.forEach(ds => {
        const data = ds.data[i];
        row.push(typeof data === 'number' ? data : (data as { y: number }).y);
      });
      return row;
    }),
    rowCount: config.labels.length,
    executionTimeMs: 0,
  };

  engine.renderChart(containerId, config.type, mockResult, {
    title: config.title,
    xAxisLabel: config.xAxisLabel,
    yAxisLabel: config.yAxisLabel,
    showLegend: config.showLegend,
    stacked: config.stacked,
  });

  return engine.getChart(containerId) ?? null;
};

export const destroyChart = (id: string) => getChartEngine().destroyChart(id);
export const destroyAllCharts = () => getChartEngine().destroyAll();
export const exportChartAsPng = (id: string) => getChartEngine().exportAsPng(id);
export const getChart = (id: string) => getChartEngine().getChart(id);
export const updateChartData = (id: string, labels: string[], datasets: { label: string; data: number[] }[]) => {
  const mockResult: QueryResult = {
    columns: ['label', ...datasets.map(d => d.label)],
    rows: labels.map((label, i) => {
      const row: unknown[] = [label];
      datasets.forEach(ds => row.push(ds.data[i]));
      return row;
    }),
    rowCount: labels.length,
    executionTimeMs: 0,
  };
  getChartEngine().updateChart(id, mockResult);
};
