"""
Extract pharmacies from NPPES data and geocode addresses.

This script:
1. Reads NPPES CSV file (chunked for large file handling)
2. Filters for pharmacy taxonomy codes (3336*)
3. Extracts pharmacy information (name, address, city, state)
4. Geocodes addresses to get lat/lon coordinates
5. Exports to GeoJSON format compatible with Mapbox frontend

Usage:
    python fetch_pharmacies_nppes.py
"""

import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from shapely.geometry import Point
import json
import os
import sys
from tqdm import tqdm
import time
import warnings
import requests
warnings.filterwarnings('ignore')

# Pharmacy taxonomy codes (all codes starting with 3336)
PHARMACY_CODES = [
    '333600000X',  # Pharmacy (general)
    '3336C0002X',  # Clinic Pharmacy
    '3336C0003X',  # Community/Retail Pharmacy
    '3336C0004X',  # Compounding Pharmacy
    '3336H0001X',  # Home Infusion Therapy Pharmacy
    '3336I0012X',  # Institutional Pharmacy
    '3336L0003X',  # Long Term Care Pharmacy
    '3336M0002X',  # Mail Order Pharmacy
    '3336M0003X',  # Managed Care Organization Pharmacy
    '3336S0011X',  # Specialty Pharmacy
]

# Columns we need from NPPES
REQUIRED_COLS = [
    'NPI',
    'Provider Organization Name (Legal Business Name)',
    'Provider First Line Business Practice Location Address',
    'Provider Second Line Business Practice Location Address',
    'Provider Business Practice Location Address City Name',
    'Provider Business Practice Location Address State Name',
    'Provider Business Practice Location Address Postal Code',
    'Provider Business Practice Location Address Country Code (If outside U.S.)',
]

# All taxonomy code columns (check all 15)
TAXONOMY_COLS = [f'Healthcare Provider Taxonomy Code_{i}' for i in range(1, 16)]

def find_nppes_file():
    """Find the NPPES CSV file."""
    for root, dirs, files in os.walk('.'):
        for file in files:
            if 'npidata_pfile' in file and file.endswith('.csv'):
                return os.path.join(root, file)
    return None

def is_pharmacy(row):
    """Check if a row represents a pharmacy by checking all taxonomy code columns."""
    for col in TAXONOMY_COLS:
        if pd.notna(row.get(col)):
            code = str(row[col]).strip()
            if code in PHARMACY_CODES:
                return True, code
    return False, None

def build_address(row):
    """Build a complete address string from NPPES fields."""
    addr_parts = []
    
    # First line
    addr1 = row.get('Provider First Line Business Practice Location Address', '')
    if pd.notna(addr1):
        addr1_str = str(addr1).strip()
        if addr1_str:
            addr_parts.append(addr1_str)
    
    # Second line
    addr2 = row.get('Provider Second Line Business Practice Location Address', '')
    if pd.notna(addr2):
        addr2_str = str(addr2).strip()
        if addr2_str:
            addr_parts.append(addr2_str)
    
    # City
    city = row.get('Provider Business Practice Location Address City Name', '')
    if pd.notna(city):
        city_str = str(city).strip()
        if city_str:
            addr_parts.append(city_str)
    
    # State
    state = row.get('Provider Business Practice Location Address State Name', '')
    if pd.notna(state):
        state_str = str(state).strip()
        if state_str:
            addr_parts.append(state_str)
    
    # ZIP - clean up and use only first 5 digits for geocoding
    zip_code = row.get('Provider Business Practice Location Address Postal Code', '')
    if pd.notna(zip_code):
        zip_str = str(zip_code).strip()
        # Remove .0 suffix if it's a float representation
        if zip_str.endswith('.0'):
            zip_str = zip_str[:-2]
        
        # Extract only first 5 digits (ignore ZIP+4 extensions)
        zip_clean = zip_str.replace('-', '').replace(' ', '')
        if zip_clean.isdigit() and len(zip_clean) >= 5:
            # Take only first 5 digits
            zip_5digit = zip_clean[:5]
            addr_parts.append(zip_5digit)
        elif zip_clean.isdigit() and len(zip_clean) < 5:
            # If less than 5 digits, skip it (invalid)
            pass
        # Reject non-numeric ZIP codes
    
    return ', '.join(addr_parts)

def normalize_address_for_geocoding(addr_str):
    """
    Normalize address string to improve geocoding success rate.
    """
    import re
    
    # Remove trailing .0 from ZIP codes
    addr_str = re.sub(r'(\d+)\.0(,|$)', r'\1\2', addr_str)
    
    # Expand common abbreviations that might confuse geocoders
    abbreviations = {
        r'\bSTE\b': 'SUITE',
        r'\bSTE\.\b': 'SUITE',
        r'\bST\b': 'STREET',  # Only if not at end (like "ST PAUL")
        r'\bAVE\b': 'AVENUE',
        r'\bAVE\.\b': 'AVENUE',
        r'\bBLVD\b': 'BOULEVARD',
        r'\bBLVD\.\b': 'BOULEVARD',
        r'\bDR\b': 'DRIVE',
        r'\bDR\.\b': 'DRIVE',
        r'\bLN\b': 'LANE',
        r'\bLN\.\b': 'LANE',
        r'\bPKWY\b': 'PARKWAY',
        r'\bPKWY\.\b': 'PARKWAY',
        r'\bHWY\b': 'HIGHWAY',
        r'\bHWY\.\b': 'HIGHWAY',
        r'\bRR\b': 'RURAL ROUTE',
        r'\bUNIT\b': 'SUITE',  # Convert UNIT to SUITE
    }
    
    for pattern, replacement in abbreviations.items():
        addr_str = re.sub(pattern, replacement, addr_str, flags=re.IGNORECASE)
    
    # Remove extra spaces
    addr_str = ' '.join(addr_str.split())
    
    return addr_str

def geocode_with_mapbox(addr, mapbox_token):
    """Geocode using Mapbox Geocoding API."""
    if not mapbox_token:
        return None, None
    
    try:
        # Mapbox Geocoding API endpoint
        url = "https://api.mapbox.com/geocoding/v5/mapbox.places/{}.json".format(
            requests.utils.quote(addr)
        )
        params = {
            'access_token': mapbox_token,
            'country': 'US',  # Limit to US
            'limit': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get('features') and len(data['features']) > 0:
            coords = data['features'][0]['geometry']['coordinates']
            lon, lat = coords[0], coords[1]  # Mapbox returns [lon, lat]
            return lat, lon
        
        return None, None
    except Exception as e:
        return None, None

def geocode_with_census(addr):
    """Geocode using US Census Geocoder (free, US only)."""
    try:
        # Parse address components
        # Format: "street, city, state, zip"
        parts = [p.strip() for p in addr.split(',')]
        if len(parts) < 3:
            return None, None
        
        street = parts[0] if len(parts) > 0 else ''
        city = parts[-3] if len(parts) >= 3 else ''
        state = parts[-2] if len(parts) >= 2 else ''
        zip_code = parts[-1] if len(parts) >= 1 else ''
        
        # Remove "USA" if present
        if zip_code.upper() == 'USA':
            zip_code = state
            state = city
            city = parts[-3] if len(parts) >= 3 else ''
        
        # Census geocoder API
        url = "https://geocoding.geo.census.gov/geocoder/locations/address"
        params = {
            'street': street,
            'city': city,
            'state': state,
            'zip': zip_code[:5] if zip_code else '',  # Only first 5 digits
            'benchmark': 'Public_AR_Current',
            'format': 'json'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get('result') and data['result'].get('addressMatches'):
            match = data['result']['addressMatches'][0]
            coords = match['coordinates']
            return coords['y'], coords['x']  # lat, lon
        
        return None, None
    except Exception as e:
        return None, None

def geocode_addresses_batch(addresses, geocoder_type='mapbox', mapbox_token=None):
    """
    Geocode a batch of addresses.
    
    Args:
        addresses: List of address strings
        geocoder_type: 'mapbox', 'census', or 'nominatim'
        mapbox_token: Mapbox access token (required for mapbox)
    
    Returns:
        List of (lat, lon) tuples, with (None, None) for failed geocodes.
    """
    if not addresses:
        return []
    
    # Prepare addresses for geocoding
    geocode_addresses = []
    for addr in addresses:
        if not addr or len(str(addr).strip()) < 5:
            geocode_addresses.append(None)
        else:
            addr_str = str(addr).strip()
            # Normalize address
            addr_str = normalize_address_for_geocoding(addr_str)
            
            # Remove USA suffix for Census geocoder (it's US-only)
            if geocoder_type == 'census':
                addr_str = addr_str.replace(', USA', '').replace(', United States', '').strip()
            elif 'USA' not in addr_str.upper() and 'United States' not in addr_str:
                addr_str = f"{addr_str}, USA"
            
            geocode_addresses.append(addr_str)
    
    results = []
    failed_count = 0
    failed_addresses = []
    
    for addr in tqdm(geocode_addresses, desc="  Geocoding", leave=False):
        if addr is None:
            results.append((None, None))
            continue
        
        lat, lon = None, None
        
        try:
            if geocoder_type == 'mapbox' and mapbox_token:
                lat, lon = geocode_with_mapbox(addr, mapbox_token)
            elif geocoder_type == 'census':
                lat, lon = geocode_with_census(addr)
            else:
                # Fallback to Nominatim
                gdf = gpd.tools.geocode(addr, provider='nominatim', user_agent='pharmaccess_explorer', timeout=15)
                if len(gdf) > 0:
                    geom = gdf.geometry.iloc[0]
                    if geom and hasattr(geom, 'y') and hasattr(geom, 'x'):
                        lat, lon = float(geom.y), float(geom.x)
            
            if lat and lon and -180 <= lon <= 180 and -90 <= lat <= 90:
                results.append((lat, lon))
            else:
                results.append((None, None))
                failed_count += 1
                failed_addresses.append(addr[:60])
            
            # Rate limiting
            if geocoder_type == 'mapbox':
                time.sleep(0.1)  # Mapbox allows higher rate
            elif geocoder_type == 'census':
                time.sleep(0.2)  # Census is free but slower
            else:
                time.sleep(1)  # Nominatim: 1 request per second
            
        except Exception as e:
            results.append((None, None))
            failed_count += 1
            failed_addresses.append(addr[:60])
            if failed_count <= 3:
                print(f"    Geocoding error: {str(e)[:60]}...")
    
    if failed_count > 0:
        print(f"    {failed_count} addresses failed to geocode")
        for failed_addr in failed_addresses[:5]:
            print(f"    Warning: Could not geocode: {failed_addr}...")
    
    return results

def extract_pharmacies(chunk_size=50000, max_rows=None, geocode=True, geocoder_type='census', mapbox_token=None):
    """
    Extract pharmacies from NPPES data.
    
    Args:
        chunk_size: Number of rows to process at a time
        max_rows: Maximum rows to process (None for all)
        geocode: Whether to geocode addresses
    """
    nppes_file = find_nppes_file()
    if not nppes_file:
        print("ERROR: Could not find npidata_pfile CSV file.")
        print("Please ensure the NPPES data is extracted.")
        sys.exit(1)
    
    print(f"Found NPPES file: {nppes_file}")
    if max_rows:
        print(f"⚠️  TEST MODE: Processing only first {max_rows:,} rows")
        print(f"Processing in chunks of {min(chunk_size, max_rows)} rows...")
    else:
        print(f"Processing FULL DATASET in chunks of {chunk_size:,} rows...")
        print("⚠️  This will take several hours due to geocoding rate limits")
    
    # Geocoding info
    if geocode:
        if geocoder_type == 'mapbox':
            print("Geocoding enabled (using Mapbox Geocoding API)")
            print("Note: Faster rate limits, higher accuracy")
        elif geocoder_type == 'census':
            print("Geocoding enabled (using US Census Geocoder)")
            print("Note: Free, US-only, reliable for US addresses")
        else:
            print("Geocoding enabled (using Nominatim/OpenStreetMap)")
            print("Note: Rate limited to 1 request/second")
        
        if not max_rows:
            estimated_pharmacies = 70000  # Rough estimate
            if geocoder_type == 'mapbox':
                estimated_hours = estimated_pharmacies / 600  # ~10 per second
            elif geocoder_type == 'census':
                estimated_hours = estimated_pharmacies / 300  # ~5 per second
            else:
                estimated_hours = estimated_pharmacies / 3600  # 1 per second
            print(f"Estimated time: ~{estimated_hours:.1f} hours for full dataset")
    
    # Read file in chunks
    all_pharmacies = []
    total_processed = 0
    pharmacies_found = 0
    
    try:
        # Get total file size for progress tracking
        file_size = os.path.getsize(nppes_file)
        print(f"File size: {file_size / (1024**3):.2f} GB")
        
        # Read chunks
        # If max_rows is set, limit chunk size to max_rows for efficiency
        read_chunk_size = min(chunk_size, max_rows) if max_rows else chunk_size
        
        # Only use nrows parameter if max_rows is set (for testing)
        read_kwargs = {
            'chunksize': read_chunk_size,
            'low_memory': False,
            'usecols': REQUIRED_COLS + TAXONOMY_COLS
        }
        if max_rows:
            read_kwargs['nrows'] = max_rows  # Limit rows for testing
        
        chunk_iterator = pd.read_csv(nppes_file, **read_kwargs)
        
        for chunk_num, chunk in enumerate(chunk_iterator):
            if max_rows and total_processed >= max_rows:
                break
            
            print(f"\nProcessing chunk {chunk_num + 1} ({len(chunk)} rows)...")
            
            # Filter for pharmacies
            pharmacy_rows = []
            for idx, row in chunk.iterrows():
                is_pharm, code = is_pharmacy(row)
                if is_pharm:
                    pharmacy_rows.append((idx, row, code))
            
            print(f"  Found {len(pharmacy_rows)} pharmacies in this chunk")
            
            # Prepare pharmacy data for batch processing
            pharmacy_data = []
            for idx, row, taxonomy_code in pharmacy_rows:
                # Extract pharmacy info
                name_val = row.get('Provider Organization Name (Legal Business Name)', '')
                if pd.isna(name_val):
                    name = 'Unknown Pharmacy'
                else:
                    name = str(name_val).strip()
                    if not name:
                        name = 'Unknown Pharmacy'
                
                # Build address
                full_address = build_address(row)
                
                # Extract city
                city_val = row.get('Provider Business Practice Location Address City Name', '')
                if pd.isna(city_val):
                    city = ''
                else:
                    city = str(city_val).strip()
                
                # Extract state
                state_val = row.get('Provider Business Practice Location Address State Name', '')
                if pd.isna(state_val):
                    state = ''
                else:
                    state = str(state_val).strip()
                
                # Extract street address (first line only)
                street_val = row.get('Provider First Line Business Practice Location Address', '')
                if pd.isna(street_val):
                    street_address = ''
                else:
                    street_address = str(street_val).strip()
                
                pharmacy_data.append({
                    'name': name,
                    'address': street_address,
                    'city': city,
                    'state': state,
                    'full_address': full_address,
                    'npi': str(row.get('NPI', '')),
                    'taxonomy_code': taxonomy_code
                })
            
            # Batch geocode addresses
            if geocode and pharmacy_data:
                print(f"  Geocoding addresses using {geocoder_type}...")
                addresses_to_geocode = [p['full_address'] for p in pharmacy_data]
                geocode_results = geocode_addresses_batch(addresses_to_geocode, geocoder_type, mapbox_token)
                
                # Combine pharmacy data with geocoded coordinates
                for pharm_data, (lat, lon) in zip(pharmacy_data, geocode_results):
                    if lat and lon:
                        pharmacy = {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [lon, lat]
                            },
                            "properties": {
                                "name": pharm_data['name'],
                                "chain": "",  # Could extract from name patterns later
                                "address": pharm_data['address'],
                                "city": pharm_data['city'],
                                "state": pharm_data['state'],
                                "lat": lat,
                                "lon": lon,
                                "npi": pharm_data['npi'],
                                "taxonomy_code": pharm_data['taxonomy_code'],
                                "full_address": pharm_data['full_address']
                            }
                        }
                        all_pharmacies.append(pharmacy)
                        pharmacies_found += 1
                    elif pharm_data['full_address']:
                        # Log failed geocoding
                        print(f"  Warning: Could not geocode: {pharm_data['full_address'][:60]}...")
            else:
                # No geocoding - just collect addresses
                for pharm_data in pharmacy_data:
                    if pharm_data['full_address']:
                        pharmacies_found += 1
                        print(f"  Found pharmacy (no geocoding): {pharm_data['name']} - {pharm_data['full_address'][:50]}...")
            
            total_processed += len(chunk)
            
            # Show progress
            if max_rows:
                print(f"  Total processed: {total_processed:,}/{max_rows:,} rows, Pharmacies found: {pharmacies_found}")
            else:
                # For full dataset, show percentage if we can estimate file size
                print(f"  Total processed: {total_processed:,} rows, Pharmacies found: {pharmacies_found}, With coordinates: {len(all_pharmacies)}")
            
            # Stop if we've reached max_rows (shouldn't happen with nrows, but safety check)
            if max_rows and total_processed >= max_rows:
                break
        
        print(f"\n{'='*60}")
        print(f"Extraction complete!")
        print(f"Total rows processed: {total_processed:,}")
        print(f"Pharmacies found: {pharmacies_found:,}")
        print(f"Pharmacies with coordinates: {len(all_pharmacies):,}")
        print(f"{'='*60}")
        
        # Export to GeoJSON
        if all_pharmacies:
            output_path = "../frontend/public/data/pharmacies.geojson"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            geojson = {
                "type": "FeatureCollection",
                "features": all_pharmacies
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, indent=2, ensure_ascii=False)
            
            print(f"\n✓ Exported {len(all_pharmacies)} pharmacies to {output_path}")
        else:
            print("\n⚠️  No pharmacies with coordinates found. Check geocoding.")
        
        return len(all_pharmacies)
        
    except Exception as e:
        print(f"\nError processing file: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract pharmacies from NPPES data')
    parser.add_argument('--test', '-t', action='store_true', 
                       help='Test mode: process only first 1000 rows')
    parser.add_argument('--no-geocode', action='store_true',
                       help='Skip geocoding (faster but no coordinates)')
    parser.add_argument('--chunk-size', type=int, default=50000,
                       help='Chunk size for reading CSV (default: 50000)')
    parser.add_argument('--geocoder', choices=['mapbox', 'census', 'nominatim'], default='census',
                       help='Geocoding service to use (default: census)')
    parser.add_argument('--mapbox-token', type=str, default=None,
                       help='Mapbox access token (required for mapbox geocoder)')
    
    args = parser.parse_args()
    
    max_rows = 1000 if args.test else None
    geocode = not args.no_geocode
    
    # Get Mapbox token from environment or argument
    mapbox_token = args.mapbox_token or os.getenv('MAPBOX_ACCESS_TOKEN') or os.getenv('VITE_MAPBOX_ACCESS_TOKEN')
    
    if args.test:
        print("⚠️  TEST MODE: Processing only first 1,000 rows")
    else:
        print("🚀 Processing FULL DATASET - this will process all rows in the NPPES file")
    
    if not geocode:
        print("⚠️  Geocoding disabled - pharmacies will not have coordinates")
    elif args.geocoder == 'mapbox' and not mapbox_token:
        print("⚠️  WARNING: Mapbox geocoder selected but no token found!")
        print("   Set MAPBOX_ACCESS_TOKEN environment variable or use --mapbox-token")
        print("   Falling back to Census geocoder...")
        args.geocoder = 'census'
    
    if geocode:
        print(f"Using {args.geocoder} geocoder")
        if args.geocoder == 'mapbox':
            print("  Mapbox: Fast, accurate, requires token")
        elif args.geocoder == 'census':
            print("  Census: Free, US-only, reliable for US addresses")
        else:
            print("  Nominatim: Free, worldwide, 1 req/sec limit")
    
    extract_pharmacies(
        chunk_size=args.chunk_size,
        max_rows=max_rows,
        geocode=geocode,
        geocoder_type=args.geocoder,
        mapbox_token=mapbox_token
    )

