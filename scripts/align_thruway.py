"""Split uploaded linework against existing frequency corridors; flag unmatched geometry."""
import json, math
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads((ROOT/p).read_text())
service=read('data/passenger_rail_timeline.geojson'); upload=read('data/thruway_routes.geojson')
bus=[f for f in service['features'] if f['properties'].get('mode')=='thruway_bus']
def xy(coords):
 a=np.array(coords,float);return a*np.array([88000.,111000.])
def sample(line,step=200):
 out=[]
 for a,b in zip(xy(line)[:-1],xy(line)[1:]):
  n=max(1,int(np.ceil(np.linalg.norm(b-a)/step)));out.extend(a+(b-a)*np.arange(n)[:,None]/n)
 out.append(xy(line)[-1]);return out
pieces={i:[] for i in range(len(bus))};unknown=[];report=[]
for f in upload['features']:
 route=f['properties']['route'];match='Route 1' if route=='Route 1/1C' else route
 candidates=[i for i,b in enumerate(bus) if b['properties']['route']==match and match!='Route 19']
 points=[];owners=[]
 for i in candidates:
  pts=sample(bus[i]['geometry']['coordinates']);points.extend(pts);owners.extend([i]*len(pts))
 tree=cKDTree(points) if points else None
 for line in f['geometry']['coordinates']:
  # Insert all segment-boundary projections into each uploaded edge before assigning.
  boundaries=[c for i in candidates for c in [bus[i]['geometry']['coordinates'][0],bus[i]['geometry']['coordinates'][-1]]]
  bp=xy(boundaries) if boundaries else np.empty((0,2))
  current=[];last=None
  def flush():
   if len(current)>1:
    if last is None:unknown.append({'type':'Feature','properties':dict(f['properties'],frequency_status='unmatched'),'geometry':{'type':'LineString','coordinates':current.copy()}})
    else:pieces[last].append(current.copy())
  for a,b in zip(line[:-1],line[1:]):
   aa,bb=xy([a,b]);v=bb-aa;vv=float(v@v)
   if not vv:continue
   ts=[0.,1.]
   if len(bp):
    t=((bp-aa)@v)/vv;dist=np.linalg.norm(bp-(aa+np.clip(t,0,1)[:,None]*v),axis=1)
    ts.extend(t[(t>0)&(t<1)&(dist<3000)].tolist())
   # Additional samples keep distant or branching linework unassigned.
   ts.extend(np.arange(1,max(1,int(np.ceil(math.sqrt(vv)/250))))/max(1,int(np.ceil(math.sqrt(vv)/250))))
   ts=sorted(set(ts))
   for t0,t1 in zip(ts[:-1],ts[1:]):
    start=(np.array(a)+(np.array(b)-a)*t0).tolist();end=(np.array(a)+(np.array(b)-a)*t1).tolist()
    if tree:
     distance,k=tree.query(aa+v*(t0+t1)/2);owner=owners[k]
    else:owner=None
    if owner!=last or not current:
     flush();current=[start,end];last=owner
    else:current.append(end)
  flush()
for i,f in enumerate(bus):
 p=f['properties']
 if pieces[i]:
  matched_points=[point for line in pieces[i] for point in sample(line,500)]
  distances=cKDTree(matched_points).query(sample(f['geometry']['coordinates'],500))[0]
  coverage=round(float(np.mean(distances<=3000))*100,1)
 else: coverage=0
 p['geometry_coverage_pct']=coverage
 report.append({'route':p['route'],'segment':p['segment'],'matched_parts':len(pieces[i]),'corridor_coverage_pct':coverage,'status':('matched' if coverage>=95 else 'partial match') if pieces[i] else 'no compatible uploaded route'})
 if pieces[i]:
  f['geometry']={'type':'MultiLineString','coordinates':pieces[i]};p['geometry_source']='Uploaded thruway_routes_merged.shp, split at projected frequency boundaries';p['frequency_note']='Existing segment frequencies attached by route and spatial corridor; boundaries projected onto uploaded linework. Geometry may differ from the original corridor; coverage is reported separately.';p['geometry_alignment']='matched'
 else:p['geometry_alignment']='unmatched';p['frequency_note']='No matching uploaded geometry. Frequency retained for chart and totals only.'
# Keep every original frequency record for unchanged chart and route totals.
# Publish only geometry overrides; original service properties remain authoritative.
output=[]
for f in bus:
 p=f['properties'];g=f['geometry'] if p['geometry_alignment']=='matched' else None
 if g:
  lines=[]
  for line in g['coordinates']:
   keep=[line[0]]
   for k in range(1,len(line)-1):
    a,b,c=xy([keep[-1],line[k],line[k+1]]);v=c-a
    if np.linalg.norm(v)==0 or abs(np.cross(v,b-a))/np.linalg.norm(v)>.01:keep.append(line[k])
   keep.append(line[-1]);lines.append([[round(x,6),round(y,6)] for x,y in keep])
  g={'type':'MultiLineString','coordinates':lines}
 output.append({'type':'Feature','properties':{k:p[k] for k in ['route','segment','geometry_alignment','geometry_coverage_pct','frequency_note']},'geometry':g})
(ROOT/'data/thruway_frequency_geometry.geojson').write_text(json.dumps({'type':'FeatureCollection','features':output},separators=(',',':')))
(ROOT/'data/thruway_unmatched_geometry.geojson').write_text(json.dumps({'type':'FeatureCollection','features':unknown},separators=(',',':')))
(ROOT/'data/thruway_alignment_report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2));print('Unmatched geometry parts:',len(unknown))
