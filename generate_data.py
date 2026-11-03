import json, random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent / 'data'; ROOT.mkdir(parents=True, exist_ok=True)
def invoice(vendor='Aster Office Supply', vendor_id='V801', number='AST-2026-081', amount='1250.00', date='2026-10-01', description='Replacement workstation equipment', period='', currency='USD', kind='invoice'):
    return dict(vendor=vendor,vendor_id=vendor_id,number=number,amount=amount,date=date,description=description,period=period,currency=currency,kind=kind)
def change(a, **kw): return dict(a, **kw)
rng=random.Random(20261103)
train=[]
for i in range(240):
    a=invoice(vendor=f'{rng.choice(["Birch", "Maple", "Cobalt", "Orchard", "Nimbus"])} {rng.choice(["Services", "Equipment", "Supplies"])}',vendor_id=f'T{i}',number=f'TRN-{i+1000}',amount=f'{rng.randint(20,9000)}.00',date=f'2026-06-{rng.randint(1,20):02}',description=rng.choice(['Monthly IT support', 'Printer cartridge order', 'Electrical maintenance', 'Safety equipment delivery']),period='2026-06')
    mode=i%8
    if mode==0: b=change(a); y=1
    elif mode==1: b=change(a, number=a['number'].lower().replace('-', ' ')); y=1
    elif mode==2: b=change(a, vendor=a['vendor']+' LLC',vendor_id='ALIAS'+str(i),number=a['number']+'R'); y=1
    elif mode==3: b=change(a, number=a['number'].replace('1','I'),date='2026-06-25',description=a['description']+' copy'); y=1
    elif mode==4: b=change(a,number=f'TRN-{i+1001}',period='2026-07',date='2026-07-10'); y=0
    elif mode==5: b=change(a,vendor='Unrelated Catering',vendor_id='OTHER'+str(i),description='Catered lunch for guests'); y=0
    elif mode==6: b=change(a,number=f'OTHER-{i}',amount=f'{rng.randint(10000,20000)}.00',description='Separate equipment purchase'); y=0
    else: b=change(a,number=f'NEW-{i}',description='Unrelated service installation',period='2026-05'); y=0
    train.append(dict(id=f'T{i:03}',a=a,b=b,label=y))
cases=[]
def add(scenario,a,b,label,rationale,expected_route=None):
    row=dict(id=f'E{len(cases)+1:02}',scenario=scenario,a=a,b=b,label=label,rationale=rationale)
    if expected_route: row['expected_route']=expected_route
    cases.append(row)
a=invoice()
add('Exact resubmission',a,change(a),1,'Both records represent the same fictional equipment delivery.')
add('Case and punctuation',a,change(a,number='ast 2026 081'),1,'Only invoice-number presentation changed.')
add('Duplicate vendor master',a,change(a,vendor='Aster Office Supply LLC',vendor_id='V991'),1,'Fictional alias record; same underlying delivery.')
add('OCR character substitution',a,change(a,number='AST-2O26-O81'),1,'Letter O substituted for zero in the same document.')
add('Reissued number suffix',a,change(a,number='AST-2026-081R'),1,'Synthetic second billing copy, not a new obligation.')
add('Late reminder',a,change(a,date='2026-12-15',description='Replacement workstation equipment reminder'),1,'Date changed on a reminder for the same fictional order.')
add('Alias plus number change',a,change(a,vendor='Aster Office Supplies',vendor_id='V802',number='081-REISSUE'),1,'Label follows the invented delivery history; text alone is imperfect.')
add('Short supplier name',a,change(a,vendor='AOS',vendor_id='V803'),1,'AOS is a fictional alias unknown to the model.')
add('Different wording same delivery',a,change(a,number='AST081-COPY',description='Computers for the operations floor'),1,'Same fictional shipment, described in different language.')
add('Duplicate partial-value entry',a,change(a,amount='625.00'),1,'Second entry repeats half of the same obligation; equal-amount gate misses it.')
add('Identical document different vendor ID',a,change(a,vendor_id='V900'),1,'Duplicate master ID only; business identity unchanged.')
add('Date typo on duplicate',a,change(a,date='2026-01-01'),1,'Same invoice with an incorrect date; requires source verification.')
r=invoice(vendor='Harbor Network Care',vendor_id='V901',number='HNC-SEP',amount='900.00',description='Managed network service',period='2026-09',date='2026-09-30')
add('Recurring monthly charge',r,change(r,number='HNC-OCT',period='2026-10',date='2026-10-30'),0,'Equal recurring prices are separate service periods.')
add('Recurring period missing',r,change(r,number='HNC-OCT',period='',date='2026-10-30'),0,'Separate fictional month, but period evidence is missing in the second record.')
add('Separate delivery same day',a,change(a,number='AST-2026-082'),0,'Two legitimate identical equipment orders on the same day.')
add('Unrelated supplier same amount',a,change(a,vendor='Lakeside Catering',vendor_id='V999',number='LC-456',description='Conference lunch'),0,'Same amount does not establish a common obligation.')
add('Similar legal names different suppliers',a,change(a,vendor='Aster Office Supply East',vendor_id='V777',number='AST-2026-081'),0,'Separate fictional legal entities; name similarity is misleading.')
add('Reused number in later period',r,change(r,period='2026-10',date='2026-10-30'),0,'Synthetic recurring account reference reused legitimately; period distinguishes obligations.')
add('Different invoice amount',a,change(a,number='AST-2026-085',amount='1500.00'),0,'New fictional order with a different total.')
add('Different description and number',a,change(a,number='DEL-940',description='Annual office carpet cleaning'),0,'Unrelated service from the same diversified supplier.')
add('Distant legitimate purchase',a,change(a,number='AST-2026-099',date='2026-12-30'),0,'Similar equipment reordered months later.')
add('Distinct recurring period explicit',r,change(r,number='HNC-NOV',period='2026-11',date='2026-11-30'),0,'Third separate monthly service obligation.')
add('Missing amount',a,change(a,amount=''),None,'No reliable total: abstain and repair the input.','DATA REVIEW')
add('Credit note',a,change(a,number='CN-081',amount='-1250.00',kind='credit_note'),None,'Credit reconciliation is outside duplicate-invoice scoring.','SPECIALIST REVIEW')
add('Currency mismatch',a,change(a,currency='EUR'),None,'No comparison of nominal USD and EUR amounts.','OUT OF SCOPE')
add('Invalid invoice date',a,change(a,date='2026-13-99'),None,'Invalid source value: do not silently infer a date.','DATA REVIEW')
(ROOT/'train.json').write_text(json.dumps(train,indent=2),encoding='utf-8')
(ROOT/'test.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')
print(f'Created {len(train)} training pairs and {len(cases)} evaluation cases.')
