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
report={'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'runs':[]}
expected={}
for bn in [64,128]:
 for permuted in [False,True]:
  for factor in [0,1,16]:
   for name,only in [('q4','Q4_K'),('q5q8','Q5_K / Q8_0')]:
    label=f'reference-bn{bn}-perm{int(permuted)}-p{factor}-{name}'
    log=root/(label+'.log');assert not log.exists(),log
    env=base|{'STRATA_PF_F16_BN':str(bn),'STRATA_PF_F16_KQ_PERSIST':str(factor)}
    cmd=[str(binary),'--no-timing','--only='+only]+(['--reference-permuted'] if permuted else [])
    started=time.monotonic()
    with log.open('w') as f: p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120)
    txt=log.read_text(); hashes=re.findall(r'reference output bits hash ([0-9a-f]+)',txt)
    assert p.returncode==0 and len(hashes)==(2 if name=='q4' else 1),(label,p.returncode,txt[-3000:])
    key=(bn,permuted,name)
    if factor==0:expected[key]=hashes
    assert hashes==expected[key],(label,hashes,expected[key])
    result={'label':label,'seconds':round(time.monotonic()-started,3),'exit':p.returncode,'hashes':hashes,'env':{k:v for k,v in env.items() if k.startswith('STRATA_')},'argv':cmd}
    report['runs'].append(result);(root/'reference-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(label,'PASS',hashes,flush=True)
print('All reference and output-bit comparisons passed.',flush=True)
