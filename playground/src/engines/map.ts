/**
 * Map Engine - Leaflet-based interactive map visualization
 * 
 * Renders GeoJSON data as choropleth maps with SQL query integration.
 * Supports parcel data, growth areas, fire districts, and other GIS layers.
 */

import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default marker icon issue in bundled environments
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import iconRetina from 'leaflet/dist/images/marker-icon-2x.png';

// @ts-expect-error - Leaflet type definitions don't expose this
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetina,
  iconUrl: icon,
  shadowUrl: iconShadow,
});

// ============================================================================
// Types
// ============================================================================

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: GeoJSON.Geometry;
  properties: Record<string, unknown>;
}

export interface GeoJSONCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

export interface MapLayerConfig {
  name: string;
  url: string; // Parquet file URL
  style?: L.PathOptions;
  fillProperty?: string; // Property to use for choropleth fill
  labelProperty?: string; // Property to show on hover
  minZoom?: number;
  maxZoom?: number;
}

export interface ChoroplethConfig {
  property: string; // Property name to color by
  scale: 'linear' | 'quantile' | 'jenks';
  colors: string[]; // Color ramp from low to high
  nullColor?: string;
}

// ============================================================================
// Map Engine Class
// ============================================================================

class MapEngine {
  private map: L.Map | null = null;
  private layers: Map<string, L.GeoJSON> = new Map();

  // Frederick County center coordinates
  private readonly defaultCenter: L.LatLngExpression = [39.15, -78.15];
  private readonly defaultZoom = 10;

  /**
   * Initialize the map in a container element
   */
  init(containerId: string): L.Map {
    const container = document.getElementById(containerId);
    if (!container) {
      throw new Error(`Map container '${containerId}' not found`);
    }

    // Destroy existing map if present
    if (this.map) {
      this.map.remove();
    }

    // Create map
    this.map = L.map(containerId, {
      center: this.defaultCenter,
      zoom: this.defaultZoom,
      zoomControl: true,
      attributionControl: true,
    });

    // Add base tile layer (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(this.map);

    // Add satellite layer option
    const satellite = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        attribution: '&copy; Esri',
        maxZoom: 19,
      }
    );

    // Layer control
    L.control.layers(
      {
        'Street Map': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'),
        'Satellite': satellite,
      },
      {},
      { position: 'topright' }
    ).addTo(this.map);

    return this.map;
  }

  /**
   * Get the current map instance
   */
  getMap(): L.Map | null {
    return this.map;
  }

  /**
   * Add GeoJSON data as a layer
   */
  addGeoJSONLayer(
    name: string,
    geojson: GeoJSONCollection,
    options?: {
      style?: L.PathOptions;
      onEachFeature?: (feature: GeoJSONFeature, layer: L.Layer) => void;
      fitBounds?: boolean;
    }
  ): L.GeoJSON {
    if (!this.map) {
      throw new Error('Map not initialized');
    }

    // Remove existing layer with same name
    if (this.layers.has(name)) {
      this.map.removeLayer(this.layers.get(name)!);
    }

    const defaultStyle: L.PathOptions = {
      color: '#00d9ff',
      weight: 1,
      opacity: 0.8,
      fillOpacity: 0.3,
    };

    const layer = L.geoJSON(geojson as GeoJSON.FeatureCollection, {
      style: options?.style || defaultStyle,
      onEachFeature: options?.onEachFeature || ((feature, layer) => this.defaultOnEachFeature(feature as GeoJSONFeature, layer)),
    });

    layer.addTo(this.map);
    this.layers.set(name, layer);

    // Fit map to layer bounds
    if (options?.fitBounds !== false && layer.getBounds().isValid()) {
      this.map.fitBounds(layer.getBounds(), { padding: [20, 20] });
    }

    return layer;
  }

  /**
   * Default feature interaction handler
   */
  private defaultOnEachFeature(feature: GeoJSONFeature, layer: L.Layer): void {
    // Create popup with feature properties
    const props = feature.properties;
    const popupContent = Object.entries(props)
      .filter(([key]) => !key.startsWith('_') && key !== 'geometry')
      .slice(0, 10)
      .map(([key, value]) => {
        const displayValue = typeof value === 'number' 
          ? value.toLocaleString() 
          : String(value);
        return `<strong>${key}:</strong> ${displayValue}`;
      })
      .join('<br>');

    if (popupContent) {
      layer.bindPopup(popupContent);
    }

    // Highlight on hover
    if (layer instanceof L.Path) {
      layer.on('mouseover', () => {
        layer.setStyle({ weight: 3, fillOpacity: 0.5 });
      });
      layer.on('mouseout', () => {
        layer.setStyle({ weight: 1, fillOpacity: 0.3 });
      });
    }
  }

  /**
   * Apply choropleth coloring to a layer
   */
  applyChoropleth(
    layerName: string,
    config: ChoroplethConfig
  ): void {
    const layer = this.layers.get(layerName);
    if (!layer) {
      throw new Error(`Layer '${layerName}' not found`);
    }

    // Collect values for the property
    const values: number[] = [];
    layer.eachLayer((l) => {
      if (l instanceof L.Path) {
        const feature = (l as unknown as { feature?: GeoJSONFeature }).feature;
        if (feature) {
          const value = feature.properties[config.property];
          if (typeof value === 'number' && !isNaN(value)) {
            values.push(value);
          }
        }
      }
    });

    if (values.length === 0) {
      console.warn(`No numeric values found for property '${config.property}'`);
      return;
    }

    // Calculate breaks based on scale
    const breaks = this.calculateBreaks(values, config.scale, config.colors.length);
    
    // Apply colors
    layer.eachLayer((l) => {
      if (l instanceof L.Path) {
        const feature = (l as unknown as { feature?: GeoJSONFeature }).feature;
        if (feature) {
          const value = feature.properties[config.property];
          
          let color: string;
          if (typeof value !== 'number' || isNaN(value)) {
            color = config.nullColor || '#ccc';
          } else {
            color = this.getColorForValue(value, breaks, config.colors);
          }
          
          l.setStyle({ fillColor: color, fillOpacity: 0.7 });
        }
      }
    });

    // Add legend
    this.addLegend(breaks, config.colors, config.property);
  }

  /**
   * Calculate class breaks for choropleth
   */
  private calculateBreaks(values: number[], scale: string, numClasses: number): number[] {
    const sorted = [...values].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];

    switch (scale) {
      case 'linear': {
        const step = (max - min) / numClasses;
        return Array.from({ length: numClasses + 1 }, (_, i) => min + step * i);
      }
      case 'quantile': {
        const step = sorted.length / numClasses;
        const breaks = [min];
        for (let i = 1; i < numClasses; i++) {
          breaks.push(sorted[Math.floor(step * i)]);
        }
        breaks.push(max);
        return breaks;
      }
      default:
        return this.calculateBreaks(values, 'linear', numClasses);
    }
  }

  /**
   * Get color for a value based on breaks
   */
  private getColorForValue(value: number, breaks: number[], colors: string[]): string {
    for (let i = 0; i < breaks.length - 1; i++) {
      if (value <= breaks[i + 1]) {
        return colors[i];
      }
    }
    return colors[colors.length - 1];
  }

  /**
   * Add a legend to the map
   */
  private addLegend(breaks: number[], colors: string[], property: string): void {
    if (!this.map) return;

    // Remove existing legend
    const existingLegend = document.querySelector('.map-legend');
    if (existingLegend) {
      existingLegend.remove();
    }

    // @ts-expect-error - Leaflet control typing issue
    const legend: L.Control = L.control({ position: 'bottomright' });
    
    legend.onAdd = () => {
      const div = L.DomUtil.create('div', 'map-legend');
      div.innerHTML = `
        <style>
          .map-legend {
            background: var(--bg-secondary, rgba(0,0,0,0.8));
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 11px;
            color: var(--text-primary, white);
          }
          .map-legend-title {
            font-weight: 600;
            margin-bottom: 6px;
          }
          .map-legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            margin: 3px 0;
          }
          .map-legend-color {
            width: 18px;
            height: 12px;
            border: 1px solid rgba(255,255,255,0.3);
          }
        </style>
        <div class="map-legend-title">${property}</div>
        ${colors.map((color, i) => {
          const from = breaks[i];
          const to = breaks[i + 1];
          const label = from === to 
            ? from.toLocaleString()
            : `${from.toLocaleString()} - ${to.toLocaleString()}`;
          return `
            <div class="map-legend-item">
              <div class="map-legend-color" style="background: ${color}"></div>
              <span>${label}</span>
            </div>
          `;
        }).join('')}
      `;
      return div;
    };

    legend.addTo(this.map);
  }

  /**
   * Remove a layer by name
   */
  removeLayer(name: string): void {
    const layer = this.layers.get(name);
    if (layer && this.map) {
      this.map.removeLayer(layer);
      this.layers.delete(name);
    }
  }

  /**
   * Clear all layers
   */
  clearLayers(): void {
    this.layers.forEach((layer) => {
      if (this.map) {
        this.map.removeLayer(layer);
      }
    });
    this.layers.clear();
  }

  /**
   * Zoom to Frederick County bounds
   */
  zoomToCounty(): void {
    if (!this.map) return;
    // Frederick County approximate bounds
    const bounds = L.latLngBounds(
      [38.95, -78.55], // SW
      [39.35, -77.85]  // NE
    );
    this.map.fitBounds(bounds);
  }

  /**
   * Destroy the map instance
   */
  destroy(): void {
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
    this.layers.clear();
  }
}

// Singleton instance
let mapEngineInstance: MapEngine | null = null;

export function getMapEngine(): MapEngine {
  if (!mapEngineInstance) {
    mapEngineInstance = new MapEngine();
  }
  return mapEngineInstance;
}

// ============================================================================
// Color Ramps
// ============================================================================

export const COLOR_RAMPS = {
  // Sequential ramps
  blues: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#084594'],
  greens: ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32'],
  reds: ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#99000d'],
  purples: ['#fcfbfd', '#efedf5', '#dadaeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#4a1486'],
  
  // Diverging ramps
  redBlue: ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac'],
  brownGreen: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
  
  // Property value ramp
  value: ['#ffffcc', '#c7e9b4', '#7fcdbb', '#41b6c4', '#2c7fb8', '#253494'],
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Convert parquet query results to GeoJSON
 * Assumes geometry column contains WKT or GeoJSON
 */
export function queryResultToGeoJSON(
  rows: unknown[][],
  columns: string[],
  geometryColumn = 'geometry'
): GeoJSONCollection {
  const geomIndex = columns.indexOf(geometryColumn);
  if (geomIndex === -1) {
    throw new Error(`Geometry column '${geometryColumn}' not found in results`);
  }

  const features: GeoJSONFeature[] = rows.map((row) => {
    const properties: Record<string, unknown> = {};
    columns.forEach((col, i) => {
      if (col !== geometryColumn) {
        properties[col] = row[i];
      }
    });

    const geomValue = row[geomIndex];
    let geometry: GeoJSONFeature['geometry'];

    if (typeof geomValue === 'string') {
      // Try parsing as GeoJSON
      try {
        geometry = JSON.parse(geomValue);
      } catch {
        // Assume WKT and skip for now
        console.warn('WKT parsing not implemented, skipping feature');
        geometry = { type: 'Point', coordinates: [0, 0] };
      }
    } else if (typeof geomValue === 'object' && geomValue !== null) {
      geometry = geomValue as GeoJSONFeature['geometry'];
    } else {
      geometry = { type: 'Point', coordinates: [0, 0] };
    }

    return {
      type: 'Feature',
      geometry,
      properties,
    };
  });

  return {
    type: 'FeatureCollection',
    features,
  };
}
