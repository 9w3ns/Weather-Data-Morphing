import os
import json
import urllib.request


def assemble_rings(ways):
    """Join disconnected OSM 'outer' way segments into closed rings by
    chaining matching endpoints. OSM multipolygon relations split a
    district boundary into many small ways that share endpoints but are
    not stored in order, so they must be stitched together before use.
    """
    remaining = [list(w) for w in ways if len(w) >= 2]
    rings = []

    while remaining:
        chain = remaining.pop(0)
        extended = True
        while extended and chain[0] != chain[-1]:
            extended = False
            for i, seg in enumerate(remaining):
                if seg[0] == chain[-1]:
                    chain.extend(seg[1:])
                elif seg[-1] == chain[-1]:
                    chain.extend(list(reversed(seg))[1:])
                elif seg[-1] == chain[0]:
                    chain[0:0] = seg[:-1]
                elif seg[0] == chain[0]:
                    chain[0:0] = list(reversed(seg))[:-1]
                else:
                    continue
                remaining.pop(i)
                extended = True
                break
        if chain[0] != chain[-1]:
            chain.append(chain[0])
        rings.append(chain)

    return rings


def fetch_bangkok_geojson(output_path):
    print("Fetching Bangkok district boundaries from OpenStreetMap...")
    
    # Overpass API query for admin_level 6 (districts) in Bangkok
    query = """
    [out:json][timeout:60];
    area["name:en"="Bangkok"]["admin_level"="4"]->.searchArea;
    (
      relation["admin_level"="6"](area.searchArea);
    );
    out geom;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    data = query.encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data)
        req.add_header('User-Agent', 'Bot/1.0')
        req.add_header('Accept', 'application/json')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            
        features = []
        for element in result.get('elements', []):
            if element['type'] == 'relation':
                tags = element.get('tags', {})
                name_en = tags.get('name:en', tags.get('name', 'Unknown'))
                
                # Collect raw 'outer' way segments, then stitch them into
                # closed rings (OSM relations store boundaries as many
                # unordered, disconnected way fragments).
                outer_ways = []
                for member in element.get('members', []):
                    if member['type'] == 'way' and member['role'] == 'outer':
                        poly = [[node['lon'], node['lat']] for node in member.get('geometry', [])]
                        if poly:
                            outer_ways.append(poly)

                rings = [r for r in assemble_rings(outer_ways) if len(r) >= 4]

                if rings:
                    # Each ring becomes its own Polygon (no hole support needed
                    # for admin boundaries here); a MultiPolygon covers districts
                    # split into multiple parts (e.g. exclaves).
                    polygons = [[ring] for ring in rings]
                    feature = {
                        "type": "Feature",
                        "properties": {
                            "District": name_en,
                            "admin_level": tags.get('admin_level')
                        },
                        "geometry": {
                            "type": "Polygon" if len(polygons) == 1 else "MultiPolygon",
                            "coordinates": polygons[0] if len(polygons) == 1 else polygons
                        }
                    }
                    features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
            
        print(f"Successfully saved GeoJSON with {len(features)} districts to {output_path}")
        return [f['properties']['District'] for f in features]
        
    except Exception as e:
        print(f"Failed to fetch GeoJSON: {e}")
        return []

if __name__ == "__main__":
    # NOTE: this only (re)fetches district boundary geometry. UHI data
    # (data/gis/bangkok_uhi_data.csv) is generated separately by
    # data/fetch_uhi_lst.py + data/fetch_uhi_lcz.py + data/merge_uhi_data.py
    # (see docs/uhi_data_sourcing_plan.md) -- running this script does NOT
    # touch that file.
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data', 'gis')
    os.makedirs(data_dir, exist_ok=True)

    geojson_path = os.path.join(data_dir, 'bangkok_districts.geojson')
    fetch_bangkok_geojson(geojson_path)
