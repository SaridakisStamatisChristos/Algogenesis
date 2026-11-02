"""v3.7: compare a frozen v3.6 genome with scalar and AVX2 C competitors.

Same-translation-unit, same-array timings. The vector reference is included
only on CPUs reporting AVX2 support. This is a local workload comparison,
not a broad SOTA benchmark or a new genome selection pass.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import platform
import shutil
import statistics
import tempfile
from hashlib import sha256
from pathlib import Path

from native_autotune_v35 import EVAL_CELLS
from native_benchmark_v34 import REFERENCE, TASKS, _run
from native_codegen_v34 import compile_genome, decode_genome
from native_blinded_v36 import PROTOCOL as V36_PROTOCOL, _geomean

PROTOCOL='native-competitors-v37-1'
DATA_SEED=0xAE7719320D4CB58F

COMPETITORS=r'''
AG_NOINLINE int64_t ag_ref_branchless(const int64_t *data, size_t n, int64_t key) {
    (void)key;
    if(!n) return 0;
    int64_t best=data[0], acc=TASK_SUM ? best : 1;
    for(size_t i=1;i<n;i++) {
        int64_t x=data[i], unit=TASK_SUM ? x : 1;
        int better=TASK_MAX ? x>best : x<best;
        int equal=x==best;
        int64_t mask=-(int64_t)better;
        acc=(unit&mask)|((acc+(int64_t)equal*unit)&~mask);
        best=(x&mask)|(best&~mask);
    }
    return acc;
}
#if (defined(__x86_64__) || defined(__i386__)) && defined(__GNUC__)
#include <immintrin.h>
static int ag_has_avx2(void) {
    __builtin_cpu_init();
    return !!__builtin_cpu_supports("avx2");
}
__attribute__((target("avx2"),noinline))
int64_t ag_ref_avx2(const int64_t *data, size_t n, int64_t key) {
    (void)key;
    if(!n) return 0;
    __m256i bestv=_mm256_set1_epi64x(data[0]);
    size_t i=0;
    for(;i+4<=n;i+=4) {
        __m256i x=_mm256_loadu_si256((const __m256i*)(data+i));
        __m256i better=TASK_MAX ? _mm256_cmpgt_epi64(x,bestv)
                                  : _mm256_cmpgt_epi64(bestv,x);
        bestv=_mm256_blendv_epi8(bestv,x,better);
    }
    int64_t lanes[4];
    _mm256_storeu_si256((__m256i*)lanes,bestv);
    int64_t best=lanes[0];
    for(unsigned k=1;k<4;k++) if(TASK_MAX ? lanes[k]>best : lanes[k]<best) best=lanes[k];
    for(;i<n;i++) if(TASK_MAX ? data[i]>best : data[i]<best) best=data[i];
    __m256i target=_mm256_set1_epi64x(best);
    __m256i ones=_mm256_set1_epi64x(1);
    __m256i counts=_mm256_setzero_si256();
    i=0;
    for(;i+4<=n;i+=4) {
        __m256i x=_mm256_loadu_si256((const __m256i*)(data+i));
        __m256i equal=_mm256_cmpeq_epi64(x,target);
        counts=_mm256_add_epi64(counts,_mm256_and_si256(equal,ones));
    }
    uint64_t totals[4];
    _mm256_storeu_si256((__m256i*)totals,counts);
    uint64_t count=totals[0]+totals[1]+totals[2]+totals[3];
    for(;i<n;i++) count+=(uint64_t)(data[i]==best);
    return TASK_SUM ? best*(int64_t)count : (int64_t)count;
}
#endif
'''

HARNESS=r'''
typedef int64_t (*ag_fn_t)(const int64_t*, size_t, int64_t);
static ag_fn_t volatile ag_functions[5];
static unsigned ag_count;
static volatile uint64_t ag_sink=0;
static uint64_t ag_rng=UINT64_C(0x5a2026c0ffee1234);
static uint64_t rng(void) {
    uint64_t x=ag_rng;
    x^=x<<13; x^=x>>7; x^=x<<17;
    return ag_rng=x;
}
static uint64_t now_ns(void) {
    struct timespec ts;
    if(clock_gettime(CLOCK_MONOTONIC,&ts)!=0) abort();
    return (uint64_t)ts.tv_sec*UINT64_C(1000000000)+(uint64_t)ts.tv_nsec;
}
static uint64_t sample(ag_fn_t f, const int64_t *v, size_t n, size_t iters) {
    uint64_t sum=0,start=now_ns();
    for(size_t k=0;k<iters;k++) sum+=(uint64_t)f(v,n,(int64_t)k);
    uint64_t elapsed=now_ns()-start;
    ag_sink^=sum;
    return elapsed;
}
static void fill(int64_t *v,size_t n,unsigned dist) {
    for(size_t i=0;i<n;i++) {
        uint64_t r=rng();
        if(dist==0) v[i]=(int64_t)(r%2001)-1000;
        if(dist==1) v[i]=(int64_t)(r%5)-2;
        if(dist==2) v[i]=7;
        if(dist==3) v[i]=(int64_t)i;
        if(dist==4) v[i]=(int64_t)(n-i);
        if(dist==5) v[i]=(i%2) ? 1000 : -1000;
    }
}
static void verify_all(int64_t *v) {
    static const size_t sizes[]={0,1,2,3,7,16,32,127,128,256,1024,4096};
    for(unsigned dist=0;dist<6;dist++) for(unsigned j=0;j<12;j++) {
        size_t n=sizes[j];
        fill(v,n,dist);
        int64_t expected=ag_ref_two_pass(v,n,3);
        for(unsigned k=0;k<ag_count;k++) {
            int64_t got=ag_functions[k](v,n,3);
            if(got!=expected) {
                fprintf(stderr,"native mismatch dist=%u n=%zu function=%u got=%" PRId64 " expected=%" PRId64 "\n",dist,n,k,got,expected);
                exit(3);
            }
        }
    }
    for(unsigned t=0;t<250;t++) {
        size_t n=(size_t)(rng()%129);
        for(size_t i=0;i<n;i++) v[i]=(int64_t)(rng()%2001)-1000;
        int64_t expected=ag_ref_two_pass(v,n,0);
        for(unsigned k=0;k<ag_count;k++) if(ag_functions[k](v,n,0)!=expected) abort();
    }
}
int main(int argc,char **argv) {
    static int64_t values[4096];
    ag_functions[0]=ag_generated;
    ag_functions[1]=ag_ref_better;
    ag_functions[2]=ag_ref_equal;
    ag_functions[3]=ag_ref_branchless;
    ag_count=4;
#if (defined(__x86_64__) || defined(__i386__)) && defined(__GNUC__)
    if(ag_has_avx2()) { ag_functions[4]=ag_ref_avx2; ag_count=5; }
#endif
    verify_all(values);
    if(argc>1 && strcmp(argv[1],"--verify-only")==0) {
        printf("NATIVE_VERIFICATION_PASS avx2=%u\n",(unsigned)(ag_count==5)); return 0;
    }
    if(argc!=4) return 2;
    char *end=NULL;
    long reps=strtol(argv[1],&end,10);
    if(!argv[1][0] || *end || reps<1 || reps>100) return 2;
    long work=strtol(argv[2],&end,10);
    if(!argv[2][0] || *end || work<10000 || work>20000000) return 2;
    unsigned long long seed=strtoull(argv[3],&end,10);
    if(!argv[3][0] || *end || !seed) return 2;
    ag_rng=(uint64_t)seed;
    static const char *names[]={"uniform","duplicates","all_equal","increasing","decreasing","alternating"};
    static const size_t sizes[]={16,128,1024};
    printf("distribution,length,repeat,generated_ns,better_first_ns,equal_first_ns,branchless_ns");
    if(ag_count==5) printf(",avx2_ns");
    putchar('\n');
    for(unsigned j=0;j<3;j++) for(unsigned dist=0;dist<6;dist++) {
        size_t n=sizes[j];
        if(!((j==2) || (dist>=3))) continue; /* v3.6 EVAL_CELLS only */
        fill(values,n,dist);
        size_t iters=(size_t)work/n;
        if(iters<100) iters=100;
        int64_t expected=ag_ref_two_pass(values,n,0);
        for(unsigned k=0;k<ag_count;k++) {
            if(ag_functions[k](values,n,0)!=expected) abort();
            sample(ag_functions[k],values,n,256);
        }
        for(long rep=0;rep<reps;rep++) {
            uint64_t timings[5]={0};
            for(unsigned k=0;k<ag_count;k++) {
                unsigned idx=(k+(unsigned)rep+dist+j)%ag_count;
                timings[idx]=sample(ag_functions[idx],values,n,iters);
            }
            printf("%s,%zu,%ld",names[dist],n,rep);
            for(unsigned k=0;k<ag_count;k++) printf(",%.6f",(double)timings[k]/iters);
            putchar('\n');
        }
    }
    if(ag_sink==UINT64_C(0x9badda12345)) fprintf(stderr,"checksum edge\n");
    return 0;
}
'''


def source_for(genome,task):
    if task not in TASKS:
        raise ValueError('unsupported task')
    return (compile_genome(genome)+
            '\n#define TASK_MAX '+str(int(task.endswith('max')))+
            '\n#define TASK_SUM '+str(int(task.startswith('sum')))+'\n'+
            REFERENCE+COMPETITORS+HARNESS)


def compare(task, v36_result, *, compiler='gcc', repetitions=7,
            elements_per_sample=500000, output_dir=None):
    if task not in TASKS or type(repetitions) is not int or not 2<=repetitions<=100:
        raise ValueError('invalid task or repetitions')
    if type(elements_per_sample) is not int or not 10000<=elements_per_sample<=20000000:
        raise ValueError('invalid work')
    if not shutil.which(compiler):
        raise RuntimeError('compiler unavailable: '+compiler)
    previous=json.loads(Path(v36_result).read_text(encoding='utf-8'))
    if (previous.get('task')!=task or
            previous.get('protocol')!=V36_PROTOCOL or
            previous.get('status')!='blinded_native_experiment_complete' or
            previous.get('selection_measurements_exclude_holdout_cells') is not True):
        raise ValueError('requires completed v3.6 result for the same task')
    records=previous.get('profiled_candidates')
    index=previous.get('selected_index')
    if (not isinstance(records,list) or type(index) is not int or
            not 0<=index<len(records) or records[index].get('index')!=index or
            records[index].get('score') is None or
            records[index].get('genome')!=previous.get('selected_genome')):
        raise ValueError('v3.6 selected genome provenance mismatch')
    genome=decode_genome(previous['selected_genome'])
    source=source_for(genome,task)
    flags=['-std=c11','-O3','-fno-lto','-Wall','-Wextra','-Werror',
           '-D_POSIX_C_SOURCE=200809L']
    version=_run([compiler,'--version']).splitlines()[0]
    with tempfile.TemporaryDirectory(prefix='ag-v37-') as tmp:
        path=Path(tmp)/'benchmark.c'
        executable=Path(tmp)/'benchmark'
        sanitized=Path(tmp)/'sanitized'
        path.write_text(source,encoding='utf-8')
        _run([compiler,*flags,str(path),'-o',str(executable)])
        verification=_run([str(executable),'--verify-only']).strip()
        if not verification.startswith('NATIVE_VERIFICATION_PASS avx2='):
            raise AssertionError('native verification missing')
        _run([compiler,*flags,'-O1','-fsanitize=undefined',
              '-fno-sanitize-recover=all',str(path),'-o',str(sanitized)])
        if not _run([str(sanitized),'--verify-only']).startswith('NATIVE_VERIFICATION_PASS'):
            raise AssertionError('UBSan verification missing')
        raw=_run([str(executable),str(repetitions),str(elements_per_sample),str(DATA_SEED)])
    rows=list(csv.DictReader(io.StringIO(raw)))
    if len(rows)!=len(EVAL_CELLS)*repetitions:
        raise AssertionError('incomplete evaluation cells')
    avx2='avx2_ns' in rows[0]
    if avx2!=(verification.endswith('avx2=1')):
        raise AssertionError('SIMD availability mismatch')
    keys=['generated_ns','better_first_ns','equal_first_ns','branchless_ns']
    if avx2: keys.append('avx2_ns')
    if set(rows[0])!={'distribution','length','repeat',*keys}:
        raise AssertionError('unexpected timing columns')
    cells=[]
    for n,dist in sorted(EVAL_CELLS):
        samples=[r for r in rows if int(r['length'])==n and r['distribution']==dist]
        if len(samples)!=repetitions:
            raise AssertionError('missing timing repetitions')
        medians={key:statistics.median(float(s[key]) for s in samples) for key in keys}
        if not all(x>0 for x in medians.values()):
            raise AssertionError('nonpositive latency')
        stronger=min(medians[k] for k in keys[1:])
        cells.append({'length':n,'distribution':dist,'median_ns_per_call':medians,
                      'strong_reference_ns':stronger,
                      'ratio_to_strong':medians['generated_ns']/stronger,
                      'strongest_reference':min(keys[1:],key=lambda k:medians[k]),
                      'samples':samples})
    ratios=[c['ratio_to_strong'] for c in cells]
    report={'protocol':PROTOCOL,'task':task,'status':'expanded_comparison_complete',
            'source_v36_protocol':previous['protocol'],
            'selected_index':previous['selected_index'],
            'source_sha256':sha256(source.encode()).hexdigest(),
            'compiler':version,'compiler_flags':flags,'platform':platform.platform(),
            'machine':platform.machine(),'cpu':platform.processor(),
            'data_seed':DATA_SEED,'repetitions':repetitions,
            'elements_per_sample':elements_per_sample,
            'native_verification':'passed','ubsan':'passed','avx2_available':avx2,
            'native_baselines':keys[1:], 'raw_samples':len(rows),'cells':cells,
            'summary':{'geometric_ratio_to_strong':_geomean(ratios),
                       'cells_faster':sum(x<1 for x in ratios),
                       'cells_slower':sum(x>1 for x in ratios),
                       'cells_total':len(cells)},
            'global_sota_claim':False,
            'limitations':['frozen v3.6 winner, previously exposed evaluation cell families',
                           'single machine, compiler and warm-cache workload',
                           'AVX2 is optional; no AVX-512/NEON or library comparison',
                           'finite correctness checks, no universal proof']}
    if output_dir is not None:
        destination=Path(output_dir);destination.mkdir(parents=True,exist_ok=True)
        stem=destination/('v37_'+task)
        stem.with_suffix('.c').write_text(source,encoding='utf-8')
        stem.with_suffix('.csv').write_text(raw,encoding='utf-8')
        stem.with_suffix('.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=TASKS,required=True)
    parser.add_argument('--v36-result',required=True)
    parser.add_argument('--compiler',default='gcc')
    parser.add_argument('--repetitions',type=int,default=7)
    parser.add_argument('--elements-per-sample',type=int,default=500000)
    parser.add_argument('--output-dir',default='native_v37_evidence')
    args=parser.parse_args()
    result=compare(args.task,args.v36_result,compiler=args.compiler,
                   repetitions=args.repetitions,
                   elements_per_sample=args.elements_per_sample,
                   output_dir=args.output_dir)
    print(json.dumps({'task':result['task'],'summary':result['summary'],
                      'avx2_available':result['avx2_available']},sort_keys=True))


if __name__=='__main__':
    main()
