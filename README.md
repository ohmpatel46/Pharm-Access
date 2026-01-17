# PharmAccess Explorer

A 3-day prototype mapping pharmacy deserts and inferred supply-chain connectivity across the United States, relevant for McKesson.

## Project Structure

```
pharmaccess/
├── frontend/              # React + Vite + Mapbox GL JS application
│   ├── public/
│   │   └── data/         # GeoJSON data files
│   ├── src/
│   │   ├── components/   # React components
│   │   └── styles/       # CSS styles
│   └── package.json
├── data/                 # Python data pipeline scripts
│   ├── fetch_pharmacies.py
│   ├── preprocess_regions.py
│   └── build_supply_graph.py
└── README.md
```

## Quick Start

### Prerequisites

- **Node.js** (v18 or higher)
- **Python** (v3.8 or higher)
- **Mapbox Access Token** ([Get one here](https://account.mapbox.com/access-tokens/))

### 1. Frontend Setup

```bash
cd frontend
npm install
```

Create a `.env` file in the `frontend/` directory:

```env
VITE_MAPBOX_ACCESS_TOKEN=your_mapbox_token_here
```

Run the development server:

```bash
npm run dev
```

The app will open at `http://localhost:3000`

### 2. Build Pharmacy Dataset

Install Python dependencies:

```bash
pip install -r data/requirements.txt
```

**Option A: NPPES Data (Recommended - Official CMS Data)**

Extract pharmacies from NPPES (CMS) data:

```bash
cd data
python fetch_pharmacies_nppes.py --test  # Test mode (first 100k rows)
```

For full extraction:
```bash
python fetch_pharmacies_nppes.py  # Full dataset (may take 4-8 hours with geocoding)
```

This will:
- Read NPPES CSV file (chunked for large file handling)
- Filter for pharmacy taxonomy codes (3336*)
- Geocode addresses to get lat/lon coordinates
- Export to `frontend/public/data/pharmacies.geojson`

**Note:** 
- Full dataset extraction + geocoding may take 4-8 hours
- Use `--test` flag for quick testing (first 100k rows, ~5-10 minutes)
- Geocoding uses Nominatim API with rate limiting (1 request/second)

**Option B: OSM Data (Legacy)**

```bash
cd data
python fetch_pharmacies.py --test  # Use test mode for faster results
```

### 3. Load Data in Mapbox

Once `pharmacies.geojson` is generated, refresh your browser. The map will automatically load and display:
- **Clustered pharmacy points** (color-coded by density)
- **Individual pharmacy markers** (clickable with popups)
- **Interactive clustering** (zoom in to see individual pharmacies)

## Features

### Current Implementation

- ✅ Mapbox GL JS map centered on USA
- ✅ Pharmacy data loading from GeoJSON
- ✅ Clustering visualization (cluster bubbles and labels)
- ✅ Interactive popups showing pharmacy details (name, chain, address)
- ✅ Responsive full-screen layout

### Placeholder Data Files

The following files are empty placeholders for future implementation:

- `frontend/public/data/regions.geojson` - Census tract polygons with desert classifications
- `frontend/public/data/supply_edges.geojson` - DC → pharmacy supply chain edges
- `frontend/public/data/pharmacy_graph_edges.geojson` - Pharmacy → pharmacy nearest neighbor graph

## Next Steps

### 1. Pharmacy Desert Analysis

**File:** `data/preprocess_regions.py`

- Load census tract polygons (from Census Bureau or similar)
- Compute distance-to-nearest-pharmacy for each tract
- Classify tracts as "pharmacy deserts" (e.g., >5 miles from nearest pharmacy)
- Export `regions.geojson` with desert classification
- Add layer to map showing desert regions

### 2. Supply Chain Graph

**File:** `data/build_supply_graph.py`

- Identify distribution centers (DCs) for major pharmacy chains
- Compute DC → pharmacy supply edges (using network analysis)
- Compute pharmacy → pharmacy nearest neighbor graph
- Export `supply_edges.geojson` and `pharmacy_graph_edges.geojson`
- Add line layers to map showing supply chain connections

### 3. Deployment

**Vercel Deployment:**

1. Build the frontend:
   ```bash
   cd frontend
   npm run build
   ```

2. Deploy to Vercel:
   ```bash
   npm install -g vercel
   vercel
   ```

3. Set environment variable in Vercel dashboard:
   - `VITE_MAPBOX_ACCESS_TOKEN`

4. Ensure `public/data/` files are included in the build

## Development

### Frontend Commands

```bash
npm run dev      # Start development server
npm run build    # Build for production
npm run preview  # Preview production build
```

### Data Pipeline

See `data/README_DATA.md` for details on the Python scripts.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `VITE_MAPBOX_ACCESS_TOKEN` | Mapbox access token for map rendering | Yes |

## License

See LICENSE file.

