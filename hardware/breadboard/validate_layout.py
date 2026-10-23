"""Check the plans and prove selected wiring mistakes are rejected.

This imports our own generator, which also refreshes its HTML/SVG outputs.
It never executes the received third-party generator.
"""
import json
import xml.etree.ElementTree as ET
import generate_layout as g

def rejects(label, change, rgb=False):
    plan=g.make(rgb)
    change(plan)
    try:
        plan.validate()
    except AssertionError:
        return {'mutation':label,'rejected':True}
    raise AssertionError('Validator accepted: '+label)

results=[]
results.append(rejects('5 V joined to 3.3 V',lambda l:l.wire('T3:49','B5:49','5V','power','Injected short')))
results.append(rejects('TX jumper in base clip',lambda l:l.wire('g52','i56','TX','tx','Injected wrong clip')))
results.append(rejects('3.3 V half-rail bridge removed',lambda l:setattr(l,'wires',[w for w in l.wires if w['a']!='T3:25'])))
results.append(rejects('RGB common cathode joined to 5 V',lambda l:l.wire('a24','B5:49','5V','rgb','Injected wrong common'),rgb=True))
results.append(rejects('Front phototransistor collector shorted to emitter',lambda l:l.wire('d60','d61','SENSE','rx','Injected optical-front short')))
results.append(rejects('Button contact pairs bypassed by a jumper',lambda l:l.wire('a14','a16','PANIC','panic','Injected switch bypass')))
def rotate_switch_wrong(l):
    p=next(p for p in l.parts if p['ref']=='S1')
    p['pins']={'1':'e14','2':'e16','3':'f14','4':'f16'}
results.append(rejects('Switch rotated 90 degrees across PANIC and GND',rotate_switch_wrong))
results.append(rejects('Potentiometer wiper shorted to grounded end',lambda l:l.wire('b44','b45','VTH','rx','Injected wiper short')))
basic={p['ref']:p for p in g.A.parts}
rgb={p['ref']:p for p in g.B.parts}
assert all(p==rgb[ref] for ref,p in basic.items())
assert set(rgb)-set(basic)=={'DL1','R13','R14','R15'}
assert rgb['DL1']['pins']=={'L1':'d23','L2':'d24','L3':'d25','L4':'d26'}
assert g.B.hole_nets['d24']==g.B.hole_nets['PI:6']=='GND'
for pin,h,net,ref in [(29,'d23','RGB_R_A','R13'),(31,'d25','RGB_G_A','R14'),(33,'d26','RGB_B_A','R15')]:
    assert g.B.hole_nets[h]==net
    assert g.B.hole_nets['PI:'+str(pin)]!=net
    assert rgb[ref]['value']=='1 kΩ'
    a,b=rgb[ref]['pins'].values()
    assert g.B.hole_nets[a]==g.B.hole_nets['PI:'+str(pin)]
    assert g.B.hole_nets[b]==net
for name,l in [('basic',g.A),('rgb',g.B)]:
    root=ET.parse(g.HERE/f'faronet-breadboard-{name}.svg').getroot()
    assert len([e for e in root.iter() if 'data-hole' in e.attrib])==830
    assert l.nets['j55']=='GND' and l.nets['j56']=='Q_BASE' and l.nets['j57']=='IR_K'
    assert l.nets['c60']=='GND' and l.nets['c61']=='SENSE'
    assert l.hole_nets['c61']==l.hole_nets['c41']==l.hole_nets['b37']=='SENSE'
    assert any(w['a']=='b61' and w['b']=='c41' for w in l.wires)
    assert any(w['a']=='a60' and w['b']=='TG:49' for w in l.wires)
    assert 'c40' not in l.claims
    assert len([e for e in root.iter() if e.attrib.get('data-facing')=='east'])==2
    assert l.nets['e38']=='OPT_RX' and l.nets['f38']=='5V'
    assert l.hole_nets['a38']==l.hole_nets['e38']==l.hole_nets['PI:13']
    assert l.nets['f37']=='NC_U1_7'
    assert len({w['a'] for w in l.wires if w['a'].startswith('PI:')})==(11 if name=='rgb' else 8)
    parts={p['ref']:p for p in l.parts}
    assert parts['S1']['pins']=={'1':'e16','2':'f16','3':'e14','4':'f14'}
    assert all(l.hole_nets[h]=='GND' for h in ['e16','f16'])
    assert all(l.hole_nets[h]=='PANIC' for h in ['e14','f14','PI:18'])
    assert any(w['a']=='PI:18' and w['b']=='d14' for w in l.wires)
    assert parts['RV1']['pins']=={'1 extremo':'d43','2 cursor':'c44','3 extremo':'d45'}
    assert l.hole_nets['d43']=='VBIAS' and l.hole_nets['c44']=='VTH' and l.hole_nets['d45']=='GND'
    # A pressed button joins PANIC to GND, while R12 still separates 3V3.
    pressed=g.UF();pressed.p=dict(l.copper_roots)
    pressed.join('e14','e16')
    assert pressed.root('PI:18')==pressed.root('PI:6')
    assert pressed.root('PI:1')!=pressed.root('PI:6')!=pressed.root('PI:2')
    # The horizontal RM065 uses b44 instead of c44, the same electrical clip.
    assert 'b44' not in l.claims and l.hole_nets['b44']==l.hole_nets['c44']=='VTH'
    assert not any(h.startswith('EXT:') for h in l.claims)
    alternate=g.make(l.rgb,horizontal_trimpot=True)
    alt_parts={p['ref']:p for p in alternate.parts}
    assert alt_parts['RV1']['pins']=={'1 extremo':'d43','2 cursor':'b44','3 extremo':'d45'}
    assert all(parts[r]==p for r,p in alt_parts.items() if r!='RV1')
    assert alternate.wires==l.wires
    assert alternate.hole_nets['b44']=='VTH'
report={'valid':True,'base_placement_unchanged_with_rgb':True,'switch':'DTS-6 internal pairs 1-2 and 3-4 included; at rest PANIC separate from GND; pressed PANIC reaches GND without shorting 3V3 through copper','trimpot':'RM063 candidate footprint; RM065 wiper b44 reaches the same VTH clip; actual parts require measurement','rgb':'User-confirmed common cathode L2; L1 red, L3 green, L4 blue; 3.3 V GPIO through individual 1 kΩ; active high','mutations':results,
 'plans':{n:{'parts':len(l.parts),'jumpers':len(l.wires),'holes':830,'occupied_breadboard_holes':sum(not h.startswith(('PI:','EXT:')) for h in l.claims)} for n,l in [('basic',g.A),('rgb',g.B)]},
 'limits':'Copper connectivity and correspondence only. No physical measurements, optical qualification or BER test.'}
(g.HERE/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
