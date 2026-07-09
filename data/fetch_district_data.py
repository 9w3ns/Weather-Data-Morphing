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

def create_mock_csv(districts, output_path):
    print("Creating dataset CSV...")
    
    # Based on the World Bank report text
    high_uhi = ["Khlong San", "Sathon", "Din Daeng", "Pom Prap Sattru Phai", "Samphanthawong", "Pathum Wan", "Bang Rak", "Ratchathewi", "Phaya Thai"]
    low_uhi = ["Don Mueang", "Sai Mai", "Nong Chok", "Bang Khen", "Lat Krabang", "Min Buri", "Khlong Sam Wa"]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("District,UHI_Risk,Death_Risk_Index,Dominant_LCZ\n")
        
        if not districts:
            # Fallback list if OSM fails
            districts = high_uhi + low_uhi + ["Bangkok Noi", "Bangkok Yai", "Chatuchak", "Thon Buri"]
            
        for dist in districts:
            # Clean up OSM names (e.g. "Khet Pathum Wan" -> "Pathum Wan")
            clean_name = dist.replace("Khet ", "").strip()
            
            # Assign data based on report text
            if any(h.lower() in clean_name.lower() for h in high_uhi):
                uhi_risk = "Severe"
                death_risk = "1.035"
                lcz = "LCZ 1 (Compact high-rise)"
            elif any(l.lower() in clean_name.lower() for l in low_uhi):
                uhi_risk = "Low"
                death_risk = "1.022"
                lcz = "LCZ 6 (Open low-rise)"
            else:
                uhi_risk = "Medium"
                death_risk = "1.028"
                lcz = "LCZ 3 (Compact low-rise)"
                
            f.write(f'"{clean_name}","{uhi_risk}",{death_risk},"{lcz}"\n')
            
    print(f"Successfully saved CSV dataset to {output_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data', 'gis')
    os.makedirs(data_dir, exist_ok=True)
    
    geojson_path = os.path.join(data_dir, 'bangkok_districts.geojson')
    csv_path = os.path.join(data_dir, 'bangkok_uhi_data.csv')
    
    districts = fetch_bangkok_geojson(geojson_path)
    create_mock_csv(districts, csv_path)
