import json,re,collections,argparse
from pathlib import Path
parser=argparse.ArgumentParser(description='Summarize the fixed 64K Qwen3.8 Vulkan operator profile, excluding warmup/decode.')
parser.add_argument('log',type=Path)
parser.add_argument('--response',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--task',type=int,default=5)
a=parser.parse_args();p=a.output;p.mkdir(parents=True,exist_ok=True)
s=a.log.read_text();s=s[s.index(f'task {a.task} | processing task'):]
blocks=[]
for part in s.split('Vulkan Timings:')[1:]:
 end=re.search(r'Total time: ([\deE.+-]+) us\.',part)
 if not end:continue
 rows=[]
 for line in part[:end.start()].splitlines():
  m=re.match(r'(.+): (\d+) x ([\deE.+-]+) us = ([\deE.+-]+) us',line)
  if m:rows.append({'name':m[1],'count':int(m[2]),'seconds':float(m[4])/1e6})
 assert rows
 total=float(end[1])/1e6;assert abs(sum(x['seconds'] for x in rows)-total)<0.0001
 blocks.append({'seconds':total,'ops':rows})
target=[];draft=[]
for b in blocks:
 fa=[x for x in b['ops'] if x['name'].startswith('FLASH_ATTN_EXT dst(256,24,2048,1)')]
 if fa:
  assert len(fa)==1 and fa[0]['count']==16
  b['context_end']=int(re.search(r' k\(256,(\d+),4,1\)',fa[0]['name'])[1]);target.append(b)
 elif any(x['name']=='MUL_MAT q4_K m=5120 n=2048 k=25600' for x in b['ops']):draft.append(b)
assert len(target)==32 and len(draft)==32,(len(target),len(draft))
assert [b['context_end'] for b in target]==list(range(2048,65537,2048))
def category(n):
 if n.startswith('MUL_MAT ') and not n.startswith('MUL_MAT f32 '):return 'quantized_dense_matmul'
 if n.startswith('MUL_MAT f32 '):return 'f32_matmul'
 if n.startswith('FLASH_ATTN'):return 'attention_compute'
 if n.startswith(('FA_KV_','FA_V_','FA_MASK')):return 'attention_preparation'
 if n.startswith('MM_B_TO_F16'):return 'activation_conversion'
 if n.startswith('GATED_DELTA_NET'):return 'gated_delta_net'
 if n.startswith('CONCAT_SSM_CONV'):return 'fused_convolution'
 return 'other'
def summary(bs):
 byop=collections.Counter();cat=collections.Counter();quants=collections.Counter()
 for b in bs:
  for o in b['ops']:
   byop[o['name']]+=o['seconds'];cat[category(o['name'])]+=o['seconds']
   m=re.match(r'MUL_MAT (\w+) m=',o['name'])
   if m:quants[m[1]]+=o['seconds']
 total=sum(cat.values())
 return {'graphs':len(bs),'gpu_operator_seconds':total,'category_seconds':dict(cat.most_common()),'category_percent':{k:100*v/total for k,v in cat.most_common()},'matmul_by_type_seconds':dict(quants.most_common()),'top_operators':dict(byop.most_common(15))}
r={'scope':'One instrumented cold 64K run; shader timing adds synchronization; not an uninstrumented speed benchmark or proof of hardware saturation. Live model remained resident but idle; diagnostic aborted if live traffic arrived.','target':summary(target),'draft_prefill':summary(draft),'combined_prefill':summary(target+draft),'target_context_bands':[{**{'from':end-16384,'to':end},**summary([b for b in target if end-16384<b['context_end']<=end])} for end in (16384,32768,49152,65536)],'profile_response':json.loads(a.response.read_text())}
r['profile_response'] = {k:v for k,v in r['profile_response'].items() if k in ('timings','wall_seconds','instrumented','live_activity_abort')}
(p/'profile-summary.json').write_text(json.dumps(r,indent=2)+'\n')
(p/'profile-records.json').write_text(json.dumps({'target':target,'draft_prefill':draft},indent=2)+'\n')
print(json.dumps({k:r[k] for k in ['combined_prefill','draft_prefill']},indent=2))
