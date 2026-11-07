#include <hip/hip_runtime.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <vector>
static void ck(hipError_t e){if(e!=hipSuccess){std::fprintf(stderr,"%s\n",hipGetErrorString(e));std::exit(1);}}
__global__ void copy4(const float4* __restrict__ src,float4* __restrict__ dst,size_t n){
 for(size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;i<n;i+=(size_t)gridDim.x*blockDim.x)dst[i]=src[i];
}
int main(){
 const size_t bytes=16384ull*10240*4, n=bytes/sizeof(float4);
 float4 *a,*b;ck(hipMalloc(&a,bytes));ck(hipMalloc(&b,bytes));
 ck(hipMemset(a,0x3f,bytes));ck(hipMemset(b,0,bytes));
 hipEvent_t start,end;ck(hipEventCreate(&start));ck(hipEventCreate(&end));
 for(unsigned grid:{768u,3072u,12288u,(unsigned)((n+255)/256)}){
  std::vector<float> times;
  for(int i=0;i<25;++i){ck(hipEventRecord(start));copy4<<<grid,256>>>(a,b,n);ck(hipGetLastError());ck(hipEventRecord(end));ck(hipEventSynchronize(end));float ms;ck(hipEventElapsedTime(&ms,start,end));if(i>=5)times.push_back(ms);std::swap(a,b);}
  std::sort(times.begin(),times.end());
  std::printf("vector copy grid=%u bytes-per-buffer=%zu median=%.3f ms min=%.3f ms median-bandwidth=%.1f GB/s (read+write)\n",grid,bytes,times[10],times[0],2.0*bytes/(times[10]*1e6));
 }
 std::vector<unsigned> out(bytes/4);ck(hipMemcpy(out.data(),a,bytes,hipMemcpyDeviceToHost));
 for(unsigned x:out)if(x!=0x3f3f3f3fu){std::fprintf(stderr,"copy validation failed\n");return 1;}
 std::puts("copy validation passed");ck(hipFree(a));ck(hipFree(b));ck(hipEventDestroy(start));ck(hipEventDestroy(end));
}
