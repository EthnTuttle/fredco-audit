/**
 * ChartEngine - Chart.js wrapper for data visualization
 * 
 * Provides unified interface for creating charts from query results.
 */

import { Chart, registerables } from 'chart.js';

// Register all Chart.js components
Chart.register(...registerables);

// Chart instances cache
const chartInstances: Map<string, Chart> = new Map();

/**
 * Chart type enumeration
 */
export type ChartType = 
  | 'bar' 
  | 'line' 
  | 'pie' 
  | 'doughnut' 
  | 'scatter' 
  | 'bubble'
  | 'radar'
  | 'polarArea';

/**
 * Dataset configuration
 */
export interface Dataset {
  label: string;
  data: number[] | { x: number; y: number }[];
  backgroundColor?: string | string[];
  borderColor?: string | string[];
  borderWidth?: number;
  fill?: boolean;
  tension?: number;
}

/**
 * Chart configuration
 */
export interface ChartConfig {
  id: string;
  type: ChartType;
  labels: string[];
  datasets: Dataset[];
  title?: string;
  xAxisLabel?: string;
  yAxisLabel?: string;
  showLegend?: boolean;
  stacked?: boolean;
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
 * Get color for dataset index
 */
function getColor(index: number): string {
  return DEFAULT_COLORS[index % DEFAULT_COLORS.length];
}

/**
 * Create or update a chart
 */
export function renderChart(
  containerId: string,
  config: ChartConfig
): Chart | null {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`[ChartEngine] Container not found: ${containerId}`);
    return null;
  }

  // Clear existing content
  container.innerHTML = '';

  // Create canvas
  const canvas = document.createElement('canvas');
  canvas.id = `chart-canvas-${config.id}`;
  container.appendChild(canvas);

  // Destroy existing chart if any
  const existingChart = chartInstances.get(config.id);
  if (existingChart) {
    existingChart.destroy();
    chartInstances.delete(config.id);
  }

  // Apply default colors if not specified
  const datasets = config.datasets.map((ds, i) => ({
    ...ds,
    backgroundColor: ds.backgroundColor ?? getColor(i),
    borderColor: ds.borderColor ?? getColor(i),
    borderWidth: ds.borderWidth ?? 2,
  }));

  // Create chart
  const chart = new Chart(canvas, {
    type: config.type,
    data: {
      labels: config.labels,
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: !!config.title,
          text: config.title ?? '',
          color: '#eee',
          font: { size: 14 },
        },
        legend: {
          display: config.showLegend ?? true,
          position: 'top',
          labels: {
            color: '#aaa',
          },
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#fff',
          bodyColor: '#ddd',
        },
      },
      scales: getScalesConfig(config),
    },
  });

  chartInstances.set(config.id, chart);
  console.log(`[ChartEngine] Rendered chart: ${config.id}`);
  
  return chart;
}

/**
 * Get scales configuration based on chart type
 */
function getScalesConfig(config: ChartConfig): object {
  // Pie/doughnut/radar don't use cartesian scales
  if (['pie', 'doughnut', 'radar', 'polarArea'].includes(config.type)) {
    return {};
  }

  return {
    x: {
      display: true,
      title: {
        display: !!config.xAxisLabel,
        text: config.xAxisLabel ?? '',
        color: '#aaa',
      },
      ticks: { color: '#888' },
      grid: { color: 'rgba(255,255,255,0.1)' },
      stacked: config.stacked ?? false,
    },
    y: {
      display: true,
      title: {
        display: !!config.yAxisLabel,
        text: config.yAxisLabel ?? '',
        color: '#aaa',
      },
      ticks: { color: '#888' },
      grid: { color: 'rgba(255,255,255,0.1)' },
      stacked: config.stacked ?? false,
      beginAtZero: true,
    },
  };
}

/**
 * Create a bar chart from query results
 */
export function createBarChart(
  containerId: string,
  options: {
    id: string;
    labels: string[];
    values: number[];
    label?: string;
    title?: string;
    horizontal?: boolean;
  }
): Chart | null {
  return renderChart(containerId, {
    id: options.id,
    type: options.horizontal ? 'bar' : 'bar', // Chart.js uses indexAxis for horizontal
    labels: options.labels,
    datasets: [{
      label: options.label ?? 'Value',
      data: options.values,
    }],
    title: options.title,
  });
}

/**
 * Create a line chart from query results
 */
export function createLineChart(
  containerId: string,
  options: {
    id: string;
    labels: string[];
    datasets: { label: string; values: number[] }[];
    title?: string;
    xAxisLabel?: string;
    yAxisLabel?: string;
  }
): Chart | null {
  return renderChart(containerId, {
    id: options.id,
    type: 'line',
    labels: options.labels,
    datasets: options.datasets.map(ds => ({
      label: ds.label,
      data: ds.values,
      fill: false,
      tension: 0.1,
    })),
    title: options.title,
    xAxisLabel: options.xAxisLabel,
    yAxisLabel: options.yAxisLabel,
  });
}

/**
 * Create a pie chart from query results
 */
export function createPieChart(
  containerId: string,
  options: {
    id: string;
    labels: string[];
    values: number[];
    title?: string;
    doughnut?: boolean;
  }
): Chart | null {
  return renderChart(containerId, {
    id: options.id,
    type: options.doughnut ? 'doughnut' : 'pie',
    labels: options.labels,
    datasets: [{
      label: 'Value',
      data: options.values,
      backgroundColor: options.labels.map((_, i) => getColor(i)),
    }],
    title: options.title,
    showLegend: true,
  });
}

/**
 * Create a scatter plot from query results
 */
export function createScatterChart(
  containerId: string,
  options: {
    id: string;
    points: { x: number; y: number }[];
    label?: string;
    title?: string;
    xAxisLabel?: string;
    yAxisLabel?: string;
  }
): Chart | null {
  return renderChart(containerId, {
    id: options.id,
    type: 'scatter',
    labels: [],
    datasets: [{
      label: options.label ?? 'Data',
      data: options.points,
    }],
    title: options.title,
    xAxisLabel: options.xAxisLabel,
    yAxisLabel: options.yAxisLabel,
  });
}

/**
 * Destroy a chart by ID
 */
export function destroyChart(id: string): void {
  const chart = chartInstances.get(id);
  if (chart) {
    chart.destroy();
    chartInstances.delete(id);
    console.log(`[ChartEngine] Destroyed chart: ${id}`);
  }
}

/**
 * Destroy all charts
 */
export function destroyAllCharts(): void {
  chartInstances.forEach((chart, id) => {
    chart.destroy();
    console.log(`[ChartEngine] Destroyed chart: ${id}`);
  });
  chartInstances.clear();
}

/**
 * Export chart as PNG data URL
 */
export function exportChartAsPng(id: string): string | null {
  const chart = chartInstances.get(id);
  if (!chart) {
    console.error(`[ChartEngine] Chart not found: ${id}`);
    return null;
  }
  return chart.toBase64Image('image/png', 1.0);
}

/**
 * Get chart instance by ID
 */
export function getChart(id: string): Chart | undefined {
  return chartInstances.get(id);
}

/**
 * Update chart data
 */
export function updateChartData(
  id: string,
  labels: string[],
  datasets: { label: string; data: number[] }[]
): void {
  const chart = chartInstances.get(id);
  if (!chart) {
    console.error(`[ChartEngine] Chart not found: ${id}`);
    return;
  }

  chart.data.labels = labels;
  chart.data.datasets = datasets.map((ds, i) => ({
    ...ds,
    backgroundColor: getColor(i),
    borderColor: getColor(i),
  }));
  chart.update();
  console.log(`[ChartEngine] Updated chart: ${id}`);
}
