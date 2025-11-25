import requests
import json

def get_ip_geolocation():
    try:
        response = requests.get('https://ipinfo.io/')
        data = response.json()
        loc = data.get('loc', '').split(',')
        if len(loc) == 2:
            latitude = float(loc[0])
            longitude = float(loc[1])
            city = data.get('city', 'Unknown')
            region = data.get('region', 'Unknown')
            return latitude, longitude, city, region
        else:
            return None, None, None, None
    except requests.exceptions.RequestException:
        print("Could not connect to geolocation service.")
        return None, None, None, None

if __name__ == "__main__":
    lat, lon, city, region = get_ip_geolocation()
    if lat is not None and lon is not None:
        print(json.dumps({"latitude": lat, "longitude": lon, "city": city, "region": region}, ensure_ascii=False))
    else:
        print("Could not determine IP-based location.")