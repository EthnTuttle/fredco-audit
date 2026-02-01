//! ChartEngine types for visualization

use serde::{Deserialize, Serialize};
use tsify::Tsify;

// Re-use Theme from storage module for consistency
pub use crate::storage::Theme;

/// Chart type enumeration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
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
    // Time series
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

/// Chart configuration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChartConfig {
    /// Unique chart ID
    pub id: String,
    /// Chart type
    pub chart_type: ChartType,
    /// Chart title
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// Data configuration
    pub data: ChartData,
    /// Chart options
    #[serde(skip_serializing_if = "Option::is_none")]
    pub options: Option<ChartOptions>,
    /// Theme (light/dark)
    #[serde(default)]
    pub theme: Theme,
}

/// Chart data specification
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChartData {
    /// Labels for X axis or categories
    pub labels: Vec<String>,
    /// Data series
    pub datasets: Vec<Dataset>,
}

/// A single data series
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Dataset {
    /// Series label
    pub label: String,
    /// Data values
    pub data: DataValues,
    /// Optional styling
    #[serde(skip_serializing_if = "Option::is_none")]
    pub style: Option<DatasetStyle>,
}

/// Data values (varies by chart type)
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(untagged)]
pub enum DataValues {
    /// Simple numeric values (bar, line, pie, etc.)
    Numbers(Vec<f64>),
    /// X,Y points (scatter)
    Points(Vec<Point>),
    /// X,Y,R points (bubble)
    Bubbles(Vec<BubblePoint>),
    /// Hierarchical data (treemap, sunburst)
    Hierarchical(Vec<HierarchicalNode>),
    /// Geographic data (choropleth)
    Geographic(Vec<GeoDataPoint>),
}

/// 2D point
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

/// Bubble chart point
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct BubblePoint {
    pub x: f64,
    pub y: f64,
    pub r: f64,
}

/// Hierarchical node for treemap/sunburst
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct HierarchicalNode {
    pub name: String,
    pub value: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub children: Option<Vec<HierarchicalNode>>,
}

/// Geographic data point for choropleth
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct GeoDataPoint {
    /// Region identifier (matches GeoJSON property)
    pub region_id: String,
    /// Value for coloring
    pub value: f64,
    /// Optional label
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
}

/// Dataset styling
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct DatasetStyle {
    /// Background color
    #[serde(skip_serializing_if = "Option::is_none")]
    pub background_color: Option<ColorValue>,
    /// Border color
    #[serde(skip_serializing_if = "Option::is_none")]
    pub border_color: Option<ColorValue>,
    /// Border width
    #[serde(skip_serializing_if = "Option::is_none")]
    pub border_width: Option<f64>,
    /// Fill area under line
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fill: Option<bool>,
    /// Line tension (0 = straight)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tension: Option<f64>,
}

/// Color value (single or array for gradients)
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(untagged)]
pub enum ColorValue {
    Single(String),
    Multiple(Vec<String>),
}

/// Chart options
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChartOptions {
    /// Responsive sizing
    #[serde(default = "default_true")]
    pub responsive: bool,
    /// Maintain aspect ratio
    #[serde(default = "default_true")]
    pub maintain_aspect_ratio: bool,
    /// Show legend
    #[serde(default = "default_true")]
    pub show_legend: bool,
    /// Legend position
    #[serde(default)]
    pub legend_position: LegendPosition,
    /// X axis config
    #[serde(skip_serializing_if = "Option::is_none")]
    pub x_axis: Option<AxisConfig>,
    /// Y axis config
    #[serde(skip_serializing_if = "Option::is_none")]
    pub y_axis: Option<AxisConfig>,
    /// Enable tooltips
    #[serde(default = "default_true")]
    pub tooltips: bool,
    /// Enable animations
    #[serde(default = "default_true")]
    pub animations: bool,
}

fn default_true() -> bool {
    true
}

/// Legend position
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum LegendPosition {
    #[default]
    Top,
    Bottom,
    Left,
    Right,
}

/// Axis configuration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct AxisConfig {
    /// Axis title
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// Minimum value
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min: Option<f64>,
    /// Maximum value
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max: Option<f64>,
    /// Start at zero
    #[serde(default)]
    pub begin_at_zero: bool,
    /// Stacked mode
    #[serde(default)]
    pub stacked: bool,
}

// Theme is defined in storage.rs and re-exported above

/// Choropleth configuration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChoroplethConfig {
    /// GeoJSON URL or inline data
    pub geo_data: GeoSource,
    /// Property to match region IDs
    pub region_property: String,
    /// Color scale
    pub color_scale: ColorScale,
}

/// GeoJSON source
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
#[serde(tag = "type")]
pub enum GeoSource {
    #[serde(rename = "url")]
    Url { url: String },
    #[serde(rename = "inline")]
    Inline { geojson: String },
}

/// Color scale for choropleth
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ColorScale {
    /// Minimum color
    pub min_color: String,
    /// Maximum color
    pub max_color: String,
    /// Number of steps
    #[serde(default = "default_steps")]
    pub steps: u32,
}

fn default_steps() -> u32 {
    5
}

/// Export configuration
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ExportConfig {
    /// Export format
    pub format: ExportFormat,
    /// Width in pixels
    #[serde(skip_serializing_if = "Option::is_none")]
    pub width: Option<u32>,
    /// Height in pixels
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<u32>,
    /// Background color (default: transparent for SVG)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub background: Option<String>,
}

/// Export format
#[derive(Tsify, Serialize, Deserialize, Clone, Debug, PartialEq)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub enum ExportFormat {
    Png,
    Svg,
}

/// Render request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct RenderRequest {
    /// Chart configuration
    pub config: ChartConfig,
    /// Target element ID
    pub target: String,
}

/// Export request
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ChartExportRequest {
    /// Chart ID to export
    pub chart_id: String,
    /// Export configuration
    pub config: ExportConfig,
}

/// Export result
#[derive(Tsify, Serialize, Deserialize, Clone, Debug)]
#[tsify(into_wasm_abi, from_wasm_abi)]
pub struct ExportResult {
    /// Data URL (base64 for PNG, SVG string for SVG)
    pub data_url: String,
    /// MIME type
    pub mime_type: String,
}
