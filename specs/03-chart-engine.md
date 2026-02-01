# ChartEngine Component Specification

**Component**: ChartEngine  
**Version**: 1.0.0  
**Status**: Draft  
**Last Updated**: 2026-01-31

---

## 1. Purpose and Responsibilities

The ChartEngine is a Leptos component responsible for rendering all visualizations in the FCPS Audit application. It provides a unified interface for creating charts, maps, and exportable graphics.

### Core Responsibilities

1. **Chart Rendering**: Render all chart types using Chart.js via JavaScript interop
2. **Map Rendering**: Render choropleth maps using Leaflet for geographic/district-level data
3. **Data Integration**: Accept and transform DataEngine query results into chart-ready formats
4. **Export**: Generate PNG and SVG exports of any visualization
5. **Theming**: Support light and dark themes with consistent styling
6. **Responsiveness**: Ensure all charts adapt to container dimensions

### Non-Responsibilities

- Data fetching (handled by DataEngine)
- Data analysis/calculations (handled by DataEngine)
- Layout/positioning of multiple charts (handled by parent components)

---

## 2. Rust Type Definitions

### 2.1 Core Configuration Types

```rust
use serde::{Deserialize, Serialize};
use tsify::Tsify;

/// Main chart configuration passed to ChartEngine
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChartConfig {
    /// Unique identifier for the chart instance
    pub id: String,
    /// Type of chart to render
    pub chart_type: ChartType,
    /// Data to visualize
    pub data: ChartData,
    /// Display options
    pub options: ChartOptions,
    /// Export settings (optional)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub export: Option<ExportConfig>,
}

/// Supported chart types
#[derive(Debug, Clone, Serialize, Deserialize, Tsify, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "snake_case")]
pub enum ChartType {
    // Basic
    Bar,
    Line,
    Pie,
    Doughnut,
    // Statistical
    Scatter,
    Bubble,
    Histogram,
    // Time-based
    Area,
    Timeline,
    // Comparison
    Radar,
    Polar,
    // Hierarchical
    Treemap,
    Sunburst,
    // Geographic
    Choropleth,
}

/// Chart data structure
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChartData {
    /// Labels for data points (x-axis for most charts)
    pub labels: Vec<String>,
    /// Data series
    pub datasets: Vec<Dataset>,
}

/// Individual data series
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Dataset {
    /// Display name for the series
    pub label: String,
    /// Data values
    pub data: DataValues,
    /// Series-specific styling
    #[serde(skip_serializing_if = "Option::is_none")]
    pub style: Option<DatasetStyle>,
}

/// Data value variants for different chart types
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(untagged)]
pub enum DataValues {
    /// Simple numeric values (bar, line, pie, etc.)
    Numbers(Vec<f64>),
    /// Point data for scatter plots
    Points(Vec<Point2D>),
    /// Bubble data with radius
    Bubbles(Vec<BubblePoint>),
    /// Hierarchical data for treemap/sunburst
    Hierarchical(Vec<HierarchyNode>),
    /// Geographic data for choropleth
    Geographic(Vec<GeoDataPoint>),
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Point2D {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct BubblePoint {
    pub x: f64,
    pub y: f64,
    /// Radius of the bubble
    pub r: f64,
    /// Optional label for the bubble
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct HierarchyNode {
    pub id: String,
    pub label: String,
    pub value: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parent: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub color: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct GeoDataPoint {
    /// Division code (e.g., "069" for Frederick County)
    pub division_code: String,
    /// Display name
    pub name: String,
    /// Value for color scaling
    pub value: f64,
    /// Optional tooltip content
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tooltip: Option<String>,
}
```

### 2.2 Styling Types

```rust
/// Dataset-specific styling
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct DatasetStyle {
    /// Background color(s) - single or array for each data point
    #[serde(skip_serializing_if = "Option::is_none")]
    pub background_color: Option<ColorValue>,
    /// Border color(s)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub border_color: Option<ColorValue>,
    /// Border width in pixels
    #[serde(skip_serializing_if = "Option::is_none")]
    pub border_width: Option<f64>,
    /// Fill area under line (for line/area charts)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fill: Option<bool>,
    /// Line tension for curves (0 = straight lines)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tension: Option<f64>,
    /// Point radius for line/scatter charts
    #[serde(skip_serializing_if = "Option::is_none")]
    pub point_radius: Option<f64>,
}

/// Color value - single or multiple
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(untagged)]
pub enum ColorValue {
    Single(String),
    Multiple(Vec<String>),
}

/// Theme configuration
#[derive(Debug, Clone, Serialize, Deserialize, Tsify, Default)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Theme {
    pub mode: ThemeMode,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub colors: Option<ThemeColors>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify, Default, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "snake_case")]
pub enum ThemeMode {
    #[default]
    Light,
    Dark,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ThemeColors {
    /// Primary color palette for data series
    pub primary: Vec<String>,
    /// Background color
    pub background: String,
    /// Text color
    pub text: String,
    /// Grid line color
    pub grid: String,
    /// Border color
    pub border: String,
}
```

### 2.3 Chart Options

```rust
/// Display and behavior options
#[derive(Debug, Clone, Serialize, Deserialize, Tsify, Default)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChartOptions {
    /// Chart title
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<TitleConfig>,
    /// Legend configuration
    #[serde(skip_serializing_if = "Option::is_none")]
    pub legend: Option<LegendConfig>,
    /// Tooltip configuration
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tooltip: Option<TooltipConfig>,
    /// Axis configurations
    #[serde(skip_serializing_if = "Option::is_none")]
    pub axes: Option<AxesConfig>,
    /// Enable animations
    #[serde(default = "default_true")]
    pub animated: bool,
    /// Enable responsive resizing
    #[serde(default = "default_true")]
    pub responsive: bool,
    /// Maintain aspect ratio on resize
    #[serde(default = "default_true")]
    pub maintain_aspect_ratio: bool,
    /// Aspect ratio (width/height)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub aspect_ratio: Option<f64>,
    /// Theme settings
    #[serde(default)]
    pub theme: Theme,
}

fn default_true() -> bool { true }

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct TitleConfig {
    pub text: String,
    #[serde(default = "default_true")]
    pub display: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub position: Option<Position>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub font_size: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct LegendConfig {
    #[serde(default = "default_true")]
    pub display: bool,
    #[serde(default)]
    pub position: Position,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify, Default)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "snake_case")]
pub enum Position {
    #[default]
    Top,
    Bottom,
    Left,
    Right,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct TooltipConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    /// Format string for values (e.g., "${value:,.0f}" for currency)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value_format: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct AxesConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub x: Option<AxisConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub y: Option<AxisConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct AxisConfig {
    /// Axis label
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    /// Minimum value (auto if not set)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min: Option<f64>,
    /// Maximum value (auto if not set)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max: Option<f64>,
    /// Start axis at zero
    #[serde(default)]
    pub begin_at_zero: bool,
    /// Show grid lines
    #[serde(default = "default_true")]
    pub grid: bool,
    /// Value format string
    #[serde(skip_serializing_if = "Option::is_none")]
    pub format: Option<String>,
    /// Axis type
    #[serde(default)]
    pub axis_type: AxisType,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify, Default)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "snake_case")]
pub enum AxisType {
    #[default]
    Linear,
    Logarithmic,
    Category,
    Time,
}
```

### 2.4 Export Configuration

```rust
/// Export configuration
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ExportConfig {
    /// Enable export functionality
    #[serde(default = "default_true")]
    pub enabled: bool,
    /// Allowed export formats
    #[serde(default = "default_export_formats")]
    pub formats: Vec<ExportFormat>,
    /// Default filename (without extension)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filename: Option<String>,
    /// Export dimensions
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimensions: Option<ExportDimensions>,
}

fn default_export_formats() -> Vec<ExportFormat> {
    vec![ExportFormat::Png, ExportFormat::Svg]
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "snake_case")]
pub enum ExportFormat {
    Png,
    Svg,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ExportDimensions {
    pub width: u32,
    pub height: u32,
    /// Scale factor for high-DPI exports
    #[serde(default = "default_scale")]
    pub scale: f64,
}

fn default_scale() -> f64 { 2.0 }
```

### 2.5 Choropleth-Specific Configuration

```rust
/// Choropleth map configuration
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChoroplethConfig {
    /// GeoJSON source for boundaries
    pub geo_source: GeoSource,
    /// Property in GeoJSON to match with data
    pub geo_key: String,
    /// Color scale configuration
    pub color_scale: ColorScale,
    /// Map center [lat, lng]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub center: Option<[f64; 2]>,
    /// Initial zoom level
    #[serde(skip_serializing_if = "Option::is_none")]
    pub zoom: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "snake_case")]
pub enum GeoSource {
    /// Virginia school divisions
    VaSchoolDivisions,
    /// Custom GeoJSON URL
    Custom(String),
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ColorScale {
    /// Color scale type
    pub scale_type: ColorScaleType,
    /// Colors for the scale (low to high)
    pub colors: Vec<String>,
    /// Value range (auto-calculated if not set)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub domain: Option<[f64; 2]>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(rename_all = "snake_case")]
pub enum ColorScaleType {
    Sequential,
    Diverging,
    Quantile,
    Threshold,
}
```

---

## 3. Message Protocol

### 3.1 Input Messages (to ChartEngine)

```rust
/// Messages sent to ChartEngine
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type", content = "payload")]
pub enum ChartMessage {
    /// Render a new chart
    Render(ChartConfig),
    /// Update chart data without full re-render
    UpdateData { id: String, data: ChartData },
    /// Update chart options
    UpdateOptions { id: String, options: ChartOptions },
    /// Export chart to file
    Export { id: String, format: ExportFormat },
    /// Destroy chart instance
    Destroy { id: String },
    /// Resize chart
    Resize { id: String, width: u32, height: u32 },
    /// Set theme for all charts
    SetTheme(Theme),
}
```

### 3.2 Output Events (from ChartEngine)

```rust
/// Events emitted by ChartEngine
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type", content = "payload")]
pub enum ChartEvent {
    /// Chart successfully rendered
    Rendered { id: String },
    /// Chart data updated
    DataUpdated { id: String },
    /// Export completed
    Exported { id: String, format: ExportFormat, data_url: String },
    /// Export failed
    ExportFailed { id: String, error: String },
    /// User clicked on data point
    DataPointClicked { id: String, dataset_index: usize, data_index: usize, value: f64 },
    /// User hovered on data point
    DataPointHovered { id: String, dataset_index: usize, data_index: usize },
    /// Error occurred
    Error { id: String, message: String },
}
```

---

## 4. Chart Type Specifications

### 4.1 Basic Charts (Chart.js)

| Chart Type | Use Case | Data Format | Notes |
|------------|----------|-------------|-------|
| **Bar** | Categorical comparisons | `DataValues::Numbers` | Supports horizontal via options |
| **Line** | Trends over time | `DataValues::Numbers` | Supports multiple series |
| **Pie** | Part-to-whole (single series) | `DataValues::Numbers` | Max 7-8 segments recommended |
| **Doughnut** | Part-to-whole with center space | `DataValues::Numbers` | Good for percentages |

### 4.2 Statistical Charts (Chart.js)

| Chart Type | Use Case | Data Format | Notes |
|------------|----------|-------------|-------|
| **Scatter** | Correlation analysis | `DataValues::Points` | X-Y coordinate pairs |
| **Bubble** | 3-variable comparison | `DataValues::Bubbles` | X, Y, and radius values |
| **Histogram** | Distribution analysis | `DataValues::Numbers` | Auto-binning available |

### 4.3 Time-Based Charts (Chart.js)

| Chart Type | Use Case | Data Format | Notes |
|------------|----------|-------------|-------|
| **Area** | Cumulative trends | `DataValues::Numbers` | Filled line chart |
| **Timeline** | Events over time | `DataValues::Points` | Time scale on X-axis |

### 4.4 Comparison Charts (Chart.js)

| Chart Type | Use Case | Data Format | Notes |
|------------|----------|-------------|-------|
| **Radar** | Multi-metric comparison | `DataValues::Numbers` | Good for peer comparison |
| **Polar** | Radial comparison | `DataValues::Numbers` | Circular bar chart |

### 4.5 Hierarchical Charts (Chart.js + Plugins)

| Chart Type | Use Case | Data Format | Notes |
|------------|----------|-------------|-------|
| **Treemap** | Budget breakdown | `DataValues::Hierarchical` | Requires chartjs-chart-treemap |
| **Sunburst** | Nested categories | `DataValues::Hierarchical` | Requires custom plugin |

### 4.6 Geographic Charts (Leaflet)

| Chart Type | Use Case | Data Format | Notes |
|------------|----------|-------------|-------|
| **Choropleth** | District comparisons | `DataValues::Geographic` | Virginia school divisions |

---

## 5. Export Functionality

### 5.1 PNG Export

```rust
/// Export chart to PNG
pub async fn export_png(chart_id: &str, config: ExportDimensions) -> Result<String, ExportError> {
    // 1. Get canvas element from Chart.js instance
    // 2. Apply scale factor for high-DPI
    // 3. Convert to data URL
    // 4. Return base64-encoded PNG
}
```

**Characteristics**:
- Raster format, suitable for web/documents
- Configurable dimensions and scale factor
- Includes chart background
- Default: 2x scale for retina displays

### 5.2 SVG Export

```rust
/// Export chart to SVG
pub async fn export_svg(chart_id: &str) -> Result<String, ExportError> {
    // 1. Serialize chart to SVG using canvas2svg
    // 2. Include embedded styles
    // 3. Return SVG string
}
```

**Characteristics**:
- Vector format, infinitely scalable
- Editable in vector graphics software
- Smaller file size for simple charts
- Requires canvas2svg library for Chart.js charts
- Leaflet maps use native SVG export

### 5.3 Export Error Handling

```rust
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum ExportError {
    ChartNotFound(String),
    CanvasNotAvailable,
    ExportFailed(String),
    UnsupportedFormat(String),
}
```

---

## 6. Component API

### 6.1 Leptos Component

```rust
use leptos::*;

/// ChartEngine component props
#[derive(Props, Clone)]
pub struct ChartEngineProps {
    /// Chart configuration
    pub config: ChartConfig,
    /// Optional CSS class
    #[prop(optional)]
    pub class: Option<String>,
    /// Callback when chart is rendered
    #[prop(optional)]
    pub on_rendered: Option<Callback<String>>,
    /// Callback when data point is clicked
    #[prop(optional)]
    pub on_click: Option<Callback<DataPointClick>>,
    /// Callback when export completes
    #[prop(optional)]
    pub on_export: Option<Callback<ExportResult>>,
}

#[derive(Clone)]
pub struct DataPointClick {
    pub dataset_index: usize,
    pub data_index: usize,
    pub value: f64,
    pub label: String,
}

#[derive(Clone)]
pub struct ExportResult {
    pub format: ExportFormat,
    pub data_url: String,
}

/// Main ChartEngine component
#[component]
pub fn ChartEngine(props: ChartEngineProps) -> impl IntoView {
    // Implementation
}
```

### 6.2 Imperative API

```rust
/// Handle to control a chart imperatively
pub struct ChartHandle {
    id: String,
}

impl ChartHandle {
    /// Update chart data
    pub fn update_data(&self, data: ChartData);
    
    /// Update chart options
    pub fn update_options(&self, options: ChartOptions);
    
    /// Export chart
    pub async fn export(&self, format: ExportFormat) -> Result<String, ExportError>;
    
    /// Destroy chart instance
    pub fn destroy(&self);
    
    /// Resize chart
    pub fn resize(&self, width: u32, height: u32);
}
```

---

## 7. Example Usage

### 7.1 Basic Bar Chart

```rust
use crate::components::chart_engine::*;

#[component]
fn PerPupilSpendingChart() -> impl IntoView {
    let config = ChartConfig {
        id: "per-pupil-spending".to_string(),
        chart_type: ChartType::Bar,
        data: ChartData {
            labels: vec![
                "Frederick".to_string(),
                "Clarke".to_string(),
                "Fauquier".to_string(),
                "Shenandoah".to_string(),
                "Warren".to_string(),
                "State Avg".to_string(),
            ],
            datasets: vec![Dataset {
                label: "Per-Pupil Spending (FY2024)".to_string(),
                data: DataValues::Numbers(vec![15734.0, 18234.0, 16892.0, 14567.0, 15123.0, 17636.0]),
                style: Some(DatasetStyle {
                    background_color: Some(ColorValue::Single("#3b82f6".to_string())),
                    border_color: Some(ColorValue::Single("#1d4ed8".to_string())),
                    border_width: Some(1.0),
                    ..Default::default()
                }),
            }],
        },
        options: ChartOptions {
            title: Some(TitleConfig {
                text: "Per-Pupil Expenditure Comparison".to_string(),
                display: true,
                position: Some(Position::Top),
                font_size: Some(16),
            }),
            axes: Some(AxesConfig {
                x: None,
                y: Some(AxisConfig {
                    label: Some("Dollars".to_string()),
                    begin_at_zero: false,
                    min: Some(12000.0),
                    format: Some("${value:,.0f}".to_string()),
                    ..Default::default()
                }),
            }),
            ..Default::default()
        },
        export: Some(ExportConfig {
            enabled: true,
            formats: vec![ExportFormat::Png, ExportFormat::Svg],
            filename: Some("per-pupil-spending-fy24".to_string()),
            ..Default::default()
        }),
    };

    view! {
        <ChartEngine
            config=config
            class="h-96"
            on_click=|click| log::info!("Clicked: {:?}", click)
        />
    }
}
```

### 7.2 Multi-Series Line Chart

```rust
#[component]
fn EnrollmentTrendChart() -> impl IntoView {
    let config = ChartConfig {
        id: "enrollment-trend".to_string(),
        chart_type: ChartType::Line,
        data: ChartData {
            labels: vec![
                "2019-20".to_string(),
                "2020-21".to_string(),
                "2021-22".to_string(),
                "2022-23".to_string(),
                "2023-24".to_string(),
            ],
            datasets: vec![
                Dataset {
                    label: "Frederick County".to_string(),
                    data: DataValues::Numbers(vec![13856.0, 13654.0, 13789.0, 14012.0, 14121.0]),
                    style: Some(DatasetStyle {
                        border_color: Some(ColorValue::Single("#3b82f6".to_string())),
                        tension: Some(0.3),
                        fill: Some(false),
                        ..Default::default()
                    }),
                },
                Dataset {
                    label: "Warren County".to_string(),
                    data: DataValues::Numbers(vec![6234.0, 6156.0, 6198.0, 6312.0, 6378.0]),
                    style: Some(DatasetStyle {
                        border_color: Some(ColorValue::Single("#10b981".to_string())),
                        tension: Some(0.3),
                        fill: Some(false),
                        ..Default::default()
                    }),
                },
            ],
        },
        options: ChartOptions {
            title: Some(TitleConfig {
                text: "Enrollment Trends (ADM)".to_string(),
                display: true,
                ..Default::default()
            }),
            ..Default::default()
        },
        export: None,
    };

    view! { <ChartEngine config=config /> }
}
```

### 7.3 Choropleth Map

```rust
#[component]
fn RegionalSpendingMap() -> impl IntoView {
    let config = ChartConfig {
        id: "regional-spending-map".to_string(),
        chart_type: ChartType::Choropleth,
        data: ChartData {
            labels: vec![],
            datasets: vec![Dataset {
                label: "Per-Pupil Spending".to_string(),
                data: DataValues::Geographic(vec![
                    GeoDataPoint {
                        division_code: "069".to_string(),
                        name: "Frederick County".to_string(),
                        value: 15734.0,
                        tooltip: Some("$15,734 per pupil".to_string()),
                    },
                    GeoDataPoint {
                        division_code: "043".to_string(),
                        name: "Clarke County".to_string(),
                        value: 18234.0,
                        tooltip: Some("$18,234 per pupil".to_string()),
                    },
                    // ... more divisions
                ]),
                style: None,
            }],
        },
        options: ChartOptions {
            title: Some(TitleConfig {
                text: "Regional Per-Pupil Spending (FY2024)".to_string(),
                display: true,
                ..Default::default()
            }),
            ..Default::default()
        },
        export: Some(ExportConfig {
            enabled: true,
            formats: vec![ExportFormat::Png],
            filename: Some("regional-spending-map".to_string()),
            dimensions: Some(ExportDimensions {
                width: 1200,
                height: 800,
                scale: 2.0,
            }),
        }),
    };

    view! { <ChartEngine config=config class="h-[600px]" /> }
}
```

### 7.4 Radar Chart for Peer Comparison

```rust
#[component]
fn PeerComparisonRadar() -> impl IntoView {
    let config = ChartConfig {
        id: "peer-comparison".to_string(),
        chart_type: ChartType::Radar,
        data: ChartData {
            labels: vec![
                "Per-Pupil Spending".to_string(),
                "Pupil-Teacher Ratio".to_string(),
                "Admin Ratio".to_string(),
                "Instruction %".to_string(),
                "Attendance Rate".to_string(),
            ],
            datasets: vec![
                Dataset {
                    label: "Frederick County".to_string(),
                    data: DataValues::Numbers(vec![0.89, 0.92, 0.95, 0.88, 0.94]),
                    style: Some(DatasetStyle {
                        background_color: Some(ColorValue::Single("rgba(59, 130, 246, 0.2)".to_string())),
                        border_color: Some(ColorValue::Single("#3b82f6".to_string())),
                        ..Default::default()
                    }),
                },
                Dataset {
                    label: "Peer Average".to_string(),
                    data: DataValues::Numbers(vec![1.0, 1.0, 1.0, 1.0, 1.0]),
                    style: Some(DatasetStyle {
                        background_color: Some(ColorValue::Single("rgba(156, 163, 175, 0.2)".to_string())),
                        border_color: Some(ColorValue::Single("#9ca3af".to_string())),
                        ..Default::default()
                    }),
                },
            ],
        },
        options: ChartOptions {
            title: Some(TitleConfig {
                text: "Frederick County vs Peer Average".to_string(),
                display: true,
                ..Default::default()
            }),
            ..Default::default()
        },
        export: None,
    };

    view! { <ChartEngine config=config /> }
}
```

### 7.5 Exporting a Chart

```rust
#[component]
fn ExportableChart() -> impl IntoView {
    let chart_ref = create_node_ref::<html::Div>();
    let (export_url, set_export_url) = create_signal(None::<String>);

    let handle_export = move |result: ExportResult| {
        set_export_url(Some(result.data_url.clone()));
        // Trigger download
        let link = document().create_element("a").unwrap();
        link.set_attribute("href", &result.data_url).unwrap();
        link.set_attribute("download", &format!("chart.{}", 
            match result.format {
                ExportFormat::Png => "png",
                ExportFormat::Svg => "svg",
            }
        )).unwrap();
        link.dyn_ref::<web_sys::HtmlElement>().unwrap().click();
    };

    view! {
        <div>
            <ChartEngine
                config=config
                on_export=handle_export
            />
            <button on:click=move |_| {
                // Trigger export via message
                send_chart_message(ChartMessage::Export {
                    id: "my-chart".to_string(),
                    format: ExportFormat::Png,
                });
            }>
                "Export PNG"
            </button>
        </div>
    }
}
```

---

## 8. Theme Support

### 8.1 Default Theme Colors

```rust
impl Default for ThemeColors {
    fn default() -> Self {
        Self {
            primary: vec![
                "#3b82f6".to_string(), // Blue
                "#10b981".to_string(), // Green
                "#f59e0b".to_string(), // Amber
                "#ef4444".to_string(), // Red
                "#8b5cf6".to_string(), // Purple
                "#06b6d4".to_string(), // Cyan
                "#f97316".to_string(), // Orange
                "#ec4899".to_string(), // Pink
            ],
            background: "#ffffff".to_string(),
            text: "#1f2937".to_string(),
            grid: "#e5e7eb".to_string(),
            border: "#d1d5db".to_string(),
        }
    }
}

/// Dark theme colors
pub fn dark_theme_colors() -> ThemeColors {
    ThemeColors {
        primary: vec![
            "#60a5fa".to_string(), // Blue (lighter)
            "#34d399".to_string(), // Green (lighter)
            "#fbbf24".to_string(), // Amber (lighter)
            "#f87171".to_string(), // Red (lighter)
            "#a78bfa".to_string(), // Purple (lighter)
            "#22d3ee".to_string(), // Cyan (lighter)
            "#fb923c".to_string(), // Orange (lighter)
            "#f472b6".to_string(), // Pink (lighter)
        ],
        background: "#1f2937".to_string(),
        text: "#f9fafb".to_string(),
        grid: "#374151".to_string(),
        border: "#4b5563".to_string(),
    }
}
```

### 8.2 Theme Switching

```rust
/// Global theme context
#[derive(Clone)]
pub struct ChartThemeContext {
    pub theme: RwSignal<Theme>,
}

/// Theme provider component
#[component]
pub fn ChartThemeProvider(
    children: Children,
    #[prop(default = Theme::default())] initial_theme: Theme,
) -> impl IntoView {
    let theme = create_rw_signal(initial_theme);
    provide_context(ChartThemeContext { theme });
    children()
}

/// Hook to access and modify theme
pub fn use_chart_theme() -> ChartThemeContext {
    expect_context::<ChartThemeContext>()
}
```

---

## 9. Dependencies

### 9.1 JavaScript Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| Chart.js | ^4.4.0 | Core charting |
| chartjs-chart-treemap | ^2.3.0 | Treemap charts |
| chartjs-adapter-date-fns | ^3.0.0 | Time scale support |
| Leaflet | ^1.9.4 | Map rendering |
| leaflet-choropleth | ^1.1.4 | Choropleth maps |
| canvas2svg | ^1.0.16 | SVG export |

### 9.2 Rust Crates

| Crate | Purpose |
|-------|---------|
| leptos | UI framework |
| wasm-bindgen | JS interop |
| serde | Serialization |
| tsify | TypeScript type generation |
| web-sys | DOM access |
| js-sys | JavaScript primitives |

---

## 10. Acceptance Criteria

### 10.1 Functional Requirements

- [ ] **FR-1**: All 12 chart types render correctly with valid configuration
- [ ] **FR-2**: Charts accept data from DataEngine query results without transformation
- [ ] **FR-3**: PNG export produces valid image at specified dimensions
- [ ] **FR-4**: SVG export produces valid, scalable vector graphic
- [ ] **FR-5**: Dark mode theme applies consistently to all chart types
- [ ] **FR-6**: Charts resize responsively when container dimensions change
- [ ] **FR-7**: Choropleth maps display Virginia school division boundaries
- [ ] **FR-8**: Tooltips display formatted values on hover
- [ ] **FR-9**: Click events fire with correct data point information
- [ ] **FR-10**: Charts animate on initial render (when enabled)

### 10.2 Non-Functional Requirements

- [ ] **NFR-1**: Initial chart render completes in <100ms for datasets under 1000 points
- [ ] **NFR-2**: Data updates re-render in <50ms
- [ ] **NFR-3**: PNG export completes in <500ms
- [ ] **NFR-4**: SVG export completes in <300ms
- [ ] **NFR-5**: Memory usage per chart instance <5MB
- [ ] **NFR-6**: No memory leaks when charts are created and destroyed
- [ ] **NFR-7**: Charts remain interactive during export operations

### 10.3 Accessibility Requirements

- [ ] **A11Y-1**: Charts include ARIA labels for screen readers
- [ ] **A11Y-2**: Color schemes meet WCAG 2.1 contrast requirements
- [ ] **A11Y-3**: Keyboard navigation supported for interactive elements
- [ ] **A11Y-4**: Data table alternative available for all charts

### 10.4 Testing Requirements

- [ ] **TEST-1**: Unit tests for all Rust type serialization
- [ ] **TEST-2**: Integration tests for Chart.js interop
- [ ] **TEST-3**: Visual regression tests for each chart type
- [ ] **TEST-4**: Export tests verify valid PNG/SVG output
- [ ] **TEST-5**: Theme switching tests verify consistent styling

---

## 11. Error Handling

### 11.1 Error Types

```rust
#[derive(Debug, Clone, Serialize, Deserialize, Tsify)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum ChartError {
    /// Invalid configuration provided
    InvalidConfig { field: String, message: String },
    /// Chart type not supported
    UnsupportedChartType(String),
    /// Data format incompatible with chart type
    DataFormatMismatch { expected: String, received: String },
    /// JavaScript interop failed
    JsError(String),
    /// Canvas element not found
    CanvasNotFound(String),
    /// Export failed
    ExportError(ExportError),
    /// GeoJSON loading failed
    GeoJsonError(String),
}
```

### 11.2 Error Recovery

1. **Invalid Config**: Display error message in chart container
2. **JS Errors**: Log error, emit event, show fallback message
3. **Export Failures**: Emit failure event with error details
4. **Data Mismatches**: Attempt type coercion, fail gracefully with message

---

## 12. Future Considerations

1. **Real-time Updates**: WebSocket integration for live data streaming
2. **Chart Annotations**: Support for highlighting specific data points
3. **Drill-down**: Hierarchical navigation within treemap/sunburst
4. **Combined Charts**: Support for mixed chart types (bar + line)
5. **Custom Plugins**: API for extending chart functionality
6. **Print Optimization**: Print-specific styling and layouts
7. **Offline Support**: Cache chart configurations for offline rendering
