# Генерує сценарії: послідовність (ім'я, шаблон|значення) змінних + шаблон повідомлення.
import yaml, json, datetime as dt
d={a['id']:a for a in yaml.safe_load(open('automations.yaml'))}
tz=dt.timezone(dt.timedelta(hours=2)); now=dt.datetime.now(tz).replace(second=0,microsecond=0)
iso=lambda m:(now+dt.timedelta(minutes=m)).isoformat()
def ev(end_min, nxt_min):
    return {'calendar.x':{'events':[{'start':iso(-20),'end':iso(end_min),'summary':'Відключення'},
        {'start':iso(nxt_min),'end':iso(nxt_min+120),'summary':'Відключення'},
        {'start':iso(nxt_min+200),'end':iso(nxt_min+260),'summary':'Можливе відключення'}]}}
eco=d['ecoflow_outage_start']['actions'][0]['variables']
sched=d['ecoflow_outage_start']['actions'][2]['variables']
planv=[a for a in d['ecoflow_power_restored']['actions'] if 'variables' in a and 'plan' in a['variables']][0]['variables']
def msgs(aid):
    out=[]
    def walk(x):
        if isinstance(x,dict):
            if str(x.get('action','')).startswith('notify.'): out.append(x['data']['message'])
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(d[aid]['actions']); return out
def lit(v): return json.dumps(v,ensure_ascii=False) if not isinstance(v,bool) else str(v).lower()
def scen(name,msg,ov=None,evv=None,extra=None,trig=None):
    seq=[]
    for k,v in eco.items():
        seq.append([k, None if (ov and k in ov) else (v if isinstance(v,str) else str(v)), lit(ov[k]) if (ov and k in ov) else None])
    pre="{% set ev = "+json.dumps(evv,ensure_ascii=False)+" %}" if evv else ""
    if evv or (ov and 'dtek_cal' in ov):
        for k,v in sched.items(): seq.append([k,v,None])
        if msg in (mr, mse):
            for k,v in planv.items(): seq.append([k,v,None])
    for k,v in (extra or {}).items(): seq.append([k,v if isinstance(v,str) else None, None if isinstance(v,str) else lit(v)])
    return {'name':name,'pre':pre+(trig or ''),'seq':seq,'msg':msg}
TV="{% set trigger = {'platform':'numeric_state','entity_id':'sensor.delta_2_max_ac_in_volts'} %}"
ms=msgs('ecoflow_outage_start')[0]; mse=msgs('dtek_schedule_updated_signal')[0]; mon=msgs('ecoflow_outage_monitor'); mr=msgs('ecoflow_power_restored')[0]; me=msgs('dtek_emergency_signal')[0]
cal={'dtek_cal':'calendar.x','dtek_emerg':''}
S=[
 scen('LIVE start, no dtek', ms, {'dtek_cal':'','dtek_emerg':''}, trig=TV),
 scen('start planned, end in 2h', ms, cal, ev(120,400), trig=TV),
 scen('start short (load 600W)', ms, {**cal,'load_w':600.0}, ev(300,600), trig=TV),
 scen('monitor short', mon[0], {**cal,'load_w':900.0}, ev(300,600), extra={'warned':False}),
 scen('monitor recovered', mon[1], {**cal,'load_w':90.0}, ev(300,600), extra={'warned':True}),
 scen('restored', mr, {**cal,'soc':45.0,'in_w':820.0,'out_w':120.0}, ev(-5,300), extra={'off_since':iso(-200)}),
 scen('restored LIVE no dtek', mr, {'dtek_cal':'','dtek_emerg':'','dtek_reason':''}, None, extra={'off_since':''}),
 scen('restored chain short', mr, {**cal,'soc':40.0,'remain_mah':15700.0,'in_w':900.0,'out_w':120.0,'charge_set':800.0,'avg_out_w':400.0}, {'calendar.x':{'events':[
   {'start':iso(120),'end':iso(360),'summary':'Відключення'},{'start':iso(420),'end':iso(660),'summary':'Відключення'}]}}, extra={'off_since':iso(-180)}),
 scen('restored chain ok', mr, {**cal,'soc':90.0,'remain_mah':35300.0,'in_w':300.0,'out_w':120.0,'charge_set':800.0,'avg_out_w':120.0}, {'calendar.x':{'events':[
   {'start':iso(120),'end':iso(360),'summary':'Відключення'},{'start':iso(480),'end':iso(720),'summary':'Відключення'}]}}, extra={'off_since':iso(-180)}),
 scen('restored next not in time', mr, {**cal,'soc':20.0,'remain_mah':7900.0,'in_w':900.0,'out_w':120.0,'charge_set':800.0,'avg_out_w':150.0}, {'calendar.x':{'events':[
   {'start':iso(60),'end':iso(240),'summary':'Відключення'}]}}, extra={'off_since':''}),
 scen('schedule+plan', mse, {**cal,'avg_out_w':300.0}, ev(-5,200), trig="{% set trigger = {'event':{'data':{'group':'3.1','group_name':'3.1','days':{}}}} %}"),
 scen('emergency', me, None, trig="{% set trigger = {'event':{'data':{'reason':'Аварійні ремонтні роботи','start':'"+iso(-5)+"','end':'"+iso(240)+"','start_raw':'x','end_raw':'y'}}} %}"),
]
json.dump(S,open('test/cases.json','w'),ensure_ascii=False); print(len(S))
