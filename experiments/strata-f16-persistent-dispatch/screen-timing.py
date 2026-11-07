import os,json,pathlib,subprocess,time,re,hashlib
import argparse
ap=argparse.ArgumentParser(description="Rejected persistent-dispatch experiment; runs isolated GPU tests.")
ap.add_argument('--build-dir',type=pathlib.Path,required=True)
ap.add_argument('--sdk',type=pathlib.Path,required=True)
ap.add_argument('--output',type=pathlib.Path,required=True)
a=ap.parse_args()
root=a.output.resolve();root.mkdir(parents=True,exist_ok=True)
sdk=a.sdk.resolve()
base={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
base.update(ROCM_PATH=str(sdk),HIP_PATH=str(sdk),HIP_PLATFORM='amd',
            LD_LIBRARY_PATH=f'{sdk}/lib:{sdk}/lib/rocm_sysdeps/lib:{sdk}/lib/llvm/lib',STRATA_PF_F16='1')
binary=a.build_dir.resolve()/'hip_prefill_fused_iq'
base['S20_NOMMQ']='1'
report={'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'runs':[]}
expected=None
# A screen, bracketed by original and default-off controls; no concurrent GPU work.
for index,factor in enumerate(['control',0,1,2,4,8,16,0,'control']):
 label=f'screen-{index}-p{factor}-q4q5-16k';log=root/(label+'.log');assert not log.exists(),log
 env=base|{'STRATA_PF_F16_KQ_PERSIST':str(0 if factor=='control' else factor)}
 exe=str(binary)+('.control' if factor=='control' else '')
 cmd=[exe,'--no-ref','--only=Q4_K / Q5_1','--chunks=16384']
 started=time.monotonic()
 with log.open('w') as f:p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120)
 txt=log.read_text();hashes=re.findall(r'fused output bits hash ([0-9a-f]+)',txt)
 assert p.returncode==0 and len(hashes)==1,(label,p.returncode,txt[-3000:])
 if expected is None:expected=hashes
 assert hashes==expected,(label,hashes,expected)
 timing=re.search(r'fused back to back: median ([\d.]+) ms, min ([\d.]+); alternating min ([\d.]+)',txt)
 assert timing,(label,txt[-3000:])
 result={'label':label,'factor':factor,'seconds':round(time.monotonic()-started,3),'exit':p.returncode,'hashes':hashes,'median_ms':float(timing[1]),'min_ms':float(timing[2]),'alternate_min_ms':float(timing[3]),'argv':cmd,'env':{k:v for k,v in env.items() if k.startswith('STRATA_') or k=='S20_NOMMQ'}}
 report['runs'].append(result);(root/'screen-results.json').write_text(json.dumps(report,indent=2)+'\n');print(label,result['median_ms'],'ms',flush=True)
print('Screen complete: hashes identical.',flush=True)
