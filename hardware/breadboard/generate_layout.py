"""Generate/review FaroNet breadboard plans from an explicit hole model.

No third-party generator is executed. A–E and F–J clips are separate; all
four power rails are modelled split at 25/26 and explicitly bridged.
The validation checks copper continuity, not component dynamics or optics.
"""
from pathlib import Path
import json,html,base64,collections,re,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
REF=HERE/'circuit-reference.json'
CANON=json.loads(REF.read_text())
CP={}
for c in CANON['components']:
 CP.setdefault(c['ref'],dict(c,pins={}));CP[c['ref']]['pins'].update(c['pins'])
COL={'5V':'#bc3f25','3V3':'#7945ae','GND':'#425261','VBIAS':'#986300','VTH':'#986300','SENSE':'#986300','OPT_RX':'#007e83','TX':'#1164a4','LED_TX':'#208047','LED_RX':'#a37400','PANIC':'#aa467d','RGB_R':'#b3464d','RGB_G':'#208047','RGB_B':'#275db0','RGB_R_A':'#b3464d','RGB_G_A':'#208047','RGB_B_A':'#275db0'}
def esc(s):return html.escape(str(s),quote=True)
def color(n):return COL.get(n,'#3e687b')
P=22;X0=730
ROW={r:185+i*P for i,r in enumerate('abcde')}
ROW.update({r:ROW['e']+3*P+i*P for i,r in enumerate('fghij')})
RY={'T3':95,'TG':117,'B5':495,'BG':517}
W,H=2500,1420

def xy(a):
 if a.startswith('PI:'):
  n=int(a.split(':')[1]);return (278 if n%2 else 320),180+((n-1)//2)*25
 if a.startswith('EXT:'):return EXTXY[a]
 if ':' in a:
  r,i=a.split(':');i=int(i);offset=i-1+(i-1)//5+(1 if i>25 else 0)
  return X0+33+offset*P,RY[r]
 return X0+(int(a[1:])-1)*P,ROW[a[0]]
EXTXY={}
class UF:
 def __init__(self):self.p={}
 def root(self,a):
  self.p.setdefault(a,a)
  if self.p[a]!=a:self.p[a]=self.root(self.p[a])
  return self.p[a]
 def join(self,a,b):self.p[self.root(a)]=self.root(b)

class Layout:
 def __init__(self,rgb):self.rgb=rgb;self.parts=[];self.wires=[];self.claims={};self.nets={};self.checks=[]
 def part(self,ref,pins,stage):
  assert ref in CP
  assert set(pins)==set(CP[ref]['pins']),(ref,set(pins),set(CP[ref]['pins']))
  for p,a in pins.items():self.claim(a,ref+'.'+p,CP[ref]['pins'][p])
  self.parts.append(dict(ref=ref,value=CP[ref]['value'],pins=pins,stage=stage))
 def claim(self,a,owner,net):
  assert ((re.fullmatch(r'[a-j](?:[1-9]|[1-5][0-9]|6[0-3])',a) is not None)
   or (re.fullmatch(r'(?:T3|TG|B5|BG):(?:[1-9]|[1-4][0-9]|50)',a) is not None)
   or (re.fullmatch(r'PI:(?:[1-9]|[1-3][0-9]|40)',a) is not None)
   or a in EXTXY),'Dirección inválida: '+a
  if a.startswith('EXT:') and a in self.claims:
   assert self.nets[a]==net
   self.claims[a]+=' + '+owner;return
  assert a not in self.claims,(a,owner,self.claims.get(a))
  self.claims[a]=owner;self.nets[a]=net
 def wire(self,a,b,n,stage,why,route=None):
  for h in [a,b]:self.claim(h,'W'+str(len(self.wires)+1).zfill(2),n)
  self.wires.append(dict(id='W'+str(len(self.wires)+1).zfill(2),a=a,b=b,net=n,stage=stage,why=why,route=route))
 def source(self,contact,a,stage='power'):
  pin=next(p for p in CANON['pins'] if p[0]==contact);self.wire('PI:'+str(pin[1]),a,pin[3],stage,f'Pi físico {pin[1]} · {pin[2]} · futuro J1.{contact}')
 def validate(self):
  uf=UF()
  for c in range(1,64):
   for bank in ['abcde','fghij']:
    for r in bank:uf.join(bank[0]+str(c),r+str(c))
  for rail in RY:
   for lo,hi in [(1,25),(26,50)]:
    for i in range(lo,hi+1):uf.join(f'{rail}:{lo}',f'{rail}:{i}')
  for w in self.wires:uf.join(w['a'],w['b'])
  # The tactile switch duplicates each contact across two physical legs.
  # Model those permanent joins, but never the momentary closure at rest.
  for p in self.parts:
   for a,b in CP[p['ref']].get('internal_connections',[]):uf.join(p['pins'][a],p['pins'][b])
  roots=collections.defaultdict(set);netroots=collections.defaultdict(set)
  for a,n in self.nets.items():roots[uf.root(a)].add(n);netroots[n].add(uf.root(a))
  shorts={r:ns for r,ns in roots.items() if len(ns)>1}
  assert not shorts,shorts
  assert all(len(v)==1 for v in netroots.values()),{n:v for n,v in netroots.items() if len(v)>1}
  expected={c['ref']+'.'+p for c in CANON['components'] if self.rgb or c['block']!='RGB' for p in c['pins']}
  actual={p['ref']+'.'+pin for p in self.parts for pin in p['pins']}
  actual|={f'J1.{p[0]}' for p in CANON['pins'] if self.rgb or p[0]<=8}
  assert actual==expected,(actual^expected)
  for p in self.parts:
   if p['ref'].startswith('R') and p['ref']!='RV1':
    a,b=p['pins'].values();assert uf.root(a)!=uf.root(b),'Resistencia puenteada '+p['ref']
  assert uf.root('PI:1')!=uf.root('PI:2')!=uf.root('PI:6')
  for pin in [11,13,15,16,18]+([29,31,33] if self.rgb else []):assert uf.root('PI:'+str(pin))!=uf.root('PI:2')
  for p in self.parts:
   if p['ref'] in ['U1','U2']:
    for term,a in p['pins'].items():
     if CP[p['ref']]['pins'][term].startswith('NC_'):
      assert sum(uf.root(h)==uf.root(a) for h in self.claims)==1,'Clip NC ocupado: '+a
  self.hole_nets={}
  for a in uf.p:
   ns=roots.get(uf.root(a));
   if ns:self.hole_nets[a]=next(iter(ns))
  self.copper_roots={a:uf.root(a) for a in uf.p}
  s=next(p for p in self.parts if p['ref']=='S1')['pins']
  assert uf.root(s['1'])==uf.root(s['2']) and uf.root(s['3'])==uf.root(s['4'])
  assert uf.root(s['1'])!=uf.root(s['3']),'Botón puenteado en reposo'
  rv=next(p for p in self.parts if p['ref']=='RV1')['pins']
  assert len({uf.root(a) for a in rv.values()})==3,'Terminales del trimpot puenteados'
  self.checks=['830 agujeros: 630 de señal + 200 de alimentación','Un solo terminal/punta por agujero','Cada red tiene continuidad por clips, jumpers y parejas internas S1','Ningún clip une redes distintas','5 V, 3,3 V y GND separados','Ningún GPIO unido por cobre a 5 V','Resistencias no puenteadas por clips','S1 abierto en reposo; sus dos parejas internas modeladas','Tres terminales de RV1 en redes distintas','Pines no usados de IC definidos o aislados','Todos los terminales del esquema presentes']
  return self

def make(rgb,*,horizontal_trimpot=False):
 l=Layout(rgb)
 # Power, including all split-rail bridges; one local ground.
 l.source(1,'T3:2');l.source(2,'B5:2');l.source(3,'TG:2')
 l.wire('TG:4','BG:4','GND','power','Unir solo GND superior e inferior; no insertar en T3:4 ni B5:4',route=[xy('TG:4'),(xy('TG:4')[0],140),(555,140),(555,560),(xy('BG:4')[0],560),xy('BG:4')])
 for r,n in [('T3','3V3'),('TG','GND'),('B5','5V'),('BG','GND')]:l.wire(r+':25',r+':26',n,'power','Puente entre mitades del mismo riel; comprobar continuidad')
 # Mandatory indicator LEDs.
 l.part('R10',{'1':'j5','2':'d5'},'leds');l.part('D2',{'A':'c5','K':'c6'},'leds');l.wire('a6','TG:8','GND','leds','Cátodo del verde a GND');l.source(6,'h5','leds')
 l.part('R11',{'1':'j9','2':'d9'},'leds');l.part('D3',{'A':'c9','K':'c10'},'leds');l.wire('a10','TG:10','GND','leds','Cátodo del amarillo a GND');l.source(7,'h9','leds')
 # DTS-6 candidate, rotated 90 degrees clockwise from datasheet top view.
 # 6.5 x 4.5 mm leads require gentle adjustment to the 7.62 x 5.08 mm grid.
 l.part('S1',{'1':'e16','2':'f16','3':'e14','4':'f14'},'panic')
 l.wire('b16','TG:14','GND','panic','Retorno del pulsador')
 l.part('R12',{'1':'b11','2':'b14'},'panic');l.wire('a11','T3:10','3V3','panic','Alimentación del pull-up de pánico');l.source(8,'d14','panic')
 # Comparator DIP8, notch RIGHT, pin1 at e38.
 l.part('U1',{'4 GND':'e35','3 IN1+':'e36','2 IN1−':'e37','1 OUT1':'e38','5 IN2+':'f35','6 IN2−':'f36','7 OUT2':'f37','8 VCC':'f38'},'rx')
 l.wire('a35','TG:28','GND','rx','U1.4 GND');l.wire('j35','BG:28','GND','rx','U1.5 entrada no usada a GND')
 l.wire('j38','B5:31','5V','rx','U1.8 alimentación 5 V')
 l.part('C2',{'1':'i38','2':'i40'},'rx');l.wire('j40','d35','GND','rx','C2 a U1.4 por retorno corto')
 l.part('R5',{'1':'T3:30','2':'a38'},'rx');l.source(5,'c38','rx')
 l.part('R6',{'1':'d38','2':'e44'},'rx')
 # PT333 at the east optical front; long lead 1 E, short lead 2 C.
 l.part('Q2',{'E':'c60','C':'c61'},'rx');l.wire('a60','TG:49','GND','rx','PT333 emisor a tierra en el frente óptico');l.wire('b41','b37','SENSE','rx','Nodo local SENSE / R4 a U1.2')
 l.wire('b61','c41','SENSE','rx','Colector Q2 del frente óptico al nodo SENSE local; mantener corto',route=[xy('b61'),(xy('b61')[0],169),(xy('c41')[0],169),xy('c41')])
 l.part('R4',{'1':'a47','2':'a41'},'rx')
 l.part('R8',{'1':'c50','2':'c46'},'rx');l.wire('a50','T3:40','3V3','rx','Parte superior del divisor VBIAS')
 l.part('R9',{'1':'d46','2':'d53'},'rx');l.wire('a53','TG:42','GND','rx','Parte inferior del divisor')
 l.part('C3',{'1':'e46','2':'e48'},'rx');l.wire('a48','TG:38','GND','rx','C3 filtro VBIAS')
 l.wire('c47','a46','VBIAS','rx','Extensión de la red VBIAS sin compartir agujeros ocupados')
 l.wire('j36','b46','VBIAS','rx','U1.6 a VBIAS (entrada no usada)')
 # Upright RM063-like trimmer pictured by user: ends 5 mm, wiper offset 2.5 mm.
 # Alternative horizontal RM065: move only pin 2 from c44 to b44 after measurement.
 l.part('RV1',{'1 extremo':'d43','2 cursor':'b44' if horizontal_trimpot else 'c44','3 extremo':'d45'},'rx')
 l.wire('b47','b43','VBIAS','rx','Extremo 1 del trimpot a VBIAS; confirmar cursor antes de montar')
 l.wire('a45','TG:36','GND','rx','Retorno trimpot');l.wire('a44','a36','VTH','rx','Cursor e histéresis a U1.3; b44 queda libre para variante RM065')
 # TX: EBC as indicated by the team, flat face toward j.
 l.part('Q1',{'E':'j55','B':'j56','C':'j57'},'tx')
 l.part('R2',{'1':'f52','2':'f56'},'tx');l.source(4,'j52','tx')
 l.part('R3',{'1':'g56','2':'g51'},'tx');l.wire('g55','i51','GND','tx','Emisor Q1 y pulldown a la misma tierra');l.wire('f51','BG:41','GND','tx','Retorno del driver IR')
 l.part('D1',{'A':'i60','K':'i61'},'tx');l.part('R1',{'1':'B5:48','2':'j60'},'tx');l.wire('g57','j61','IR_K','tx','Colector Q1 a cátodo IR')
 l.part('C1',{'+':'B5:44','−':'BG:46'},'power')
 if rgb:
  l.part('DL1',{'L1':'d23','L2':'d24','L3':'d25','L4':'d26'},'rgb')
  l.part('R13',{'1':'g18','2':'g21'},'rgb');l.source(9,'j18','rgb')
  l.part('R14',{'1':'g23','2':'g26'},'rgb');l.source(10,'j23','rgb')
  l.part('R15',{'1':'g28','2':'g31'},'rgb');l.source(11,'j28','rgb')
  for a,b,n,why in [('i21','e23','RGB_R_A','R13 a L1 rojo'),('i26','e25','RGB_G_A','R14 a L3 verde'),('i31','e26','RGB_B_A','R15 a L4 azul')]:l.wire(a,b,n,'rgb',why)
  l.wire('e24','TG:20','GND','rgb','L2 cátodo común a GND',route=[xy('e24'),(1236,286),(1346,286),(1346,138),(xy('TG:20')[0],138),xy('TG:20')])
 return l.validate()

A=make(False);B=make(True)
print('Validated holes/nets:',[(len(x.claims),len(x.wires),len(x.parts)) for x in [A,B]])

LABEL={'power':'Alimentación','leds':'Verde / amarillo','panic':'Pánico','rx':'Receptor','tx':'Emisor IR','rgb':'RGB cátodo común'}
class Drawing:
 def __init__(self,l):self.l=l;self.s=[];self.name='rgb' if l.rgb else 'basic'
 def add(self,v):self.s.append(v)
 def text(self,x,y,s,cls='bb-t',anchor='start'):
  self.add(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{esc(s)}</text>')
 def badge(self,x,y,s,stage=None):
  stage=stage or ''
  w=max(35,len(s)*9+12)
  self.add(f'<g data-stage="{stage}"><rect x="{x-w/2}" y="{y-15}" width="{w}" height="23" rx="5" fill="#fff" fill-opacity=".96" stroke="#afc7d7"/><text x="{x}" y="{y+2}" text-anchor="middle" class="bb-ref">{esc(s)}</text></g>')
 def hole(self,a):
  x,y=xy(a);n=self.l.hole_nets.get(a,'');used=a in self.l.claims
  self.add(f'<circle cx="{x}" cy="{y}" r="{4.4 if used else 3.8}" class="bb-hole {"bb-used" if used else ""}" data-hole="{a}" data-net="{n}" fill="{color(n) if used else "#f8fafb"}"><title>{a}'+(f' · {self.l.claims[a]} · {n}' if used else (' · clip '+n if n else ' · libre'))+'</title></circle>')
 def wire(self,w):
  a,b=w['a'],w['b'];(x,y),(X,Y)=xy(a),xy(b);i=int(w['id'][1:]);stage=w['stage'];net=w['net']
  # Insulated cables; crossings only join at occupied holes, never at overlaps.
  if w['route'] is not None:route=w['route']
  elif a.startswith('PI:'):
   pin=int(a.split(':')[1]);lane=430+(i%6)*14
   if b.startswith(('T3:','TG:')):
    high=81 if b.startswith('T3:') else 133
    route=[(x,y),(lane,y),(lane,high),(X,high),(X,Y)]
   else:
    low={'power':600,'leds':640,'panic':680,'rx':720,'tx':760,'rgb':800}.get(stage,660)+(i%3)*12
    route=[(x,y),(lane,y),(lane,low),(X,low),(X,Y)]
  elif a.startswith('EXT:'):
   low=720+(i%5)*22
   if a.startswith('EXT:DL1'):
    side=(1800+(i%3)*8) if a.endswith(':A') else (2360+(i%3)*8)
    route=[(x,y),(side,y),(side,low),(X,low),(X,Y)]
   else:route=[(x,y),(x,low),(X,low),(X,Y)]
  elif ':' in a and ':' in b and a.split(':')[0]==b.split(':')[0]:
   route=[(x,y),(x,y-12),(X,y-12),(X,Y)]
  elif abs(X-x)<1 or abs(Y-y)<1:
   # keep signal row visible; lift jumpers slightly, ends stay at exact holes.
   lift=14+(i%3)*7
   route=[(x,y),(x,y-lift),(X,Y-lift),(X,Y)]
  elif ':' in a or ':' in b:route=[(x,y),(x,Y),(X,Y)]
  else:
   # A sparse lane in the central trench or immediately above the board.
   mid=(ROW['e']+ROW['f'])/2+(i%3-1)*9 if (y<ROW['f']<=Y or Y<ROW['f']<=y) else min(y,Y)-12-(i%3)*7
   route=[(x,y),(x,mid),(X,mid),(X,Y)]
  points=' '.join(f'{px},{py}' for px,py in route)
  self.add(f'<g data-stage="{stage}" data-net="{net}" class="bb-jumper"><title>{w["id"]}: {a} ↔ {b} · {esc(w["why"])}</title><polyline points="{points}" class="bb-wire-shadow"/><polyline points="{points}" class="bb-wire" style="stroke:{color(net)}"/></g>')
 def resistor(self,p):
  ref=p['ref'];a,b=p['pins'].values();x,y=xy(a);X,Y=xy(b);cx,cy=(x+X)/2,(y+Y)/2;angle=__import__('math').degrees(__import__('math').atan2(Y-y,X-x));length=min(51,__import__('math').hypot(X-x,Y-y)-10)
  if ref=='R6':cx,cy=x+.75*(X-x),y+.75*(Y-y)
  self.add(f'<g class="bb-part" data-stage="{p["stage"]}" data-ref="{ref}"><title>{ref} · {p["value"]} · {a} ↔ {b}</title><path d="M{x} {y} L{X} {Y}" class="bb-lead"/><g transform="translate({cx} {cy}) rotate({angle})"><rect x="{-length/2}" y="-8" width="{length}" height="16" rx="6" fill="#ead3a5" stroke="#99773e" stroke-width="1.2"/></g></g>')
  # Ref badges are annotations on the body, never electrically connected.
  self.badge(cx,cy,ref,p['stage'])
 def capacitor(self,p):
  ref=p['ref'];a,b=p['pins'].values();x,y=xy(a);X,Y=xy(b);cx,cy=(x+X)/2,(y+Y)/2
  if ref=='C1':
   cx+=6;cy=585
   self.add(f'<g class="bb-part" data-stage="power" data-ref="C1"><title>C1: + {a}; − {b}</title><path d="M{x} {y} Q{x} 560 {cx-18} {cy-20} M{X} {Y} Q{X} 560 {cx+18} {cy-20}" class="bb-lead"/><rect x="{cx-28}" y="{cy-28}" width="56" height="67" rx="12" fill="#1e4263"/><rect x="{cx+12}" y="{cy-23}" width="12" height="55" rx="3" fill="#dce5eb"/></g>')
   self.text(cx-45,cy-31,'+','bb-ref');self.text(cx+18,cy-3,'−','bb-ref','middle');self.text(cx,cy+60,'C1 · 100 µF / 63 V','bb-t','middle')
  else:
   self.add(f'<g class="bb-part" data-stage="{p["stage"]}" data-ref="{ref}"><title>{ref} 100 nF: {a} ↔ {b}</title><path d="M{x} {y} L{cx} {cy} L{X} {Y}" class="bb-lead"/><ellipse cx="{cx}" cy="{cy}" rx="17" ry="12" fill="#ddb579" stroke="#976e33"/></g>');self.badge(cx,cy,ref,p['stage'])
 def chip(self,p):
  n=8 if p['ref']=='U1' else 14
  top=sorted([(int(a[1:]),term,a) for term,a in p['pins'].items() if a.startswith('e')]);x,y=xy(top[0][2]);X,_=xy(top[-1][2]);mid=(ROW['e']+ROW['f'])/2
  self.add(f'<g class="bb-part" data-stage="{p["stage"]}" data-ref="{p["ref"]}"><rect x="{x-10}" y="{ROW["e"]+9}" width="{X-x+20}" height="{ROW["f"]-ROW["e"]-18}" rx="5" fill="#253d50"/><path d="M{X+10} {mid-8} a8 8 0 0 0 0 16" fill="#9eb3c1"/>')
  for term,a in p['pins'].items():
   px,py=xy(a);py2=ROW['e']+10 if a.startswith('e') else ROW['f']-10
   self.add(f'<path d="M{px} {py} V{py2}" class="bb-lead"/>');self.text(px,ROW['e']+22 if a.startswith('e') else ROW['f']-12,term.split()[0],'bb-chiptext','middle')
  self.text((x+X)/2,mid+5,p['ref']+' · '+('LM393' if n==8 else 'LS125'),'bb-chiptext','middle');self.add('</g>')
 def discrete(self,p):
  ref=p['ref'];ps=p['pins'];stage=p['stage']
  if ref in ['D1','Q2']:
   cy=xy(next(iter(ps.values())))[1];base=2148;end=2210
   body='#b6c5da' if ref=='D1' else '#293744';beam='#bb5c20' if ref=='D1' else '#007e83'
   self.add(f'<g class="bb-part" data-stage="{stage}" data-ref="{ref}" data-facing="east"><title>{ref}: lente horizontal hacia el este; '+', '.join(f'{k}={a}' for k,a in ps.items())+'</title>')
   for (k,a),dy in zip(ps.items(),[-13,9]):
    x,y=xy(a);self.add(f'<path d="M{x} {y} V{cy+dy} H{base}" class="bb-lead"/>')
   self.add(f'<path d="M{base} {cy-23} H2187 A23 23 0 0 1 2187 {cy+23} H{base} Z" fill="{body}" stroke="#526b7c" stroke-width="2"/><path d="M2193 {cy-19} Q2219 {cy} 2193 {cy+19}" fill="none" stroke="#e9f0f5" stroke-width="2"/>')
   start,finish=(2230,2420) if ref=='D1' else (2420,2230)
   self.add(f'<path d="M{start} {cy} H{finish}" fill="none" stroke="{beam}" stroke-width="3" stroke-dasharray="8 6"/>')
   tail=finish-12 if ref=='D1' else finish+12
   self.add(f'<polygon points="{finish},{cy} {tail},{cy-7} {tail},{cy+7}" fill="{beam}"/>')
   self.text(2230,cy+34,'Luz emitida →' if ref=='D1' else '← Luz entrante','bb-t')
   self.text(2150,cy+66,' · '.join(f'{k}={a}' for k,a in ps.items()),'bb-t')
   self.add('</g>');self.badge(2200,cy-34,ref+' · '+('IR' if ref=='D1' else 'PT333'),stage)
  elif ref=='DL1':
   pts=[xy(ps[k]) for k in ['L1','L2','L3','L4']];cx=sum(x for x,y in pts)/4;cy=216
   self.add('<g class="bb-part" data-stage="rgb" data-ref="DL1"><title>DL1: L1=d23 rojo, L2=d24 GND, L3=d25 verde, L4=d26 azul. Mantener orientación de la prueba.</title>')
   for i,((x,y),c) in enumerate(zip(pts,['#b3464d','#425261','#208047','#275db0'])):
    self.add(f'<path d="M{cx-15+i*10} {cy+13} L{x} {y}" class="bb-lead" style="stroke:{c}"/>')
   self.add(f'<circle cx="{cx}" cy="{cy}" r="28" fill="#f0e8ec" stroke="#677b90" stroke-width="2"/><path d="M{cx-24} {cy} A24 24 0 0 1 {cx+24} {cy}" fill="#c8a3b5"/></g>')
   self.badge(cx,cy-3,'DL1','rgb')
  elif ref=='Q1':
   pts=[xy(ps[k]) for k in ['E','B','C']];cx=pts[1][0];cy=pts[1][1]
   self.add(f'<g class="bb-part" data-stage="tx" data-ref="Q1"><path d="M{cx-28} {cy-22} A28 28 0 0 1 {cx+28} {cy-22} L{cx+28} {cy-5} H{cx-28} Z" fill="#253744" stroke="#122a3b"/>')
   for k,(x,y) in zip(['E','B','C'],pts):self.add(f'<path d="M{x} {cy-5} V{y}" class="bb-lead"/>');self.add(f'<text x="{x}" y="{y-28}" class="bb-pin" text-anchor="middle" style="fill:white">{k}</text>')
   self.add('</g>');self.badge(cx,cy+32,'Q1','tx')
  elif ref=='S1':
   x,y=xy(ps['3']);X,Y=xy(ps['2']);cx,cy=(x+X)/2,(y+Y)/2
   self.add(f'<g class="bb-part" data-stage="panic" data-ref="S1"><title>S1 candidato DTS-6: 3=e14, 4=f14 PANIC; 1=e16, 2=f16 GND. Ajustar patas con suavidad; comprobar continuidad.</title>')
   for k,a in ps.items():
    px,py=xy(a);self.add(f'<path d="M{px} {py} V{cy+(-24 if py<cy else 24)}" class="bb-lead"/>')
   self.add(f'<rect x="{cx-28}" y="{cy-26}" width="56" height="52" rx="5" fill="#bec8cb" stroke="#526b7c"/><rect x="{cx-13}" y="{cy-14}" width="26" height="28" rx="4" fill="#9a5040"/>')
   for k,a in ps.items():
    px,py=xy(a);self.text(px,cy-17 if py<cy else cy+25,k,'bb-pin','middle')
   self.add('</g>');self.badge(cx,cy,'S1','panic')
  elif ref=='RV1':
   cx,y=xy(ps['2 cursor']);cy=y+8
   self.add(f'<g class="bb-part" data-stage="rx" data-ref="RV1"><title>RV1 estilo vertical RM063: 1=d43 VBIAS, 2=c44 cursor VTH, 3=d45 GND; verificar pieza real. Cara ajustable hacia j.</title>')
   for k,a in ps.items():
    px,py=xy(a);self.add(f'<path d="M{px} {py} L{px} {cy}" class="bb-lead"/>')
   self.add(f'<rect x="{cx-28}" y="{cy-24}" width="56" height="34" rx="5" fill="#1d83be" stroke="#166594"/><ellipse cx="{cx}" cy="{cy-6}" rx="21" ry="16" fill="#edf1ed" stroke="#879ba2"/><path d="M{cx-12} {cy-6} H{cx+12}" stroke="#58747e" stroke-width="3"/></g>')
   self.badge(cx,cy-4,'RV1','rx')
  else:
   vals=list(ps.values());(x,y),(X,Y)=map(xy,vals);cx,cy=(x+X)/2,(y+Y)/2
   c={'D1':'#b6c5da','D2':'#46b879','D3':'#f0d14c','Q2':'#293744'}[ref]
   self.add(f'<g class="bb-part" data-stage="{stage}" data-ref="{ref}"><path d="M{x} {y} L{cx-4} {cy-10} M{X} {Y} L{cx+4} {cy-10}" class="bb-lead"/><circle cx="{cx}" cy="{cy-13}" r="14" fill="{c}" stroke="#4b6477"/></g>');self.badge(cx,cy-40,ref,stage)
   for k,a in ps.items():px,py=xy(a);self.text(px,py+20,k,'bb-pin','middle')
 def draw(self):
  self.add(f'<svg xmlns="http://www.w3.org/2000/svg" class="bb-scene" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="FaroNet protoboard {self.name}">')
  self.add('<style>'+SVG_CSS+'</style><rect width="2500" height="1420" fill="#f5f8fa"/>')
  self.text(55,34,'FaroNet · protoboard 830 puntos · '+('base + RGB cátodo común' if self.l.rgb else 'base sin RGB'),'bb-title')
  self.text(55,65,'Pi 2 B v1.1 y Pi 3 B: mismo header. Vista superior; agujeros exactos, cuerpos ilustrativos, no plantilla 1:1.','bb-t')
  # Pi pictorial board with true physical pin numbering.
  self.add('<rect x="70" y="125" width="335" height="660" rx="24" fill="#226746" stroke="#123d2a" stroke-width="3"/>')
  self.text(95,152,'Raspberry Pi 2/3 B','bb-pi-title');self.add('<rect x="250" y="165" width="98" height="510" rx="6" fill="#263b37"/>')
  for n in range(1,41):
   x,y=xy('PI:'+str(n));net=self.l.hole_nets.get('PI:'+str(n),'');c=color(net) if net else '#8ba498'
   self.add(f'<circle cx="{x}" cy="{y}" r="7" fill="{c}" stroke="#e4d5a6" stroke-width="2" data-net="{net}"><title>Pi físico {n}'+(' · '+net if net else ' · no usado')+'</title></circle>');self.text(x,y-10,str(n),'bb-pi-pin','middle')
  self.text(100,693,'Header común de 40 pines','bb-pi-pin');self.text(100,720,'Pin 1 arriba a la izquierda','bb-pi-pin');self.text(100,750,'Alimentar por Micro-USB','bb-pi-pin')
  for pin,lab in [(1,'1: 3,3 V · 2: 5 V'),(6,'6: GND'),(11,'11: BCM17 · TX'),(13,'13: BCM27 · RX'),(15,'15/16: verde/amarillo'),(18,'18: BCM24 · pánico')]+([(29,'29: BCM5 · rojo'),(31,'31: BCM6 · verde'),(33,'33: BCM13 · azul')] if self.l.rgb else []):
   self.text(85,xy('PI:'+str(pin))[1]+5,lab,'bb-pi-pin')
  self.text(65,800,'Valores por Faro','bb-subtitle')
  values=['R1: 330 Ω provisional; primera prueba: 1 kΩ.','R2 / R8 / R10 / R11: 1 kΩ.','R3 / R4 / R12: 10 kΩ. R5: 4,7 kΩ.','R6: 100 kΩ. R9: 2,2 kΩ. RV1: 10 kΩ.','C1: 100 µF/63 V. C2/C3: 100 nF/50 V.']
  if self.l.rgb:values+=['RGB: R13 / R14 / R15: 1 kΩ cada una.','GPIO alto = color encendido; bajo = apagado.']
  for i,v in enumerate(values):self.text(65,830+i*30,v,'bb-t')
  # Board and conductive clips.
  self.add(f'<rect x="{X0-55}" y="75" width="{62*P+110}" height="475" rx="15" fill="#fffdf6" stroke="#b8bfb7" stroke-width="2"/>')
  self.add(f'<rect x="{X0-35}" y="{ROW["e"]+10}" width="{62*P+70}" height="{ROW["f"]-ROW["e"]-20}" fill="#e7e8df"/>')
  for c in range(1,64):
   x,_=xy('a'+str(c));
   for bank in ['a','f']:
    y=ROW[bank];self.add(f'<rect x="{x-6}" y="{y-6}" width="12" height="{4*P+12}" rx="5" fill="#e9ece7"/>')
   self.text(x,159,str(c),'bb-col','middle');self.text(x,478,str(c),'bb-col','middle')
  for row,y in ROW.items():self.text(X0-28,y+5,row,'bb-row','middle');self.text(X0+62*P+29,y+5,row,'bb-row','middle')
  for rail,y in RY.items():
   n={'T3':'3V3','TG':'GND','B5':'5V','BG':'GND'}[rail]
   for lo,hi in [(1,25),(26,50)]:
    x,_=xy(f'{rail}:{lo}');X,_=xy(f'{rail}:{hi}')
    self.add(f'<path d="M{x-7} {y-9} H{X+7}" stroke="{color(n)}" stroke-width="2"/>')
   self.text(X0-62,y+5,{'T3':'T3 · +3,3 V','TG':'TG · GND','B5':'B5 · +5 V','BG':'BG · GND'}[rail],'bb-row','end')
  self.text(2180,79,'FRENTE ÓPTICO','bb-subtitle');self.text(2180,110,'ESTE / DERECHA →','bb-t')
  self.add('<path d="M2210 170 V460" stroke="#8aa2b2" stroke-width="1.5" stroke-dasharray="5 5" fill="none"/>')
  if self.l.rgb:self.add('<rect x="1830" y="900" width="510" height="270" rx="14" fill="#fff4da" stroke="#bc861b"/>')
  # Draw wires underneath occupied-hole markers and parts.
  for wire in self.l.wires:self.wire(wire)
  self.badge(555,580,'W04 · GND ↔ GND','power')
  for r in 'abcdefghij':
   for c in range(1,64):self.hole(r+str(c))
  for r in RY:
   for i in range(1,51):self.hole(f'{r}:{i}')
  for p in self.l.parts:
   r=p['ref']
   if r.startswith('R') and r!='RV1':self.resistor(p)
   elif r.startswith('C'):self.capacitor(p)
   elif r.startswith('U'):self.chip(p)
   elif r in ['D1','D2','D3','Q1','Q2','DL1','S1','RV1']:self.discrete(p)
  # The rail addresses count their own 50 holes; they are not signal columns.
  # Keep the one marker underneath R5 off the drawing rather than hiding its ref.
  for rail,y in RY.items():
   for i in [1,5,10,15,20,25,26,30,35,40,45,50]:
    if rail=='TG' and i==30:continue
    x,_=xy(f'{rail}:{i}');self.text(x,y+15,str(i),'bb-rail-index','middle')
  # These are explanatory callouts; the actual parts are now on the board.
  self.add('<rect x="740" y="870" width="530" height="155" rx="12" fill="#fff" stroke="#a9c1d2"/>')
  self.text(760,900,'S1 · propuesta para DTS-6','bb-subtitle');self.text(760,930,'3=e14 / 4=f14 → PANIC.','bb-t');self.text(760,960,'1=e16 / 2=f16 → GND.','bb-t');self.text(760,990,'Ajustar patas; medir antes de conectar Pi.','bb-t')
  self.add('<rect x="1310" y="870" width="470" height="155" rx="12" fill="#fff" stroke="#a9c1d2"/>')
  self.text(1330,900,'RV1 · estilo vertical RM063','bb-subtitle');self.text(1330,930,'1=d43 VBIAS; 2=c44 VTH; 3=d45 GND.','bb-t');self.text(1330,960,'Confirmar cursor; ajuste hacia fila j.','bb-t');self.text(1330,990,'RM065 horizontal: cursor en b44.','bb-t')
  if self.l.rgb:
   self.add('<rect x="1830" y="900" width="510" height="270" rx="14" fill="none" stroke="#bc861b" stroke-width="2"/>')
   self.text(1850,933,'DL1 · cátodo común confirmado','bb-subtitle')
   for i,t in enumerate(['L1 rojo → d23 · R13 · GPIO5 / físico29','L2 común → d24 · GND','L3 verde → d25 · R14 · GPIO6 / físico31','L4 azul → d26 · R15 · GPIO13 / físico33','Mantener la orientación de tu prueba.','RGB solo con GPIO de 3,3 V; no usar 5 V.']):self.text(1850,971+i*32,t,'bb-t')
  self.text(65,1040,'Lectura rápida','bb-subtitle')
  for i,t in enumerate(['a38 = columna 38, fila a. a–e de esa columna están unidos.','f–j de esa misma columna forman otro clip, separado por la ranura.','T3 = 3,3 V; TG = GND superior; B5 = 5 V; BG = GND inferior.','Los cuatro puentes 25↔26 unen mitades del mismo riel.','Cruzar cables aislados en el dibujo NO los une. Solo importan sus extremos.','E/B/C de Q1 según orientación indicada: cara plana hacia j.','PT333: emisor largo 1; colector corto 2, según hoja Everlight.']):self.text(65,1075+30*i,t,'bb-t')
  self.text(740,1055,'Referencias y puntos clave','bb-subtitle')
  for i,t in enumerate(['U1 LM393: muesca derecha; pin 1 = e38; pin 8 = f38.','Q1: E=j55, B=j56, C=j57. Comprobar pieza antes de energía.','Q2 PT333: E=c60, C=c61; lente al ESTE, como D1.','D1 IR: A=i60, K=i61; R1=330 Ω provisional (1 kΩ inicial sin ficha).','C1: +=B5:44, −=BG:46. Cerámicos C2/C3 no tienen polaridad.','SENSE: b61 → c41 → b41 → b37 / U1.2.','R4 carga: a47 → a41, 10 kΩ inicial.']):self.text(740,1090+30*i,t,'bb-t')
  self.text(65,1340,'Revisión por software: continuidad del cobre, separación de redes y correspondencia con el esquema. No sustituye mediciones reales.','bb-subtitle')
  self.text(65,1380,'Montaje final del proyecto: circuito validado y soldado en perfboard/PCB; la protoboard es para las pruebas iniciales.','bb-t')
  self.add('</svg>');return ''.join(self.s)

SVG_CSS='''
.bb-scene text{font-family:system-ui,-apple-system,sans-serif;fill:#213f56}.bb-scene .bb-t{font-size:19px}.bb-scene .bb-title{font-size:28px;font-weight:750}.bb-scene .bb-subtitle{font-size:21px;font-weight:750}.bb-scene .bb-row{font-size:16px;font-weight:750}.bb-scene .bb-col{font-size:13px}.bb-scene .bb-rail-index{font-size:10px;fill:#526e7c;stroke:#fffdf6;stroke-width:2;paint-order:stroke fill}.bb-scene .bb-ref{font-size:14px;font-weight:750}.bb-scene .bb-pin{font-size:13px;font-weight:750;fill:#16354e}.bb-scene .bb-chiptext{font-size:13px;font-weight:750;fill:#fff}.bb-scene .bb-pi-pin{font-size:14px;fill:#fff}.bb-scene .bb-pi-title{font-size:23px;font-weight:750;fill:white}.bb-scene .bb-lead{fill:none;stroke:#8294a0;stroke-width:2.2;stroke-linecap:round}.bb-scene .bb-hole{stroke:#687b83;stroke-width:1;cursor:pointer}.bb-scene .bb-wire{fill:none;stroke-width:3.1;stroke-linejoin:round;stroke-linecap:round;opacity:.82}.bb-scene .bb-wire-shadow{fill:none;stroke:#fff;stroke-width:5.7;stroke-linejoin:round;stroke-linecap:round;opacity:.84}.bb-scene .bb-jumper{cursor:pointer}.bb-scene .bb-pick{filter:drop-shadow(0 0 5px #ffad12)}.bb-scene .bb-pick .bb-wire{stroke-width:6;opacity:1}.bb-scene.has-net .bb-jumper:not(.bb-pick){opacity:.10}.bb-scene .stage-dim{opacity:.1}.bb-scene .bb-hole.bb-pick{stroke:#f8a514;stroke-width:4}
'''
SA=Drawing(A).draw();SB=Drawing(B).draw()
(HERE/'faronet-breadboard-basic.svg').write_text(SA)
(HERE/'faronet-breadboard-rgb.svg').write_text(SB)
plans={}
for name,l in [('basic',A),('rgb',B)]:
 plans[name]=dict(parts=l.parts,wires=l.wires,checks=l.checks,occupied=l.claims,hole_nets=l.hole_nets,unresolved=['S1: candidato DTS-6; confirmar parejas y encaje sin forzar','RV1: SKU AD8289; confirmar estilo y cursor en pieza real'],mounting=CANON['mounting_identification'],optical_front={'direction':'east/right','Q2':{'E':'c60','C':'c61'},'D1':{'A':'i60','K':'i61'},'receiver_link':'b61 to c41; c41 shares clip with a41 R4 and b41 to U1.2','placement':'Both lenses horizontal and toward right; rotate peer Faro 180 degrees, align D1 to peer Q2 at equal height','limits':'Mechanical proposal; no optical bench qualification'},rgb_pinout={'type':'common-cathode','L1':'red','L2':'GND common','L3':'green','L4':'blue','evidence':'User diode test; preserve test orientation; verify other LED separately'} if l.rgb else None,q1_order='EBC indicado por equipo, plano hacia j',pt333='Everlight 1=E largo, 2=C corto; contrastar pieza real')
(HERE/'layout-data.json').write_text(json.dumps(plans,ensure_ascii=False,indent=2))
print('SVG and layout data written.')

FINDINGS=[
 ['Coincidencia','IR + NPN, PT333 + LM393, TX/RX y pánico','La arquitectura general coincide. Se conserva el desacoplo, el ajuste de umbral y la salida del LM393 con pull-up a 3,3 V.'],
 ['Cambio importante','Receptor diferente: no unir los dos diseños a medias','Recibido: colector del PT a 3,3 V; emisor a VSIG y 47 kΩ a GND; señal a U1.3 (+). Nuestro: emisor a GND; colector a SENSE y carga 10 kΩ a VBIAS; señal a U1.2 (−). Ambos pueden entregar alto con luz, pero requieren su propio cableado de umbral e histéresis.'],
 ['Cambio importante','J1 y GPIO no son intercambiables','Recibido: J1.1=5 V, J1.2=3,3 V; pánico GPIO26/físico37 y RGB GPIO16/20/21. Nuestro: J1.1=3,3 V, J1.2=5 V; pánico GPIO24/físico18 y RGB directo GPIO5/6/13. No mezclar arneses ni configurar el software con el otro mapa.'],
 ['Actualización incorporada','Se prefiere el RGB de cuatro patas','La prueba del equipo confirma cátodo común L2 y ánodos L1 rojo, L3 verde, L4 azul. El tipo coincide con el SVG recibido; no se debe copiar su orden R/K/G/B sin contrastarlo. Este montaje usa GPIO5/6/13 con 1 kΩ por color. El DL410 de ocho terminales queda fuera.'],
 ['Corrección incorporada','Q1 es E–B–C en el plan','El generador recibido dice EBC, no ECB. El equipo indicó EBC con cara plana hacia el observador. En nuestro dibujo la cara plana mira hacia j y E/B/C se insertan en j55/j56/j57. Es una orientación indicada por el equipo; comprobar la pieza real antes de alimentar.'],
 ['Pieza identificada por referencia','PT333: identificar el terminal físico','La hoja Everlight PT333-3B identifica pin1/emisor (largo, sin recortar) y pin2/colector (corto). Se dibuja E=c60 y C=c61. Confirmar correspondencia del encapsulado; no aplicar la regla ánodo/cátodo de un LED al fototransistor.'],
 ['No asumir','IR a 35 mA y alcance de 1–2 m','El recibido propone 100 Ω y supone un máximo típico del LED desconocido. Ese dato no identifica el emisor comprado. Nuestro plan mantiene 330 Ω provisional; primera prueba con 1 kΩ si falta ficha y medir I=V/R. Alcance y BER se miden.'],
 ['Corrección incorporada','Apagado del NPN al arrancar','El recibido confía en el pull-down inicial del GPIO y usa 2,2 kΩ de base. Conservamos R2=1 kΩ y R3=10 kΩ externos del esquema actual. El cálculo con ganancia hFE típica no demuestra saturación a 35 mA.'],
 ['Depende de la placa real','Rieles de alimentación posiblemente partidos','El SVG recibido no dibuja puentes entre mitades y conecta fuentes en el extremo izquierdo mientras usa electrónica a la derecha. Si el riel real está partido, la mitad derecha queda sin alimentar. Nuestro modelo lo supone partido y puentea 25↔26 en los cuatro rieles; comprobarlo con multímetro.'],
 ['Representación corregida','830 puntos reales en el modelo','El generador recibido dibuja 63 agujeros por cada riel: 630+252=882, aunque lo llama 830. Nuestro dibujo contiene 630 puntos de señal y 4×50 de riel. Las direcciones de riel son propias (T3:1…50), distintas de columnas 1…63.'],
 ['Huella candidata incorporada','S1: familia DTS-6, posible DTS-644R','La ficha une 1–2 y 3–4 internamente. Ahora se dibuja sobre la ranura e/f, en columnas 14/16, con ajuste suave de patas de 6,5×4,5 a 7,62×5,08 mm. Confirmar patrón y encaje reales antes de conectar la Pi.'],
 ['Huella candidata incorporada','RV1: AD8289 es código de tienda','La foto corresponde visualmente al estilo vertical RM063. Se dibuja 1=d43, 2=c44, 3=d45 y se conserva una alternativa RM065 con cursor b44. Medir extremos y cursor antes de montar; SKU y color no identifican el fabricante.'],
 ['Se conserva nuestro esquema','LM393 y su canal no usado','La numeración del LM393 con muesca derecha en el SVG recibido es coherente. El recibido lleva su pin6 a 5 V; no lo calificamos como corto: TI contempla casos con una entrada fuera del rango cuando la otra permanece dentro. En nuestro plan pin5=GND, pin6=VBIAS y pin7 libre; ambas entradas quedan dentro del rango previsto.'],
 ['Valores distintos','Pull-up, indicadores y pánico','Recibido: pull-up RX 22 kΩ, indicadores 330 Ω y pánico con pull-up interno + 100 nF. Nuestro: RX 4,7 kΩ, indicadores 1 kΩ y pánico con 10 kΩ externo y antirrebote de software. No reasignar resistencias solo por el número R.'],
 ['Dato del equipo prevalece','Inventario y compras','El documento recibido afirma que falta un fototransistor; el equipo confirmó dos PT333. El RGB de cuatro patas fue confirmado como cátodo común, con L2 compartido y L1/L3/L4 rojo/verde/azul; se prefiere al DL410. No se supone que el segundo Faro tenga otro RGB de cuatro patas: confirmar una unidad compatible por Faro.'],
 ['Límite de evidencia','Simulador recibido','faro-sim.html usa un modelo simplificado: corriente óptica supuesta a 1 m, C_EFF, retardo y ruido escogidos. Sirve para explorar tendencias, no para verificar estas piezas, el pinout, el montaje, una distancia o la BER real.'],
 ['Comprobar integración','Comandos faro-test','Los archivos adjuntos mencionan módulos y comandos que no están en la copia local inspeccionada (el CLI local indica GPIO pendiente). No se cambió firmware ni se promete que esos comandos estén disponibles en la Pi. Verificar la versión que use el equipo.'],
]

PINCOMPARE=[['TX','17 / 11','17 / 11'],['RX','27 / 13','27 / 13'],['Verde TX','22 / 15','22 / 15'],['Amarillo RX','23 / 16','23 / 16'],['Pánico','26 / 37','24 / 18'],['RGB rojo','16 / 36 directo al LED','5 / 29 vía R13 de 1 kΩ a L1'],['RGB verde','20 / 38 directo al LED','6 / 31 vía R14 de 1 kΩ a L3'],['RGB azul','21 / 40 directo al LED','13 / 33 vía R15 de 1 kΩ a L4']]
FUNCTIONS=[['Resistencia IR','R2 = 100 Ω (330 Ω primera prueba)','R1 = 330 Ω provisional; 1 kΩ inicial sin ficha'],['Base NPN','R1 = 2,2 kΩ','R2 = 1 kΩ'],['Pulldown base','No dibujado','R3 = 10 kΩ'],['Carga detector','R3 = 47 kΩ a GND, en emisor','R4 = 10 kΩ a VBIAS, en colector'],['Pull-up RX','R6 = 22 kΩ','R5 = 4,7 kΩ a 3,3 V'],['Histéresis','R4 = 4,7 kΩ + R5 = 100 kΩ','R6 = 100 kΩ a cursor RV1'],['Referencia','RV1 entre 3,3 V y GND','R8/R9 generan VBIAS; RV1 entre VBIAS y GND']]

def table(head,rows):return '<div class="bb-table-wrap"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in r)+'</tr>' for r in rows)+'</tbody></table></div>'
PI_DEST={1:'T3:2',2:'B5:2',6:'TG:2',11:'j52',13:'c38',15:'h5',16:'h9',18:'d14',29:'j18',31:'j23',33:'j28'}
PI_FUNCTION={1:'Alimentación 3,3 V',2:'Alimentación 5 V',6:'GND común local',11:'TX emisor IR',13:'RX comparador',15:'LED verde TX',16:'LED amarillo RX',18:'Botón de pánico',29:'RGB rojo (R13, 1 kΩ)',31:'RGB verde (R14, 1 kΩ)',33:'RGB azul (R15, 1 kΩ)'}
PI_COMPAT_ROWS=[[PI_FUNCTION[p[1]],f'físico {p[1]} · {p[2]}',f'físico {p[1]} · {p[2]}','<code>'+PI_DEST[p[1]]+'</code>'] for p in CANON['pins']]
FACING='''<svg xmlns="http://www.w3.org/2000/svg" class="face-view" viewBox="0 0 1600 620" width="1600" height="620" role="img" aria-label="Dos Faros enfrentados con rutas ópticas alineadas"><style>.face-view text{font-family:system-ui,sans-serif;fill:#213f56}.face-view .face-title{font-size:28px;font-weight:750}.face-view .face-label{font-size:24px;font-weight:700}.face-view .face-note{font-size:20px}.face-view .face-small{font-size:18px}</style><rect width="1600" height="620" rx="15" fill="#f3f8fa"/>
<text x="60" y="48" class="face-title">Dos Faros enfrentados · vista desde arriba</text><text x="60" y="88" class="face-note">Construir ambos con las lentes al este del plano individual. Después, girar todo el Faro B 180°.</text>
<text x="70" y="144" class="face-label">Faro A · orientación del plano</text><text x="1100" y="144" class="face-label">Faro B · girado 180°</text>
<rect x="70" y="170" width="430" height="300" rx="18" fill="#e2f0e8" stroke="#5d8b70" stroke-width="2"/><rect x="1100" y="170" width="430" height="300" rx="18" fill="#e2f0e8" stroke="#5d8b70" stroke-width="2"/>
<rect x="90" y="272" width="100" height="110" rx="10" fill="#226746"/><text x="140" y="338" text-anchor="middle" class="face-label" style="fill:white">Pi</text><rect x="1410" y="272" width="100" height="110" rx="10" fill="#226746"/><text x="1460" y="338" text-anchor="middle" class="face-label" style="fill:white">Pi</text>
<path d="M450 232 H480 A18 18 0 0 1 480 268 H450 Z" fill="#293744"/><path d="M450 362 H480 A18 18 0 0 1 480 398 H450 Z" fill="#b6c5da" stroke="#526b7c"/>
<path d="M1150 232 H1120 A18 18 0 0 0 1120 268 H1150 Z" fill="#b6c5da" stroke="#526b7c"/><path d="M1150 362 H1120 A18 18 0 0 0 1120 398 H1150 Z" fill="#293744"/>
<text x="410" y="242" text-anchor="end" class="face-label">Q2 · RX</text><text x="410" y="372" text-anchor="end" class="face-label">D1 · TX</text><text x="1190" y="242" class="face-label">D1 · TX</text><text x="1190" y="372" class="face-label">Q2 · RX</text>
<path d="M1095 250 H505" fill="none" stroke="#007e83" stroke-width="4" stroke-dasharray="10 7"/><polygon points="505,250 520,242 520,258" fill="#007e83"/><text x="800" y="222" text-anchor="middle" class="face-label">B transmite; A recibe</text>
<path d="M505 380 H1095" fill="none" stroke="#bb5c20" stroke-width="4" stroke-dasharray="10 7"/><polygon points="1095,380 1080,372 1080,388" fill="#bb5c20"/><text x="800" y="352" text-anchor="middle" class="face-label">A transmite; B recibe</text>
<text x="330" y="441" class="face-note">Frente ESTE →</text><text x="1120" y="441" class="face-note">← Frente OESTE</text>
<text x="60" y="518" class="face-label">Alinear D1 de A con Q2 de B, y D1 de B con Q2 de A, a la misma altura.</text><text x="60" y="558" class="face-note">Ajustar por las lentes; los bordes plásticos no son la referencia. Probar una dirección por vez.</text><text x="60" y="600" class="face-small">Esquema de colocación, sin escala ni garantía de alcance. Cada Faro conserva su Pi y fuente independientes.</text></svg>'''
(HERE/'faronet-facing-layout.svg').write_text(FACING)
source_path=Path('/Users/ajqc/Downloads/protoboard-faro.svg')
original=''
if source_path.exists():
 raw=source_path.read_text();xml=ET.fromstring(raw)
 assert not any(el.tag.split('}')[-1] in ['script','foreignObject'] for el in xml.iter())
 original='<img class="original" alt="SVG recibido, conservado como referencia" src="data:image/svg+xml;base64,'+base64.b64encode(raw.encode()).decode()+'">'

CSS='''
:root{color-scheme:light;--ink:#1d3c53;--muted:#526d81;--border:#cddde7}*{box-sizing:border-box}body{margin:0;background:#f0f5f8;color:var(--ink);font:16px/1.6 system-ui,-apple-system,sans-serif}main{max-width:1340px;margin:auto;padding:28px 28px 70px}header{padding:32px 36px;border-radius:16px;background:#143c54;color:white}h1{font-size:37px;line-height:1.18;margin:10px 0 16px;letter-spacing:-.7px}h2{font-size:25px;line-height:1.3;margin:8px 0 12px}h3{font-size:19px;margin:20px 0 10px}p{margin:10px 0}.kicker{font-size:12px;font-weight:760;letter-spacing:1.6px;color:#117e79}header .kicker{color:#89d9ce}header p{color:#e1eef5;max-width:1000px}.card{border:1px solid var(--border);border-radius:12px;background:white;padding:24px;margin:23px 0;scroll-margin-top:15px}.notice{padding:15px 18px;border-left:5px solid #bd861d;background:#fff4d9;border-radius:6px}.notice.good{background:#e8f5f2;border-color:#188477}.hint{font-size:14px;color:var(--muted)}a{color:#075f9f;text-underline-offset:3px}nav,.controls{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}button,nav a{font:inherit;font-size:14px;line-height:1.5;padding:8px 12px;border:1px solid #b9cedc;background:white;color:#185577;border-radius:6px;cursor:pointer;text-decoration:none}button:hover,nav a:hover{background:#e9f6ff}button[aria-pressed=true]{background:#116c70;color:white;border-color:#116c70}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #dfa03b;outline-offset:2px}select,input[type=search]{font:inherit;border:1px solid #b7cdda;border-radius:6px;padding:8px 10px;max-width:100%}.viewport{overflow:auto;max-height:790px;border:1px solid #c6d7e4;background:#f5f8fa;border-radius:8px;overscroll-behavior:contain}.bb-scene{display:block;width:2200px;max-width:none}.readout{padding:12px 16px;margin-top:12px;border-radius:6px;background:#eaf5f4;font-size:14px;overflow-wrap:anywhere}.bb-table-wrap{overflow:auto;width:100%}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.5;margin:12px 0}th{text-align:left;background:#e9f1f7;white-space:nowrap;padding:10px}td{vertical-align:top;padding:10px;border-bottom:1px solid #dbe6ed}tr:hover td{background:#f7fbfd}code{font:13px ui-monospace,monospace;color:#056a76;white-space:nowrap}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:22px}.two-col>*{min-width:0}.face-view{display:block;width:100%;height:auto}.face-wrap{overflow:auto;max-width:100%}.original{display:block;width:1800px;max-width:none}.hidden{display:none!important}ol,ul{padding-left:23px}li{margin:9px 0}.chip{display:inline-block;border-radius:20px;background:#edf4f7;border:1px solid #c6dbe6;font-size:12px;padding:2px 8px}.checklist label{display:block;padding:8px 0;border-bottom:1px solid #e0e9ee}.checklist input{width:17px;height:17px;vertical-align:middle;margin-right:9px}footer{font-size:13px;color:#5a7285;margin-top:25px}.nowrap{white-space:nowrap}.comparison td:first-child{font-weight:700}.chipmap{display:grid;grid-template-columns:1fr 1fr;gap:15px}.chipmap table{font-size:13px}
@media(max-width:720px){main{padding:14px 11px 40px}header{padding:22px}h1{font-size:29px}.card{padding:16px}h2{font-size:22px}.two-col,.chipmap{grid-template-columns:1fr}.viewport{max-height:70vh}.controls{gap:6px}}
@media print{@page{size:A3 landscape;margin:12mm}body{background:white;font-size:12px}main{max-width:none;padding:0}header{padding:20px;border-radius:0}h1{font-size:29px}h2{font-size:21px}nav,.controls,.no-print,.readout,.checklist{display:none!important}.card{border-radius:0;padding:13px;break-inside:auto}.board-version{display:block!important;break-before:page;break-after:page}.viewport{overflow:visible;max-height:none;border:0}.bb-scene{width:100%!important;height:auto!important;max-height:216mm}.original{width:100%;height:auto}table{font-size:10px}th,td{padding:5px}.hint{font-size:11px}.bb-jumper,.stage-dim{opacity:1!important}.bb-scene.has-net .bb-jumper:not(.bb-pick){opacity:1!important}.bb-scene .bb-pick{filter:none}.bb-scene .bb-pick .bb-wire{stroke-width:3.1}}
'''

CONTROL_DETAIL='''<svg xmlns="http://www.w3.org/2000/svg" class="control-view" viewBox="0 0 1600 720" width="1600" height="720" role="img" aria-label="Detalle de contactos S1 y RV1 en la protoboard"><style>.control-view text{font-family:system-ui,sans-serif;fill:#213f56;font-size:22px}.control-view .title{font-size:28px;font-weight:750}.control-view .sub{font-size:20px}.control-view .label{font-size:24px;font-weight:700}.control-view .tiny{font-size:18px}</style><rect width="1600" height="720" rx="14" fill="#f3f8fa"/>
<text x="45" y="48" class="title">S1 · vista superior del montaje</text><text x="825" y="48" class="title">RV1 · estilo vertical RM063</text>
<text x="45" y="86" class="sub">Numeración de ficha girada 90° en sentido horario.</text><text x="825" y="86" class="sub">Ajuste lateral mirando hacia la fila j (abajo).</text>
<rect x="110" y="243" width="560" height="110" rx="9" fill="#e4e6dd"/><text x="125" y="299" class="tiny">Ranura</text>
<rect x="258" y="210" width="264" height="175" rx="12" fill="#d2dce0" stroke="#657d89" stroke-width="3"/>
<path d="M290 175 V420" stroke="#aa467d" stroke-width="6"/><path d="M490 175 V420" stroke="#425261" stroke-width="6"/>
<rect x="350" y="265" width="80" height="70" rx="8" fill="#9a5040"/><text x="390" y="310" text-anchor="middle" style="fill:white" class="label">S1</text>
<circle cx="290" cy="175" r="9" fill="#aa467d"/><circle cx="290" cy="420" r="9" fill="#aa467d"/><circle cx="490" cy="175" r="9" fill="#425261"/><circle cx="490" cy="420" r="9" fill="#425261"/>
<text x="290" y="144" text-anchor="middle" class="label">3 → e14</text><text x="490" y="144" text-anchor="middle" class="label">1 → e16</text>
<text x="290" y="466" text-anchor="middle" class="label">4 → f14</text><text x="490" y="466" text-anchor="middle" class="label">2 → f16</text>
<text x="290" y="512" text-anchor="middle" class="label">PANIC</text><text x="490" y="512" text-anchor="middle" class="label">GND</text>
<text x="45" y="559">Líneas verticales = uniones internas del botón.</text><text x="45" y="594">No añadir cables entre las parejas: pulsar las une.</text>
<text x="45" y="637" class="sub">Huella original: 6,5 × 4,5 mm. Rejilla: 7,62 × 5,08 mm.</text><text x="45" y="674" class="sub">Ajustar patas con suavidad o conectar con jumpers.</text>
<path d="M1100 352 V338 M1260 352 V338 M1180 210 V247" stroke="#8499a3" stroke-width="3" fill="none"/>
<rect x="1068" y="245" width="224" height="104" rx="14" fill="#1886c2" stroke="#166594" stroke-width="2"/>
<ellipse cx="1180" cy="294" rx="79" ry="47" fill="#eef1ed" stroke="#8aa0a7" stroke-width="2"/><path d="M1134 294 H1226" stroke="#5e777e" stroke-width="8"/>
<circle cx="1100" cy="352" r="9" fill="#986300"/><circle cx="1260" cy="352" r="9" fill="#425261"/><circle cx="1180" cy="210" r="9" fill="#986300"/>
<text x="1180" y="158" text-anchor="middle" class="label">2 · cursor → c44 / VTH</text><text x="1180" y="190" text-anchor="middle" class="tiny">Pata centrada detrás de los extremos</text>
<text x="1075" y="397" text-anchor="middle" class="label">1 → d43</text><text x="1285" y="397" text-anchor="middle" class="label">3 → d45</text>
<text x="1075" y="433" text-anchor="middle">VBIAS</text><text x="1285" y="433" text-anchor="middle">GND</text>
<text x="1180" y="479" text-anchor="middle" class="sub">5 mm entre extremos; cursor desplazado 2,5 mm.</text>
<text x="825" y="531">Medir aislado: extremos ≈10 kΩ constantes;</text><text x="825" y="566">cursor–extremo cambia al girar.</text>
<text x="825" y="614" class="sub">RM065 horizontal (otra huella): cursor → b44.</text><text x="825" y="651" class="sub">Extremos d43/d45; una sola pieza, sin forzar patas.</text><text x="825" y="688" class="tiny">AD8289 es un SKU; confirmar estilo y contactos reales.</text>
</svg>'''
(HERE/'faronet-button-trimpot.svg').write_text(CONTROL_DETAIL)
CSS+='\n.control-view{display:block;width:100%;height:auto}\n'

PAGE=f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FaroNet · Revisión y protoboard comprobada</title><style>{CSS}</style></head><body><main>
<header><div class="kicker">FARONET · REVISIÓN DE COMPATIBILIDAD · 18 OCTUBRE 2026</div><h1>De los dos diseños a un montaje coherente.</h1><p>El SVG recibido comparte la arquitectura del Faro, pero cambia el receptor, el RGB, varios GPIO y el orden del conector. Este montaje conserva el núcleo del esquema anterior y actualiza el RGB con el resultado del multímetro. Añade direcciones de agujeros, puentes de riel y comprobación del cobre de una protoboard de 830 puntos.</p></header>
<nav><a href="#verdict">Resultado</a><a href="#pi-compatibility">Pi 2 / Pi 3</a><a href="#layout">Nuestro montaje</a><a href="#wires">Cable por cable</a><a href="#parts">Patillas y piezas</a><a href="#switch-pot">Botón y RV1</a><a href="#optical-front">Lentes y alineación</a><a href="#rgb-test">RGB confirmado</a><a href="#comparison">Comparación</a><a href="#tests">Antes de energizar</a></nav>
<section class="card" id="verdict"><p class="notice good"><b>Revisión 6:</b> S1 y RV1 aparecen dentro del tablero, con huellas candidatas basadas en DTS-6 y en el trimpot azul/blanco. <a href="#switch-pot">Ver contactos, ajuste y pruebas</a> antes de montarlos. No se cambian los GPIO; físico18 ahora llega a d14 para dejar e14 al botón.</p><span class="kicker">RESULTADO DE LA REVISIÓN</span><h2>El SVG recibido no es un reemplazo directo del nuestro.</h2><p>Sirve como referencia visual. Su receptor es otra topología. El RGB de cuatro patas ya fue identificado por el equipo como cátodo común; su conexión ahora queda definida en esta revisión. Los cambios de J1/pánico/RGB también requieren otro cableado y otra configuración del programa.</p><div class="notice"><b>No mezclar conectores:</b> el documento recibido asigna J1.1 a 5 V y J1.2 a 3,3 V; nuestro esquema los asigna al revés. Conectar físicamente por el mapa Pi/agujero de este archivo, no por un número J1 tomado de uno u otro documento.</div><p>La comprobación automática de nuestro montaje verifica clips, puentes y terminales contra el núcleo del esquema anterior y la nueva rama RGB: <b>cada red conectada, sin unir 5 V a 3,3 V/GND o a un GPIO por cobre</b>. No comprueba funcionamiento analógico, emisión IR ni BER. Falta la validación real del montaje.</p><p><b>Q1:</b> E–B–C según la orientación indicada por el equipo, cara plana hacia j. <b>PT333 Everlight:</b> pin 1 emisor/largo y pin 2 colector/corto en el dibujo del fabricante. Contrastar estas orientaciones con las piezas antes de aplicar energía.</p><p class="notice good"><b>Frente óptico actualizado:</b> Q2 ahora está en c60/c61 y D1 sigue en i60/i61; ambas lentes se orientan hacia el este. Usar las tablas de esta revisión; los agujeros c40/c41 del PT333 pertenecen al plano anterior. El núcleo básico puede probarse independientemente del RGB. RGB confirmado: <b>L1 rojo, L2 GND común, L3 verde, L4 azul</b>, manteniendo la orientación usada en la prueba del equipo. Ahora se conecta directamente a GPIO5/6/13 con <b>una resistencia de 1 kΩ por color</b>. Se eliminan U2/LS125, C4 y R16–R18 de esta rama. El DL410 queda fuera. <b>HIGH enciende; LOW apaga.</b> No usar el antiguo común a 5 V.</p></section>
<section class="card" id="pi-compatibility"><span class="kicker">PI 2 MODEL B v1.1 Y PI 3 MODEL B · MISMO CABLEADO</span><h2>La Pi 2 puede usar este mismo montaje de protoboard.</h2><p class="notice good"><b>El header de 40 pines es compatible:</b> en la Raspberry Pi 2 Model B v1.1, cada conexión del Faro mantiene el mismo pin físico, número BCM y nivel lógico de 3,3 V que en la Pi 3 B. No se cambia ningún jumper, resistencia ni componente por sustituir la Pi 3 por esa Pi 2. Los dos planos llevan ahora el rótulo compartido «Raspberry Pi 2/3 B».</p><p>La tabla muestra <b>todas las conexiones usadas</b>. «GPIO17» es numeración BCM; corresponde al <b>pin físico11</b> en ambas placas. Los números del header dibujado son físicos, del 1 al 40. La diferencia entre las dos placas no exige un segundo mapa de conexiones.</p>{table(['Función del Faro','Pi 2 Model B v1.1','Pi 3 Model B','Agujero de destino, igual en ambas'],PI_COMPAT_ROWS)}<p class="hint">Las últimas tres filas solo se montan en la alternativa con RGB. La resistencia de cada color está entre el GPIO y su ánodo; L2 del RGB sigue a GND. «5 V» es un pin de alimentación, no el nivel de los GPIO. Mantener la vista superior y localizar pin1 en la placa real antes de contar.</p><p>Esta equivalencia corresponde al <b>header y al circuito</b>. La comprobación del sistema operativo, librerías y temporización del enlace se deja para la fase de software; no se ha cambiado código de las Pi.</p><p class="hint">Verificación con documentación oficial: <a href="https://www.raspberrypi.com/products/raspberry-pi-2-model-b/">Pi 2 Model B, incluida revisión1.1 y header de 40 pines</a>; <a href="https://pip-assets.raspberrypi.com/categories/685-whitepapers-app-notes-compliance-guides/documents/RP-006553-WP/A-history-of-GPIO-usage-on-Raspberry-Pi-devices-and-current-best-practices">historia de GPIO, páginas4–6: continuidad del header de 40 pines y diagrama</a>; esquemas J8 de <a href="https://datasheets.raspberrypi.com/rpi2/raspberry-pi-2-b-reduced-schematics.pdf">Pi 2 (documento publicado rev1.2)</a> y <a href="https://datasheets.raspberrypi.com/rpi3/raspberry-pi-3-b-reduced-schematics.pdf">Pi 3 B</a>.</p></section>
<section class="card" id="layout"><span class="kicker">UN FARO · REPETIR PARA EL SEGUNDO</span><h2>Montaje para Pi 2 B v1.1 o Pi 3 B: mismas conexiones.</h2><div class="controls"><button data-version="basic" aria-pressed="true">Básico</button><button data-version="rgb" aria-pressed="false">Básico + RGB cátodo común</button><button data-version="both" aria-pressed="false">Ver ambos</button><button id="print">Imprimir / guardar PDF</button></div><div class="controls"><label>Bloque: <select id="stage"><option value="">Todos</option>{''.join('<option value="'+k+'">'+v+'</option>' for k,v in LABEL.items())}</select></label><label>Red: <select id="net"><option value="">Sin resaltar</option></select></label><button id="clear">Limpiar resaltado</button></div><p class="hint">Los componentes se identifican por referencia (R4, C2…). Sus valores y agujeros están en la tabla de piezas. Los cables pueden cruzarse porque están aislados; solo cuentan sus extremos y los clips internos. Toca un agujero para iluminar todo su grupo eléctrico. Al imprimir aparecen ambos planos y las tablas de la versión elegida.</p></section>
'''
for name,svg,label in [('basic',SA,'Básico sin RGB'),('rgb',SB,'Básico + RGB cátodo común')]:
 l=plans[name];holes=sum(not h.startswith(('PI:','EXT:')) for h in l['occupied'])
 PAGE+=f'''<section class="card board-version {'hidden' if name=='rgb' else ''}" data-board="{name}"><span class="kicker">{label.upper()}</span><h2>{label}</h2><p>{holes} agujeros de protoboard utilizados · {len(l['wires'])} jumpers · 830 agujeros modelados. Se cuentan extremos separados; no se permite insertar dos puntas en un agujero.</p><div class="controls"><button data-focus="full">General</button><button data-focus="pi">Pi</button><button data-focus="leds">LEDs</button><button data-focus="panic">Botón S1</button><button data-focus="pot">RV1</button><button data-focus="rx">LM393/receptor</button><button data-focus="tx">IR/Q1</button><button data-focus="optics">Frente óptico</button>{'<button data-focus="rgb">RGB confirmado</button>' if name=='rgb' else ''}<button data-zoom="-">−</button><button data-zoom="+">+</button><button data-fit>Encajar ancho</button><a href="faronet-breadboard-{name}.svg">Abrir SVG independiente</a></div><div class="viewport">{svg}</div><div class="readout">Toca un agujero o elige una red para seguir su conexión.</div></section>'''
PAGE+=f'''<section class="card" id="optical-front"><span class="kicker">FRENTE ÓPTICO · AMBAS LENTES HACIA EL ESTE</span><h2>D1 y Q2 miran a la derecha del plano.</h2><p><b>Q2/PT333 se mueve al extremo derecho:</b> emisor E en <code>c60</code>, colector C en <code>c61</code>. <b>D1/IR mantiene</b> ánodo A en <code>i60</code> y cátodo K en <code>i61</code>. Los cuerpos se montan horizontales, con la punta de la lente hacia el este y despejada del borde. No dejarlos verticales mirando al techo. El dibujo muestra el recorrido de las patas; no es una plantilla de doblado a escala.</p><div class="notice"><b>Si ya habían iniciado el montaje:</b> retirar Q2 de c40/c41. Su retorno anterior <code>a40 → TG:31</code> pasa a <code>a60 → TG:49</code>. Añadir <code>b61 → c41</code> para SENSE. Conservar <code>b41 → b37</code> y R4 <code>a47 → a41</code>: a41/b41/c41 comparten el mismo clip. <b>c41 ahora recibe un jumper, no una pata de Q2.</b> No unir el emisor con el colector al doblar las patas.</div><div class="two-col"><div><h3>Cómo montar las lentes.</h3><ol><li>Antes de doblar o recortar, marcar A/K del emisor y E/C del PT333. Conservar su correspondencia con los agujeros indicados.</li><li>Formar las patas metálicas para dejar el eje de cada lente paralelo a la mesa y hacia el borde derecho. Sujetar la parte metálica para no tirar del encapsulado; no doblar pegado al plástico ni usar la lente como palanca.</li><li>Apoyar y fijar ambos cuerpos para que mantengan altura y dirección. No depender solo de la flexión de las patas. Si están cortadas o no alcanzan sin tensión mecánica, usar extensiones cortas aisladas manteniendo el mapa de agujeros.</li><li>Dejar visible la lente. Un pequeño tubo opaco alrededor de Q2 puede ayudar a separar la recepción de la luz local; no tapar su apertura frontal.</li></ol></div><div><h3>Dirección de la lente y de la luz.</h3><p>Ambas lentes se orientan <b>hacia el este</b>. La luz de D1 sale hacia la derecha; la luz recibida entra a Q2 desde la derecha y viaja hacia la izquierda. Por eso las flechas de luz de D1 y Q2 son opuestas, aunque sus cuerpos apunten al mismo lado.</p><p>R4, LM393 y el resto del receptor conservan sus posiciones y valores. El jumper SENSE <code>b61 → c41</code> enlaza el frente con el receptor; ajustar su longitud al trayecto real y evitar lazos largos. Su presencia queda verificada por continuidad, pero la velocidad y BER todavía requieren probar el montaje.</p><p>El cambio añade <b>un jumper por Faro</b>. No añade resistencias, IC ni otro componente electrónico. GPIO y polaridad lógica permanecen iguales.</p></div></div><h3>Cómo enfrentar los dos Faros.</h3><div class="face-wrap">{FACING}</div><p>Construir ambos con el mismo plano. En la mesa, <b>girar el segundo conjunto completo 180°</b> para que su frente mire al primero. Ajustar altura y posición hasta enfrentar cada emisor con el fototransistor del otro Faro. Comenzar cerca y probar una dirección por vez, luego aumentar la distancia.</p><p><a href="faronet-facing-layout.svg">Abrir esquema de colocación independiente</a>. Precauciones de formado de patas basadas en <a href="https://www.everlight.com/wp-content/uploads/2021/02/A93B-SYG-S530-E2.pdf">recomendaciones generales de Everlight</a>; ese documento no identifica el modelo del IR comprado.</p></section>
<section class="card" id="reading"><span class="kicker">CÓMO LEER LOS AGUJEROS</span><h2>La columna es el número; la fila es la letra.</h2><div class="two-col"><div><p><code>c38</code> es fila c, columna 38. En esa columna, <b>a38, b38, c38, d38 y e38 están unidos por un clip</b>. Las filas f–j de columna38 forman otro clip, separado por la ranura central.</p><p>Un resistor de <code>a38</code> a <code>c38</code> quedaría puenteado por el mismo clip. Los resistores de este plan se conectan entre clips o rieles distintos.</p><p>Los rieles usan otra numeración: <code>T3:30</code> es el punto 30 de la tira de 3,3 V. No significa «columna 30» de la zona a–j. Sus agujeros se resaltan al seleccionarlos.</p></div><div><p><b>T3</b> = 3,3 V superior; <b>TG</b> = GND superior; <b>B5</b> = 5 V inferior; <b>BG</b> = GND inferior. Los cuatro tienen 50 agujeros y un puente entre 25 y 26.</p><p>Comprobar continuidad del riel real: un tablero puede tener cortes en otros puntos. El color impreso no suministra voltaje; los jumpers a la Pi sí. Los puentes 25↔26 unen mitades del <b>mismo</b> riel.</p><p class="notice"><b>W04 une exclusivamente TG:4 ↔ BG:4: GND superior con GND inferior.</b> Ahora se dibuja por fuera del borde izquierdo para distinguir sus extremos. T3:4 es +3,3 V y B5:4 es +5 V: ninguno recibe este jumper. Unir un positivo con GND produciría un cortocircuito. Un cable que cruza una línea del dibujo no hace contacto allí; solo se insertan sus dos extremos.</p><p>La vista de la Pi es desde componentes, con pin1 arriba a la izquierda de su header dibujado. Ubicar el pin1 real y orientar el mapa; no contar desde una esquina elegida al azar.</p></div></div></section>
<section class="card" id="wires"><span class="kicker">LISTA DE JUMPERS</span><h2>Usar estas direcciones al montar.</h2><div class="controls"><label>Versión: <select id="table-version"><option value="basic">Básico</option><option value="rgb">Con RGB</option></select></label><input type="search" id="search" placeholder="Buscar c38, GPIO, R5…" aria-label="Buscar conexión"><button id="csv">Descargar lista CSV</button></div><p class="hint">W01, W02… identifican cables; «futuro J1» identifica el conector de la perfboard del esquema anterior. No son el mismo tipo de referencia.</p><div class="bb-table-wrap"><table><thead><tr><th>Cable</th><th>Desde</th><th>Hasta</th><th>Red</th><th>Propósito</th></tr></thead><tbody id="wire-table"></tbody></table></div></section>
<section class="card" id="parts"><span class="kicker">COLOCACIÓN DE LAS PIEZAS</span><h2>Valores y terminales, sin adivinar huellas.</h2><p>La tabla sigue la versión elegida arriba. Los terminales 1/2 de resistencias o cerámicos son etiquetas de esta lista y no indican polaridad. En U1 los números sí son los pines físicos; en DL1, L1–L4 conservan la orientación de la prueba del equipo. En las conexiones externas se usan los contactos funcionales identificados.</p><div class="bb-table-wrap"><table><thead><tr><th>Pieza</th><th>Valor</th><th>Terminal → agujero / contacto</th><th>Bloque</th></tr></thead><tbody id="part-table"></tbody></table></div>
<div class="two-col"><div><h3>LM393: muesca a la derecha.</h3><p>Arriba, <code>e35/e36/e37/e38</code> son pines <b>4/3/2/1</b>. Abajo, <code>f35/f36/f37/f38</code> son <b>5/6/7/8</b>. El pin1 queda arriba a la derecha.</p><p><b>U1.7 en f37 queda libre:</b> no añadir cables al clip f–j37. No se une con el clip a–e37, que sí transporta SENSE.</p><p>El cerámico C2 se coloca cerca de U1.8 y su retorno va a U1.4. C3 va a VBIAS. C1, electrolítico, usa su positivo en B5:44 y negativo en BG:46.</p></div><div><h3>Q1, PT333, S1 y RV1.</h3><p><b>Q1:</b> E=j55, B=j56, C=j57, cara plana hacia j. EBC es la orientación indicada por el equipo; el dibujo no identifica el fabricante a partir de «A331».</p><p><b>Q2/PT333:</b> E=c60, C=c61. La hoja Everlight muestra emisor largo (pin1) y colector corto (pin2); si se recortaron las patas, confirmar por su encapsulado/datos, no por longitud.</p><p><b>S1/RV1:</b> ahora se dibujan sobre la protoboard, usando huellas candidatas DTS-6 y RM063. S1 cruza la ranura en columnas 14/16; RV1 usa columnas 43/44/45. Seguir la sección «Botón y RV1»: incluye ajuste de patas, pruebas y alternativa RM065. Confirmar cada pieza antes de conectar la Pi.</p></div></div>
<p class="notice">La rama RGB se actualizó por la prueba del equipo: <b>cátodo común L2 a GND</b>, con L1/L3/L4 como ánodos de rojo/verde/azul. No montar el LS125 ni conectar un común a 5 V siguiendo el dibujo anterior. Usar exclusivamente las conexiones RGB actuales; el núcleo básico mantiene sus posiciones.</p>
<p>Compatibilidad de Pi: <a href="#pi-compatibility">Pi 2 B v1.1 y Pi 3 B usan las mismas conexiones</a>. Guía ilustrada de polaridad y encapsulados: <a href="../faronet-full-circuit.html#components">circuitos completos anteriores</a>. Las longitudes/cuerpos del dibujo de protoboard son ilustrativos: adaptar las patas sin forzarlas.</p></section>
<section class="card" id="switch-pot"><span class="kicker">S1 Y RV1 · PROPUESTA SOBRE LA PROTOBOARD</span><h2>Los dos componentes ya tienen una posición en el tablero.</h2><p>Se sustituyen las conexiones externas de la revisión anterior por huellas basadas en las referencias nuevas. <b>Son modelos candidatos:</b> el equipo dijo «parece DTS-644R» y «si es el mismo, AD8289»; la foto es una referencia de producto. Verificar las piezas propias con las pruebas siguientes antes de conectar la Pi. No hace falta comprar otro botón ni otro potenciómetro si las piezas pasan estas comprobaciones.</p><div class="notice"><b>Cambios de agujero frente a v5:</b> Pi físico18/GPIO24 ahora llega a <code>d14</code> (antes e14). S1 ocupa e14/f14/e16/f16. RV1 va a d43/c44/d45. R6 termina ahora en <code>e44</code> (antes d44), y el jumper de VTH a U1.3 parte de <code>a44</code> (antes b44). Se quitan los cinco jumpers que iban a terminales externos y se añade b47↔b43. Las tablas de esta revisión ya incluyen estos cambios.</div><div class="face-wrap">{CONTROL_DETAIL}</div><p><a href="faronet-button-trimpot.svg">Abrir detalle de S1 y RV1</a>. El dibujo muestra conexiones y orientación; no es una plantilla a escala.</p><div class="two-col"><div><h3>S1: pulsador táctil de la familia DTS-6.</h3><p>La ficha Diptronics muestra <b>1–2 unidos permanentemente</b> y <b>3–4 unidos permanentemente</b>; al pulsar se unen ambas parejas. No hay terminal NC. Los números son los de la ficha, que pueden no estar impresos en el botón. En el plano, su vista superior se gira <b>90° en sentido horario</b>: patas 3/4 a la izquierda y 1/2 a la derecha.</p><ul><li>3 → <code>e14</code> y 4 → <code>f14</code>: PANIC. Pi físico18 → d14 y R12 de 10 kΩ → b14.</li><li>1 → <code>e16</code> y 2 → <code>f16</code>: GND; b16 → TG:14.</li><li>Sin pulsar: GPIO24 permanece alto por R12. Pulsando: se conecta a GND y lee bajo. Los contactos pueden rebotar; el antirrebote se resuelve en software.</li></ul><p><b>Encaje real:</b> la huella de la ficha es <b>6,5 × 4,5 mm</b>. En nuestro montaje, la ranura e–f mide 7,62 mm y las columnas 14–16 distan 5,08 mm. Hay que abrir suavemente las porciones libres de las patas, aproximadamente 0,56 mm por lado a través de la ranura y 0,29 mm por lado entre columnas. Estas cifras son la diferencia geométrica del modelo, no una tolerancia garantizada del botón. Sujetar las patas al ajustarlas; no torcer el cuerpo ni usar la protoboard para forzar el encaje. Si no asienta sin esfuerzo, usar los jumpers disponibles hacia los mismos clips de las columnas 14/PANIC y 16/GND.</p><ol><li>Fuera del circuito y sin energía, identificar por continuidad las dos parejas permanentes. Si no se distingue la numeración, etiquetar parejas A/B; conectarlas a PANIC/GND con el mismo patrón, sin depender del número impreso.</li><li>Orientar el botón de modo que una pareja quede verticalmente en e14/f14 y la otra en e16/f16. <b>No girarlo 90° respecto de esta posición:</b> una pareja podría unir PANIC y GND continuamente.</li><li>Insertar solo si encaja sin forzar. Antes de conectar la Pi, medir entre d14 y b16: no debe haber continuidad de baja resistencia al soltar, y debe aparecer al pulsar.</li><li>Tras verificar alimentación, comprobar aproximadamente 3,3 V en d14 al soltar y 0 V al pulsar. La especificación 12 V de la ficha es una capacidad del contacto; no es una alimentación que haya que aplicar.</li></ol><p>Fuentes: <a href="https://docs.rs-online.com/331f/A700000011971633.pdf">PDF aportado por el equipo</a> y <a href="sources/Diptronics-DTS-6.pdf">ficha Diptronics DTS-6 consultada, pp. 1–2</a> (<a href="https://www.tokiwaelenet.jp/html/upload/pdf/product/0000032005DTS-6_Spec_02.pdf">copia del distribuidor Tokiwa</a>). El color del botón no confirma por sí solo el sufijo R.</p></div><div><h3>RV1: trimpot de 10 kΩ, código de tienda AD8289.</h3><p><a href="https://www.microjpm.com/products/trimpot-potenciometro-miniatura-10-k%CF%89/">MicroJPM identifica AD8289 como su producto de 10 kΩ</a> y lo describe como compatible con protoboard. Enlaza fichas RM065/RM063 y KLS4-WH06-1A: el SKU no identifica un único fabricante. La foto se parece al <b>estilo vertical RM063</b>, con ajuste lateral. Ese es el cuerpo que se dibuja, mirando hacia la fila j.</p><ul><li>Extremo 1 → <code>d43</code>, VBIAS, con jumper b47↔b43.</li><li>Cursor 2 → <code>c44</code>, VTH, en el mismo clip que R6/e44 y el jumper a44↔a36 hacia U1.3.</li><li>Extremo 3 → <code>d45</code>, GND, mediante a45↔TG:36.</li></ul><p>El estilo RM063 tiene 5 mm entre extremos y 2,5 mm de desplazamiento del cursor. La rejilla usada aproxima esas distancias con 5,08 y 2,54 mm. Las tres patas quedan en columnas distintas, <b>43/44/45</b>; poner extremos y cursor en filas distintas de una misma columna los cortocircuitaría a través del clip.</p><ol><li>Aislado de Pi y circuito, usar escala de resistencia. Buscar la pareja cuya resistencia se mantiene aproximadamente en 10 kΩ al girar: esos son los extremos. La tercera pata es el cursor.</li><li>Entre cursor y cada extremo la lectura debe cambiar suavemente al girar; cerca de cada tope, una lectura baja y la otra se aproxima a la resistencia total. No forzar los topes.</li><li>Identificar el estilo por sus patas y encaje. En el vertical de la foto, el cursor queda centrado y retrasado una fila, en c44, con los extremos en d43/d45. Comprobarlo con el multímetro; no decidirlo por el color de la carcasa.</li><li>Al montar y alimentar, medir VBIAS y VTH respecto a GND y ajustar VTH entre los niveles SENSE medidos con luz y sin luz. R6 añade histéresis: la posición de la perilla no indica una tensión calibrada.</li></ol><p><b>Si su pieza es el RM065 horizontal:</b> la ficha indica un desplazamiento del cursor de 5 mm, en lugar de 2,5 mm. Mantener extremos en d43/d45 y colocar únicamente el cursor en <code>b44</code>, que está libre en este plano; c44 queda libre. b44, c44, a44 y e44 pertenecen al mismo clip VTH, de modo que el cableado eléctrico restante no cambia. No colocar dos potenciómetros: son dos huellas alternativas para una sola pieza.</p><p>Si los extremos quedan invertidos, solo cambia el sentido de giro; <b>el cursor sí debe ir a VTH</b>. VBIAS no es el riel de 5 V. Si la pieza no coincide con ninguna huella o necesita fuerza para insertarse, usar jumpers respetando extremos VBIAS/GND y cursor VTH.</p><p>Fuente dimensional: <a href="sources/RM065.pdf">Runtron RM065 y RM063, pp. 1–2</a> (<a href="https://www.yourduino.ru/RM065.pdf">copia consultada</a>). El valor de 10 kΩ proviene de la ficha del vendedor y debe medirse en la pieza propia.</p></div></div></section>
<section class="card" id="polarity"><span class="kicker">IDENTIFICAR PIEZAS · SIN SUPONER POR LA FORMA</span><h2>Orientación antes de insertar.</h2><div class="two-col"><div><h3>Q1: transistor de tres patas.</h3><p>Con cara plana hacia ustedes y patas hacia abajo, el equipo indica <b>E–B–C</b> de izquierda a derecha. En la vista superior del dibujo, la cara plana mira hacia j; E entra en j55, B en j56 y C en j57. Un 2N2222 de otro fabricante podría tener otro orden: el dibujo conserva la orientación confirmada por el equipo.</p><h3>PT333: no es un LED.</h3><p>En la hoja Everlight, <b>pin1/emisor = pata larga</b> y <b>pin2/colector = corta</b>, antes de recortarlas. E va a c60 y C a c61. No aplicar al PT333 la regla de ánodo largo de un LED.</p></div><div><h3>C1: electrolítico polarizado.</h3><p>Buscar la franja con símbolos <b>−</b> en el cuerpo: corresponde al negativo y va a BG:46/GND. El otro terminal es positivo y va a B5:44/5 V. En una pieza nueva sin recortar suele ser el más largo. Si ambas indicaciones no coinciden, resolverlo antes de alimentar.</p><p><b>100 µF</b> es su capacitancia; <b>63 V</b> es su tensión nominal máxima, no la alimentación a aplicar. C1 ayuda a filtrar la alimentación. No sustituye C2/C3, cerámicos de <b>100 nF = 0,1 µF</b>, que se necesitan cerca de los IC.</p><p>Las resistencias y los cerámicos de esta lista no tienen polaridad. En LEDs comunes, pata corta/lado plano suele indicar cátodo; confirmar las piezas recortadas con prueba de diodo. En el RGB usar el procedimiento específico siguiente.</p></div></div></section>
<section class="card" id="rgb-test"><span class="kicker">RESULTADO DEL MULTÍMETRO · INFORMADO POR EL EQUIPO</span><h2>RGB confirmado: cátodo común en L2.</h2><p>La punta negra permaneció en L2. Roja en L1 encendió rojo; en L3, verde; en L4, azul. El resultado identifica <b>L2 como cátodo común</b> y los otros tres terminales como ánodos. Conservar exactamente la misma orientación al identificar L1–L4: este resultado no permite inferir desde qué cara se observa el encapsulado.</p><div class="bb-table-wrap"><table><thead><tr><th>Pata probada</th><th>Función</th><th>Agujero DL1</th><th>Conexión</th></tr></thead><tbody><tr><td>L1</td><td>Ánodo rojo</td><td><code>d23</code></td><td>GPIO5 / físico29 → R13, 1 kΩ → L1</td></tr><tr><td>L2</td><td>Cátodo común</td><td><code>d24</code></td><td><code>e24</code> → <code>TG:20</code> → GND</td></tr><tr><td>L3</td><td>Ánodo verde</td><td><code>d25</code></td><td>GPIO6 / físico31 → R14, 1 kΩ → L3</td></tr><tr><td>L4</td><td>Ánodo azul</td><td><code>d26</code></td><td>GPIO13 / físico33 → R15, 1 kΩ → L4</td></tr></tbody></table></div><div class="two-col"><div><h3>Montar una resistencia por color.</h3><p>R13 va de <code>g18</code> a <code>g21</code>; R14, de <code>g23</code> a <code>g26</code>; R15, de <code>g28</code> a <code>g31</code>. Los jumpers de GPIO y de cada ánodo están en la tabla de cables. No colocar una única resistencia en L2.</p><p>Se eliminan del RGB <b>U2/LS125, C4 y R16/R17/R18</b>. Son piezas disponibles que ya no se necesitan en esta versión. El LM393 conserva C2 y VBIAS conserva C3. No modificar esas partes al retirar C4.</p></div><div><h3>Lógica del programa: activo alto.</h3><p><b>HIGH = color encendido; LOW = apagado.</b> Pedir GPIO5/6/13 como salidas con valor inicial bajo, probar un color a la vez y volver a bajo al terminar. La lógica invertida del antiguo /OE ya no aplica. El significado de las luces de depuración empieza cuando el programa inicializa sus salidas.</p><p>Las salidas son de <b>3,3 V</b>. Con 1 kΩ, la corriente se limita aproximadamente a (V_GPIO − V_LED)/1000; por ejemplo, unos 1,3 mA con V_LED de 2 V. Es una estimación, no una medición de esta pieza. Si verde/azul quedan tenues, medir antes de cambiar resistencias; no conectar el RGB a 5 V con este cableado.</p></div></div><ol><li>Sin alimentación, orientar el LED como en la prueba y colocar L1/L2/L3/L4 en d23/d24/d25/d26. Adaptar las patas con cuidado; si su separación no encaja, usar jumpers a cuatro columnas separadas respetando el mapa.</li><li>Comprobar que L2 tiene continuidad con GND y que cada ánodo alcanza su GPIO a través de su propia resistencia de 1 kΩ.</li><li>Inicializar los tres GPIO en LOW. Probar HIGH solamente en GPIO5 (rojo), después GPIO6 (verde), después GPIO13 (azul), apagando cada uno entre pruebas. Verificar colores y medir si hace falta.</li><li>Para el segundo Faro, repetir la prueba de diodo en su propia unidad. La identificación del primer RGB no garantiza el orden del segundo.</li></ol><p>La polaridad del multímetro concuerda con la prueba de diodos descrita por <a href="https://www.fluke.com/en/learn/blog/digital-multimeters/how-to-test-diodes">Fluke</a>. La elección de GPIO directo con resistencias se apoya en las <a href="https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio">características oficiales de Raspberry Pi</a>.</p></section>
<section class="card" id="comparison"><span class="kicker">COMPARACIÓN CON LO RECIBIDO</span><h2>Qué coincide y qué se corrigió o conservó.</h2>{table(['Clasificación','Punto revisado','Conclusión'],FINDINGS)}<h3>GPIO / físico.</h3>{table(['Señal','Recibido: BCM / físico','Este montaje: BCM / físico'],PINCOMPARE)}<h3>Comparar por función, no por el número R.</h3>{table(['Función','Recibido','Nuestro esquema conservado'],FUNCTIONS)}<details><summary>Ver SVG original recibido, sin modificar</summary><p class="hint">Referencia para comparación. Su circuito y sus GPIO no son la lista de montaje de este archivo.</p><div class="viewport">{original}</div></details></section>
<section class="card" id="tests"><span class="kicker">ANTES DE ENERGIZAR</span><h2>Revisado por continuidad; pendiente de probar físicamente.</h2><p>Se verificaron automáticamente estas condiciones sobre el modelo de los clips y los extremos de todos los cables:</p><ul>{''.join('<li>'+x+'</li>' for x in A.checks)}</ul><p class="notice good">Se comprobó que el validador rechaza errores introducidos deliberadamente: unir 5 V con 3,3 V, llevar un jumper al clip de otra señal o quitar el puente que alimenta media tira. Un resultado correcto de este modelo no mide una tensión, una corriente ni un fotón.</p><ol><li>Sin fuente y con condensadores descargados, medir continuidad de los cuatro rieles y sus puentes. Confirmar que a–e de una columna se unen, que f–j se unen por separado y que la ranura los separa.</li><li>Clasificar las resistencias disponibles: en el básico se usan cuatro de 1 kΩ y tres de 10 kΩ por Faro. RGB añade únicamente tres de 1 kΩ por Faro. U2, C4 y R16–R18 no se montan; básico + RGB usa 14 resistencias fijas y dos cerámicos por Faro. Los trimpots no sustituyen las fijas. No añadir 100 Ω al IR por una corriente supuesta.</li><li>Comprobar la orientación de Q1, Q2 y el IR; C1 por la marca del negativo. R1 de 1 kΩ para primera prueba sin ficha; después decidir si 330 Ω es adecuado midiendo corriente.</li><li>Conectar solo alimentación, medir 5 V, 3,3 V y VBIAS respecto a GND. Mantener desconectados los GPIO de señal durante esa comprobación.</li><li>Probar los indicadores y pánico con los BCM de esta lista. Inicializar TX/LEDs y los tres GPIO RGB en bajo (apagados). RGB es activo alto; retirar la lógica invertida del antiguo /OE. RX y pánico son entradas.</li><li>Probar detector/comparador estáticos. SENSE debe bajar con haz; ajustar VTH entre los niveles de haz/sin haz. Medir RX dentro de 0–3,3 V antes de unirlo al físico13.</li><li>Probar pulsos lentos y después secuencias conocidas. Fijar los dos Faros y separar ópticamente emisor local/receptor para evitar autoiluminación. Ambos miran al este del plano individual; girar el Faro B 180° y alinear D1 de cada Faro con Q2 del otro según la sección de lentes. El tubo opaco sugerido en el recibido puede ayudar; no demuestra un alcance.</li><li>Registrar resultados a tres distancias. Solo después de calificar el prototipo, trasladar el circuito a perfboard/PCB soldada y repetir las mediciones.</li></ol><div class="checklist">{''.join('<label><input type="checkbox">'+x+'</label>' for x in ['Rieles y ranura verificados con multímetro.','Q1 EBC y PT333 E/C contrastados con las piezas.','Valores medidos y polaridad de C1 comprobada.','No hay cortos entre 5 V, 3,3 V y GND.','RX medido antes de conectar su GPIO.','RGB: L2 a GND; L1 rojo/L3 verde/L4 azul con una resistencia por color. Otra unidad verificada por separado.','Pruebas de enlace y resultados físicos registrados.'])}</div></section>
<section class="card" id="sources"><span class="kicker">REFERENCIAS</span><h2>Fuentes y límites de esta revisión.</h2><ul><li><a href="https://datasheets.raspberrypi.com/rpi3/raspberry-pi-3-b-reduced-schematics.pdf">Raspberry Pi 3 B: header oficial</a>.</li><li><a href="https://www.ti.com/lit/ds/symlink/lm393-n.pdf">TI LM393</a>, pinout, salida abierta y rango de entrada.</li><li><a href="https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio">Raspberry Pi: GPIO de 3,3 V, uso de LEDs con resistencias y características de corriente</a>. Justifica la conexión RGB directa a baja corriente.</li><li><a href="https://www.everlight.com.cn/wp-content/plugins/ItemRelationship/product_files/pdf/PT333-3B.pdf">Everlight PT333-3B, página6</a>, emisor/colector y dibujo de patas.</li><li><a href="https://learn.adafruit.com/breadboards-for-beginners/breadboards">Adafruit: estructura de protoboards</a>.</li><li><a href="../faronet-full-circuit.html">Nuestro circuito completo de referencia</a>. Núcleo y asignación BCM conservados; su antiguo RGB con LS125 fue sustituido por esta revisión de cátodo común.</li></ul><p>Archivos recibidos: circuito-faro.md, faro-sim.html, gen_protoboard.py, pi-environment.md y protoboard-faro.svg. Se leyeron como propuestas del equipo; no se ejecutó el generador ni se modificaron los originales.</p><p>Se reutiliza el inventario comunicado: dos PT333, dos IR, dos LM393, seis cerámicos, dos trimpots, las resistencias necesarias y un RGB de cuatro patas probado. LS125/LS27 quedan disponibles sin uso en este montaje. Se requiere un RGB por Faro; la prueba de una unidad no identifica automáticamente la otra. Los otros componentes disponibles sin uso no se fuerzan dentro del circuito.</p><p>Validación estática del modelo, sin prototipo conectado: no garantiza velocidad, BER, alcance ni tolerancias. El esquema físico requiere las comprobaciones de puesta en marcha descritas.</p></section><footer>FaroNet · protoboard revisada v6 · 18 octubre 2026 · Pi 2 B v1.1 / Pi 3 B: mismo header y cableado · Un Faro por tablero; repetir para el segundo · HTML/SVG autónomos, tablas y controles sin dependencias de Internet. RGB de 4 patas confirmado por equipo: cátodo común L2; L1 rojo/L3 verde/L4 azul.</footer>
'''

JS='''
const plans=PLANS;const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=s=>document.querySelector(s);let net='';
const scopes={full:[0,0,2500,1420],pi:[50,110,430,720],leds:[660,135,540,460],panic:[925,135,270,360],pot:[1555,132,260,220],rx:[1430,80,620,500],tx:[1790,275,650,430],optics:[1850,45,620,515],rgb:[1090,80,620,510]};
function pick(n,hole){net=n;$('#net').value=n;document.querySelectorAll('.bb-scene').forEach(svg=>{svg.classList.toggle('has-net',Boolean(n));svg.querySelectorAll('[data-net]').forEach(x=>x.classList.toggle('bb-pick',Boolean(n)&&x.dataset.net===n));});document.querySelectorAll('[data-board]').forEach(card=>{const p=plans[card.dataset.board];const ends=p.parts.flatMap(c=>Object.entries(c.pins).filter(([pin,a])=>p.hole_nets[a]===n).map(([pin,a])=>c.ref+'.'+pin+'='+a));card.querySelector('.readout').innerHTML=!n?'Sin red seleccionada.':(hole?'<b>'+esc(hole)+'</b> · ':'')+'<b>'+esc(n)+'</b> · '+(n.startsWith('NC_')?'Dejar aislado. ':'')+ends.map(esc).join(' ↔ ');});}
for(const n of [...new Set(Object.values(plans.rgb.hole_nets))].sort()){const o=document.createElement('option');o.value=n;o.textContent=n;$('#net').append(o);}
$('#net').addEventListener('change',e=>pick(e.target.value));$('#clear').addEventListener('click',()=>{pick('');$('#stage').value='';stage();});
document.querySelectorAll('.bb-scene [data-hole]').forEach(x=>x.addEventListener('click',ev=>{ev.stopPropagation();pick(x.dataset.net,x.dataset.hole);}));document.querySelectorAll('.bb-scene .bb-jumper').forEach(x=>x.addEventListener('click',()=>pick(x.dataset.net)));
function stage(){const v=$('#stage').value;document.querySelectorAll('.bb-scene [data-stage]').forEach(x=>x.classList.toggle('stage-dim',Boolean(v)&&x.dataset.stage!==v));}
$('#stage').addEventListener('change',stage);
function size(svg,w){const b=svg.getAttribute('viewBox').split(' ').map(Number);svg.style.width=w+'px';svg.style.height=(w*b[3]/b[2])+'px';}
function fit(card){const svg=card.querySelector('.bb-scene'),v=card.querySelector('.viewport');if(v.clientWidth)size(svg,v.clientWidth);}
document.querySelectorAll('[data-version]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-version]').forEach(x=>x.setAttribute('aria-pressed',x===b));document.querySelectorAll('[data-board]').forEach(c=>{c.classList.toggle('hidden',b.dataset.version!=='both'&&c.dataset.board!==b.dataset.version);if(!c.classList.contains('hidden'))fit(c);});if(b.dataset.version!=='both')$('#table-version').value=b.dataset.version;render();}));
document.querySelectorAll('[data-board]').forEach(card=>{const svg=card.querySelector('.bb-scene'),v=card.querySelector('.viewport');card.querySelectorAll('[data-focus]').forEach(b=>b.addEventListener('click',()=>{const box=scopes[b.dataset.focus];svg.setAttribute('viewBox',box.join(' '));const cap=Math.min(740,innerHeight*.70);size(svg,b.dataset.focus==='full'?v.clientWidth:Math.min(v.clientWidth,cap*box[2]/box[3]));v.scrollTo(0,0);}));card.querySelectorAll('[data-zoom]').forEach(b=>b.addEventListener('click',()=>size(svg,Math.min(5000,Math.max(300,parseFloat(svg.style.width||v.clientWidth)*(b.dataset.zoom==='+'?1.25:.8))))));card.querySelector('[data-fit]').addEventListener('click',()=>fit(card));fit(card);});
function render(){const p=plans[$('#table-version').value],q=$('#search').value.toLowerCase();$('#wire-table').innerHTML=p.wires.filter(w=>Object.values(w).join(' ').toLowerCase().includes(q)).map(w=>'<tr><td><code>'+w.id+'</code></td><td><code>'+esc(w.a)+'</code></td><td><code>'+esc(w.b)+'</code></td><td><code>'+esc(w.net)+'</code></td><td>'+esc(w.why)+'</td></tr>').join('');$('#part-table').innerHTML=p.parts.filter(c=>(c.ref+' '+c.value+' '+Object.values(c.pins).join(' ')).toLowerCase().includes(q)).map(c=>'<tr><td><b>'+c.ref+'</b></td><td>'+esc(c.value)+'</td><td>'+Object.entries(c.pins).map(([pin,h])=>esc(pin)+' → <code>'+esc(h)+'</code>').join('<br>')+'</td><td>'+esc(c.stage)+'</td></tr>').join('');}
$('#table-version').addEventListener('change',render);$('#search').addEventListener('input',render);render();$('#csv').addEventListener('click',()=>{const v=$('#table-version').value,quote=s=>'"'+String(s).replaceAll('"','""')+'"';const rows=[['Tipo','Referencia','Terminal/origen','Destino','Valor/red','Nota'],...plans[v].wires.map(w=>['Cable',w.id,w.a,w.b,w.net,w.why]),...plans[v].parts.flatMap(c=>Object.entries(c.pins).map(([pin,h])=>['Pieza',c.ref,pin,h,c.value,c.stage]))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\\uFEFF'+rows.map(r=>r.map(quote).join(',')).join('\\r\\n')],{type:'text/csv;charset=utf-8'}));a.download='FaroNet-protoboard-'+v+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500);});
const boxes=new Map();window.addEventListener('beforeprint',()=>document.querySelectorAll('.bb-scene').forEach(svg=>{boxes.set(svg,svg.getAttribute('viewBox'));svg.setAttribute('viewBox','0 0 2500 1420');}));window.addEventListener('afterprint',()=>boxes.forEach((v,svg)=>{svg.setAttribute('viewBox',v);size(svg,parseFloat(svg.style.width));}));$('#print').addEventListener('click',()=>window.print());
'''.replace('PLANS',json.dumps(plans,ensure_ascii=False))
(HERE/'faronet-breadboard-review.html').write_text(PAGE+'<script>'+JS+'</script></main></body></html>')
print('Review HTML written.')
