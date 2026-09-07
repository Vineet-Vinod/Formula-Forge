"""Fetch consultation sheets into build/, using the layout's recorded georeferencing.

uv run --no-sync python tools/blender/tracks/fetch_monza_layout_references.py
The game and its exporter do not depend on network access or these images.
"""
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'assets/tracks/monza'


def fetch():
    layout=json.loads((SOURCE/'layout.json').read_text())
    survey=json.loads((SOURCE/'survey.json').read_text())
    lon,latitude=survey['origin_wgs84_lon_lat']
    lat=math.radians(latitude); e2=.00669437999014
    factor=survey['uniform_plan_scale']
    east=math.pi/180*6378137/math.sqrt(1-e2*math.sin(lat)**2)*math.cos(lat)*factor
    north=math.pi/180*6378137*(1-e2)/(1-e2*math.sin(lat)**2)**1.5*factor
    service=next(s['url'] for s in layout['sources'] if s['id']=='AGEA-2024')
    output=ROOT/'build/monza_layout_references';output.mkdir(parents=True,exist_ok=True)
    for name,region in layout['reference_regions'].items():
        x0,y0,x1,y1=region['bounds_xy']
        width,height=region['inspection_size']
        url=region.get('request_url') or service+'?'+urlencode(dict(
            SERVICE='WMS',VERSION='1.1.1',REQUEST='GetMap',LAYERS='0',STYLES='',
            SRS='EPSG:4326',BBOX=f'{lon+x0/east},{latitude+y0/north},{lon+x1/east},{latitude+y1/north}',
            WIDTH=width,HEIGHT=height,FORMAT='image/png'))
        data=urlopen(url,timeout=90).read()
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError(f'{name}: WMS did not return a PNG')
        (output/(name+'.png')).write_bytes(data)
        print(name,output/(name+'.png'),flush=True)


if __name__=='__main__':fetch()
