import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

interface MapViewProps {
  mapboxToken: string;
}

const MapView = ({ mapboxToken }: MapViewProps) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Check if container has dimensions
    if (mapContainer.current.offsetWidth === 0 || mapContainer.current.offsetHeight === 0) {
      console.warn('Map container has no dimensions, waiting...');
      // Try again after a short delay
      const timer = setTimeout(() => {
        if (mapContainer.current && (mapContainer.current.offsetWidth > 0 && mapContainer.current.offsetHeight > 0)) {
          initializeMap();
        }
      }, 100);
      return () => clearTimeout(timer);
    }

    initializeMap();

    function initializeMap() {
      if (!mapContainer.current || map.current) return;

      // Initialize map
      mapboxgl.accessToken = mapboxToken;

      try {
        map.current = new mapboxgl.Map({
          container: mapContainer.current,
          style: 'mapbox://styles/mapbox/satellite-streets-v12', // Satellite style with star/galaxy background
          center: [-98.5795, 39.8283], // Center of USA
          zoom: 4,
          projection: 'globe', // Enable globe projection (shows star/galaxy background)
          antialias: true, // Better rendering quality
          preserveDrawingBuffer: true, // Help with WebGL context
        });

        const currentMap = map.current;
        
        // Configure globe to show star/galaxy background with dusk theme
        currentMap.on('style.load', () => {
          try {
            // Set dusk lighting preset
            currentMap.setConfigProperty('basemap', 'lightPreset', 'dusk');
            
            // Satellite-streets style has star/galaxy background built-in with globe projection
            // Apply dusk lighting for darker theme effect
            console.log('Satellite-streets style with star background and dusk lighting loaded');
          } catch (e) {
            console.log('Using default globe settings:', e);
          }
        });
        
        // The star/galaxy background appears automatically with globe projection
        // when you zoom out far enough or rotate the globe to view space
        // This is a built-in feature of Mapbox globe projection
        
        // Log map initialization
        console.log('Map initialized successfully');
        
        // Handle WebGL context loss
        currentMap.on('webglcontextlost', () => {
          console.warn('WebGL context lost');
        });
        
        currentMap.on('webglcontextrestored', () => {
          console.log('WebGL context restored');
          const pharmaciesSource = currentMap.getSource('pharmacies');
          if (pharmaciesSource && 'reload' in pharmaciesSource) {
            (pharmaciesSource as mapboxgl.GeoJSONSource).reload();
          }
        });

        currentMap.on('load', () => {
      console.log('Loading pharmacy data...');
      
      // Add pharmacy data source with optimized clustering for large datasets
      currentMap.addSource('pharmacies', {
        type: 'geojson',
        data: '/data/pharmacies.geojson',
        cluster: true,
        clusterMaxZoom: 12, // Cluster up to zoom level 12
        clusterRadius: 50, // Larger radius for better clustering
        clusterProperties: {
          // Keep cluster properties minimal
        },
        generateId: true, // Generate IDs for better performance
      });
      
      // Log when source is loaded
      const source = currentMap.getSource('pharmacies') as mapboxgl.GeoJSONSource;
      if (source && 'setData' in source) {
        console.log('Pharmacy source added, loading data...');
      }

      // Add cluster circles
      currentMap.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'pharmacies',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': [
            'step',
            ['get', 'point_count'],
            '#51bbd6',
            100,
            '#f1f075',
            750,
            '#f28cb1',
          ],
          'circle-radius': [
            'step',
            ['get', 'point_count'],
            20,
            100,
            30,
            750,
            40,
          ],
        },
      });

      // Add cluster count labels
      currentMap.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'pharmacies',
        filter: ['has', 'point_count'],
        layout: {
          'text-field': '{point_count_abbreviated}',
          'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Bold'],
          'text-size': 12,
        },
      });

      // Add unclustered pharmacy points (only show at higher zoom levels)
      currentMap.addLayer({
        id: 'unclustered-point',
        type: 'circle',
        source: 'pharmacies',
        filter: ['!', ['has', 'point_count']],
        minzoom: 10, // Only show individual points at zoom 10+
        paint: {
          'circle-color': '#11b4da',
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            10, 4,  // Smaller at zoom 10
            15, 8   // Larger at zoom 15
          ],
          'circle-stroke-width': 1,
          'circle-stroke-color': '#fff',
        },
      });

      // Create popup
      const popup = new mapboxgl.Popup({
        closeButton: false,
        closeOnClick: false,
      });

      // Show popup on hover for unclustered points
      currentMap.on('mouseenter', 'unclustered-point', (e) => {
        if (!e.features || e.features.length === 0) return;

        const feature = e.features[0];
        const props = feature.properties || {};
        const coordinates = (feature.geometry as GeoJSON.Point).coordinates.slice() as [number, number];

        // Build popup content - simple name and address
        const name = props.name || 'Unknown Pharmacy';
        const address = props.full_address || [props.address, props.city, props.state].filter(Boolean).join(', ') || 'Address not available';

        const popupContent = `
          <div style="padding: 8px; min-width: 200px;">
            <strong style="font-size: 14px; display: block; margin-bottom: 4px;">${name}</strong>
            <span style="color: #666; font-size: 12px;">${address}</span>
          </div>
        `;

        popup
          .setLngLat(coordinates)
          .setHTML(popupContent)
          .addTo(currentMap);
      });

      currentMap.on('mouseleave', 'unclustered-point', () => {
        popup.remove();
      });

      // Zoom in on cluster click
      currentMap.on('click', 'clusters', (e) => {
        if (!e.features || e.features.length === 0) return;

        const feature = e.features[0];
        const clusterId = feature.properties?.cluster_id;
        const source = currentMap.getSource('pharmacies') as mapboxgl.GeoJSONSource;

        source.getClusterExpansionZoom(clusterId, (err, zoom) => {
          if (err || zoom === undefined || zoom === null) return;

          currentMap.easeTo({
            center: (feature.geometry as GeoJSON.Point).coordinates as [number, number],
            zoom: zoom,
          });
        });
      });

      // Show popup on click for unclustered points
      currentMap.on('click', 'unclustered-point', (e) => {
        if (!e.features || e.features.length === 0) return;

        const feature = e.features[0];
        const props = feature.properties || {};
        const coordinates = (feature.geometry as GeoJSON.Point).coordinates.slice() as [number, number];

        // Build popup content - simple name and address
        const name = props.name || 'Unknown Pharmacy';
        const address = props.full_address || [props.address, props.city, props.state].filter(Boolean).join(', ') || 'Address not available';

        const popupContent = `
          <div style="padding: 8px; min-width: 200px;">
            <strong style="font-size: 14px; display: block; margin-bottom: 4px;">${name}</strong>
            <span style="color: #666; font-size: 12px;">${address}</span>
          </div>
        `;

        new mapboxgl.Popup()
          .setLngLat(coordinates)
          .setHTML(popupContent)
          .addTo(currentMap);
      });

      // Change cursor on hover
      currentMap.on('mouseenter', 'clusters', () => {
        currentMap.getCanvas().style.cursor = 'pointer';
      });
      currentMap.on('mouseleave', 'clusters', () => {
        currentMap.getCanvas().style.cursor = '';
      });
      currentMap.on('mouseenter', 'unclustered-point', () => {
        currentMap.getCanvas().style.cursor = 'pointer';
      });
      currentMap.on('mouseleave', 'unclustered-point', () => {
        currentMap.getCanvas().style.cursor = '';
      });
      
      // Log when map is fully loaded
      console.log('Map layers and interactions set up');
        });
      
      currentMap.on('error', (e) => {
        console.error('Map error:', e);
      });
      } catch (error) {
        console.error('Failed to initialize map:', error);
      }
    }

    // Cleanup
    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [mapboxToken]);

  return <div ref={mapContainer} style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} />;
};

export default MapView;

