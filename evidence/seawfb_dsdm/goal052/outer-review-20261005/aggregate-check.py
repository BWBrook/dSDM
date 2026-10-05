from pathlib import Path
import hashlib,json,math,statistics,sys
p=Path(sys.argv[1]); s=json.loads(p.read_bytes()); a=s['aggregate']
plan=json.loads((p.parent/'plan.json').read_bytes())
rows={(x['region'],x['target']):x for x in s['targets']}
if sorted(a['common73']['targets'])!=sorted(plan['panels']['primary']): raise RuntimeError('common panel drift')
for region,panel in a['regional'].items():
    if sorted(panel['targets'])!=sorted(plan['panels']['regional'][region]): raise RuntimeError('regional panel drift')
for item in s['targets']:
    if item['thresholds']!=plan['thresholds'][item['target']]: raise RuntimeError('frozen threshold drift')
    if item['panel']['regional'] and not item['support']['x10']['passes']: raise RuntimeError('frozen panel support failure')
if len(rows)!=471: raise RuntimeError('target-region inventory incomplete or duplicated')
contrasts={
'ft_random':('multihead_full_finetune_minus_target_only_random_init_resmlp','multihead_full_finetune','target_only_random_init_resmlp'),
'ft_q':('multihead_full_finetune_minus_target_plus_q_linear_resmlp','multihead_full_finetune','target_plus_q_linear_resmlp'),
'ft_conventional':('multihead_full_finetune_minus_goal051_selected_conventional','multihead_full_finetune','selected_conventional'),
'ft_q_conventional':('multihead_full_finetune_minus_goal051_q_augmented_conventional','multihead_full_finetune','selected_conventional_plus_q'),
'frozen_random':('multihead_frozen_trunk_minus_target_only_random_init_resmlp','multihead_frozen_trunk','target_only_random_init_resmlp'),
'ft_frozen':('multihead_full_finetune_minus_multihead_frozen_trunk','multihead_full_finetune','multihead_frozen_trunk'),
'ensemble_ft':('fixed_ensemble_minus_multihead_full_finetune','fixed_ensemble','multihead_full_finetune'),
'ensemble_conventional':('fixed_ensemble_minus_selected_conventional','fixed_ensemble','selected_conventional')}
checks=0
def close(x,y):
    global checks
    checks+=1
    if not math.isclose(x,y,rel_tol=0,abs_tol=1e-12): raise RuntimeError(f'aggregate mismatch {x} vs {y}')
def delta(region,target,left,right,mask='x10'):
    arm=rows[region,target]['metrics'][mask]
    x,y=arm[left]['roc_auc'],arm[right]['roc_auc']
    return None if x is None or y is None else x-y
def verify(values,stored):
    vals=[v for v in values if v is not None]
    if len(vals)!=stored['denominator']: raise RuntimeError('denominator mismatch')
    if not vals:
        if stored['mean'] is not None: raise RuntimeError('empty mean mismatch')
        return
    close(statistics.fmean(vals),stored['mean']); close(statistics.median(vals),stored['median'])
    if sum(v>0 for v in vals)!=stored['positive_count']: raise RuntimeError('positive count mismatch')
for panel_name in ('primary_by_region','regional'):
    for region,panel in a[panel_name].items():
        for _,(name,left,right) in contrasts.items():
            verify([delta(region,t,left,right) for t in panel['targets']],panel['contrasts'][name])
            verify([delta(region,t,left,right,'x20') for t in panel['targets']],a['x20'][panel_name][region]['contrasts'][name])
for _,(name,left,right) in contrasts.items():
    vals=[]
    for target in a['common73']['targets']:
        d=[delta(r,target,left,right) for r in a['common73']['regions']]
        if any(v is None for v in d): raise RuntimeError('primary x10 unexpectedly missing')
        vals.append(statistics.fmean(d))
    verify(vals,a['common73']['contrasts'][name])
    x20_means=[a['x20']['primary_by_region'][r]['contrasts'][name]['mean'] for r in a['common73']['regions']]
    close(statistics.fmean(x20_means),a['x20']['common_equal_region_macro']['contrasts'][name]['mean'])
    inter=[]
    for target in a['common73']['targets']:
        d=[delta(r,target,left,right,'x20') for r in a['common73']['regions']]
        inter.append(None if any(v is None for v in d) else statistics.fmean(d))
    verify(inter,a['x20']['common_three_region_intersection']['contrasts'][name])
summary={'status':'pass','scores_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows_checked':len(rows),'numeric_comparisons':checks,'primary_target_count':a['common73']['target_count'],'common':{},'primary_regions':{},'regional_panels':{},'x20_common_equal_region_macro':{}}
for key,(name,_,_) in contrasts.items():
    summary['common'][key]={k:a['common73']['contrasts'][name][k] for k in ('mean','median','positive_count','denominator')}
    summary['x20_common_equal_region_macro'][key]=a['x20']['common_equal_region_macro']['contrasts'][name]
for section,label in [('primary_by_region','primary_regions'),('regional','regional_panels')]:
    for region,panel in a[section].items():
        summary[label][region]={'targets':panel['target_count'],'contrasts':{key:{k:panel['contrasts'][name][k] for k in ('mean','median','positive_count','denominator')} for key,(name,_,_) in contrasts.items()}}
print(json.dumps(summary,indent=2,sort_keys=True))
