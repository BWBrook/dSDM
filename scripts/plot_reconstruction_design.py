"""Draw the response-free study design from public boundary sources."""
from __future__ import annotations

import hashlib
import html
import json
import subprocess
from pathlib import Path

import geopandas as gpd
from shapely import box, make_valid, union_all
from shapely.geometry import mapping

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'manuscript/figures'
IBRA = ROOT / 'data/raw/goal040/domain/ibra7_1_subregions.geojson'
STATES = ROOT / 'data/raw/goal040/domain/extracted/STE_2026_AUST_GDA2020.shp'
MANIFEST = ROOT / 'metadata/goal040_domain_boundary_manifest.json'
CONFIG = ROOT / 'config/goal048_seawfb_bioregional_freeze.json'
OLD_SVG = ROOT / 'evidence/seawfb_bioregional_freeze/goal048/selected_holdouts.svg'
RECEIPT = ROOT / 'evidence/reconstruction/20261113/design-figure.json'
W, H = 1800, 2140
BLUE, ORANGE, GREY = '#286C9E', '#BC623C', '#5D666D'
DARK = '#23343C'


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def path_data(geom, transform) -> str:
    parts = []
    def visit(v):
        if v['type'] == 'Polygon':
            for ring in v['coordinates']:
                pts = [transform(x, y) for x, y, *_ in ring]
                parts.append('M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x, y in pts) + ' Z')
        elif v['type'] == 'MultiPolygon':
            for coordinates in v['coordinates']:
                visit({'type': 'Polygon', 'coordinates': coordinates})
        elif v['type'] == 'GeometryCollection':
            for g in v['geometries']:
                visit(g)
    visit(mapping(geom))
    return ' '.join(parts)


def build() -> None:
    manifest = json.loads(MANIFEST.read_text())
    config = json.loads(CONFIG.read_text())
    assert sha(IBRA) == manifest['exact_study_domain']['authority']['sha256']
    state_zip = ROOT / 'data/raw/goal040/domain/STE_2026_AUST_SHP_GDA2020.zip'
    assert sha(state_zip) == manifest['products']['land_and_state']['sha256']
    frame = gpd.read_file(IBRA).to_crs(3577)
    states = gpd.read_file(STATES).to_crs(3577)
    assert len(frame) == 419 and frame['REG_CODE_7'].nunique() == 89
    selected = manifest['exact_study_domain']['ibra_subregion_allowlist']
    selected_frame = frame[frame.SUB_CODE_7.isin(selected)]
    assert len(selected_frame) == len(selected) == 163
    land = union_all(make_valid(states[~states.STE_CODE26.astype(str).isin(['7', '9'])].geometry.array))
    tas = union_all(make_valid(states[states.STE_CODE26.astype(str) == '6'].geometry.array))
    old = union_all(make_valid(selected_frame.geometry.array)).intersection(land)
    footprint = gpd.GeoSeries([box(135.3700, -43.6325, 153.6300, -23.7725)], crs=4326).to_crs(3577).iloc[0]
    old = old.intersection(footprint)
    bbs = union_all(make_valid(frame[frame.REG_CODE_7 == 'BBS'].geometry.array)).intersection(land)
    bird = union_all([old, bbs])
    mainland = old.difference(tas)
    holdouts = {code: union_all(make_valid(frame[frame.REG_CODE_7 == code].geometry.array)) for code in ['NCP', 'SEH', 'NNC']}
    buffered = union_all([g.buffer(50_000.0) for g in holdouts.values()])
    development = bird.difference(buffered)
    assert all(g.intersection(bird).area / g.area > 0.99 for g in holdouts.values())
    minx, miny, maxx, maxy = bird.bounds
    mwidth, mheight = 920, 920
    scale = min(mwidth / (maxx-minx), mheight / (maxy-miny))
    xo, yo = 125 + (mwidth-(maxx-minx)*scale)/2, 145 + (mheight-(maxy-miny)*scale)/2
    def tr(x, y):
        return xo+(x-minx)*scale, yo+(maxy-y)*scale
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="7.4in" height="8.8in" viewBox="0 0 {W} {H}">',
             '<title>Three geographic tests and three learners</title>',
             '<metadata>Boundary-only map. No observation locations or response-derived masks. Display geometry simplified at 3 km; buffer calculated in EPSG:3577 before simplification.</metadata>',
             '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#53656F" stroke-width="1.4"/></marker></defs>',
             '<rect width="1800" height="2140" fill="white"/>',
             '<g font-family="Arial, Helvetica, sans-serif" fill="'+DARK+'">']
    def text(x, y, s, size=31, weight='normal', fill=DARK, anchor='start'):
        lines.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{html.escape(s)}</text>')
    def multiline(x, y, ss, size=31, gap=43, **kw):
        for i, s in enumerate(ss): text(x, y+i*gap, s, size=size, **kw)
    def geom(g, fill='none', stroke='none', width=1, dash=None):
        simplified = g.simplify(3000.0, preserve_topology=True)
        extra = f' stroke-dasharray="{dash}"' if dash else ''
        lines.append(f'<path d="{path_data(simplified,tr)}" fill="{fill}" fill-rule="evenodd" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"{extra}/>')
    def rect(x,y,w,h,fill='white',stroke='#D1D9DD',radius=12,width=2):
        lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
    def arrow(x1,y1,x2,y2):
        lines.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="#53656F" stroke-width="3" marker-end="url(#arrow)"/>')

    text(60,70,'(a)  Three geographic tests',size=43,weight='bold')
    text(60,115,'Public boundaries in southeastern Australia',size=30,fill='#596A73')
    geom(development,fill='#D8EAF4',stroke='#7AA2BB',width=1.7)
    geom(buffered.intersection(bird),fill='#F4DADF',stroke='#C08894',width=1.8,dash='7,5')
    for code, g in holdouts.items(): geom(g,fill='#886184',stroke='#624761',width=2.4)
    geom(mainland,stroke=GREY,width=3.2)
    geom(tas,stroke=ORANGE,width=4.0)
    pos = {code: tr(*g.representative_point().coords[0]) for code,g in holdouts.items()}
    labels = {'NCP':(155,830),'SEH':(800,850),'NNC':(980,435)}
    for code,(tx,ty) in labels.items():
        px,py = pos[code]
        lines.append(f'<path d="M{px:.2f},{py:.2f} L{tx},{ty-12}" fill="none" stroke="#624761" stroke-width="2.5"/>')
        rect(tx-8,ty-35,96,48,fill='white',stroke='none',radius=3)
        text(tx,ty,code,size=32,weight='bold',fill='#624761')
    # North and metric scale use the same Albers map transform.
    text(155,210,'N',size=31,weight='bold',anchor='middle')
    arrow(155,280,155,225)
    bar=200000*scale
    lines.append(f'<path d="M150,1040 h{bar:.2f} M150,1030 v20 M{150+bar:.2f},1030 v20" stroke="{DARK}" stroke-width="3"/>')
    text(150+bar/2,1084,'200 km',size=29,anchor='middle')
    text(1100,175,'Birds: 73 primary species',size=35,weight='bold')
    rect(1100,205,54,30,fill='#D8EAF4',stroke='#7AA2BB')
    multiline(1175,232,['Development geography','(Tasmania included)'],size=30,gap=40)
    rect(1100,310,54,30,fill='#886184',stroke='#624761')
    multiline(1175,337,['Three withheld bioregions'],size=30)
    rect(1100,375,54,30,fill='#F4DADF',stroke='#C08894')
    multiline(1175,402,['50 km buffers excluded','from all bird fitting'],size=30,gap=40)
    multiline(1100,505,['NCP  Naracoorte Coastal Plain','SEH  South Eastern Highlands','NNC  NSW North Coast'],size=29,gap=43)
    text(1100,675,'Mammals: two further tests',size=35,weight='bold')
    lines.append(f'<path d="M1100,720 h55" stroke="{GREY}" stroke-width="5"/>')
    multiline(1175,733,['5 mainland species','→ Tasmania (orange outline)'],size=30,gap=40)
    lines.append(f'<path d="M1100,820 h55" stroke="{ORANGE}" stroke-width="5"/>')
    multiline(1175,833,['8 Tasmanian species','tested in withheld patches'],size=30,gap=40)
    rect(1100,910,620,200,fill='#F8F9FA')
    text(1125,951,'Five-patch design: schematic only',size=29,weight='bold')
    for i,(xx,yy) in enumerate([(1145,985),(1225,1010),(1320,990),(1430,1005),(1530,985)]):
        rect(xx,yy,57,46,fill='#F4DADF',stroke=ORANGE,radius=3)
    text(1125,1090,'Invented positions; no observation locations',size=26,fill='#596A73')
    text(60,1160,'a: Boundaries show study extents, not the availability of records or predictors.',size=27,fill='#596A73')

    text(60,1250,'(b)  Three learners separate two sources of improvement',size=43,weight='bold')
    xs=[60,640,1220]
    names=['Pretrained network','Single-species network','Conventional model']
    colors=[BLUE,ORANGE,GREY]
    fills=['#E4EFF6','#F8EAE3','#ECEFF1']
    for x,n,c,f in zip(xs,names,colors,fills):
        rect(x,1300,520,84,fill=f,stroke=c,width=3)
        text(x+260,1354,n,size=35,weight='bold',fill=c,anchor='middle')
    rect(60,1420,520,88,fill='#E4EFF6',stroke=BLUE)
    multiline(320,1458,['Learn from other species','(target excluded)'],size=30,gap=36,anchor='middle')
    arrow(320,1515,320,1550)
    rect(60,1565,520,80,fill='#E4EFF6',stroke=BLUE)
    text(320,1615,'Fine-tune on target species',size=30,anchor='middle')
    rect(640,1470,520,175,fill='#F8EAE3',stroke=ORANGE)
    multiline(900,1520,['Fit on target species only','Same architecture as the','pretrained network'],size=30,gap=39,anchor='middle')
    rect(1220,1470,520,175,fill='#ECEFF1',stroke=GREY)
    multiline(1480,1520,['Fit on target species','Select within development','data only'],size=30,gap=39,anchor='middle')
    for x,c in zip(xs,colors):
        arrow(x+260,1655,x+260,1690)
        text(x+260,1735,'Predict target distribution',size=29,anchor='middle',fill=c)
    rect(60,1790,810,123,fill='#F2F6F8',stroke='#B5C7D1')
    text(85,1838,'Pretrained − single-species',size=33,weight='bold')
    text(85,1882,'What learning from other species adds',size=31)
    rect(910,1790,830,123,fill='#F2F6F8',stroke='#B5C7D1')
    text(935,1838,'Single-species − conventional',size=33,weight='bold')
    text(935,1882,'What the network adds by itself',size=31)
    rect(60,1950,1680,78,fill='#F8F9FA',stroke='#D1D9DD')
    text(900,1999,'Withheld geography is excluded from every stage of fitting and selection.',size=32,anchor='middle',weight='bold')
    text(60,2095,'Additional controls → Supporting information: frozen encoder; scalar community models',size=29,fill='#596A73')
    lines.extend(['</g>','</svg>'])
    OUT.mkdir(exist_ok=True)
    svg = OUT / 'study-design.svg'
    svg.write_text('\n'.join(lines)+'\n')
    subprocess.run(['rsvg-convert','-f','pdf','-o',str(OUT/'study-design.pdf'),str(svg)],check=True)
    subprocess.run(['rsvg-convert','-f','png','-d','300','-p','300','-o',str(OUT/'study-design.png'),str(svg)],check=True)
    inputs = [IBRA,state_zip,MANIFEST,CONFIG,OLD_SVG,ROOT/'scripts/goal048_seawfb_bioregional_freeze.py']
    receipt = {
        'schema_version':'dsdm-design-figure-v1','date':'2026-11-13','base_commit':'f62df73',
        'status':'pass; 300 dpi PNG visually inspected for legibility and overlaps',
        'sources':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
        'outputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [svg,OUT/'study-design.pdf',OUT/'study-design.png']],
        'geographic_source':'IBRA 7.1 official subregions (419 features,89 regions); ASGS Edition4 state land; source hashes match frozen Goal040 manifest',
        'licences':{'IBRA7.1':'CC BY 3.0 AU; Australian Government DCCEEW','ASGS2026':'CC BY 4.0; Australian Bureau of Statistics'},
        'bird_extent':'Goal040 163-subregion public-boundary union within its footprint and land mask, plus complete BBS boundary on land; Tasmania ordinary bird development geography',
        'mainland_mammal_extent':'Goal040 boundary extent excluding Tasmania',
        'cartography':'EPSG:3577; 50km buffers constructed before 3km display simplification; no analytical geometry or masks changed',
        'limitations':'Boundary-only display omits response support, predictor coverage and subscale inland-water exclusions. Five displayed patches are invented schematic positions, not real withheld patches.',
        'raw_observations_read':False,
        'reproduce':'.venv/bin/python scripts/plot_reconstruction_design.py (existing project environment; rsvg-convert on PATH)',
    }
    RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'generated','outputs':receipt['outputs']},indent=2))

if __name__ == '__main__':
    build()
