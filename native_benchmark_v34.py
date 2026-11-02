"""v3.4 measured native-code performance versus independent strong references.

Generates candidate C from a v3.3 typed AST, verifies outputs, and builds
the candidate plus two C baselines in the same GCC -O3 translation unit.
Per-cell repeated timings and losses are preserved; NOT SOTA evidence.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import platform
import shutil
import statistics
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path
from native_codegen_v34 import compile_genome, decode_genome

TASKS=('count_max','count_min','sum_max','sum_min')
NATIVE_LENGTHS=(16,128,1024)
NATIVE_DISTRIBUTIONS=('uniform','duplicates','all_equal','increasing','decreasing','alternating')
ALL_CELLS=frozenset((n,d) for n in NATIVE_LENGTHS for d in NATIVE_DISTRIBUTIONS)

REFERENCE=r'''
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
AG_NOINLINE int64_t ag_ref_better(const int64_t *data, size_t n, int64_t key) {
    (void)key;
    if (!n) return 0;
    int64_t best=data[0], acc=TASK_SUM ? best : 1;
    for(size_t i=1;i<n;i++) {
        int64_t x=data[i];
        if(TASK_MAX ? x>best : x<best) {
            best=x; acc=TASK_SUM ? x : 1;
        } else if(x==best) acc+=TASK_SUM ? x : 1;
    }
    return acc;
}
AG_NOINLINE int64_t ag_ref_equal(const int64_t *data, size_t n, int64_t key) {
    (void)key;
    if(!n) return 0;
    int64_t best=data[0], acc=TASK_SUM ? best : 1;
    for(size_t i=1;i<n;i++) {
        int64_t x=data[i];
        if(x==best) acc+=TASK_SUM ? x : 1;
        else if(TASK_MAX ? x>best : x<best) {
            best=x; acc=TASK_SUM ? x : 1;
        }
    }
    return acc;
}
AG_NOINLINE int64_t ag_ref_two_pass(const int64_t *data, size_t n, int64_t key) {
    (void)key;
    if(!n) return 0;
    int64_t best=data[0];
    for(size_t i=1;i<n;i++) if(TASK_MAX ? data[i]>best : data[i]<best) best=data[i];
    int64_t answer=0;
    for(size_t i=0;i<n;i++) if(data[i]==best) answer+=TASK_SUM ? data[i] : 1;
    return answer;
}
'''

HARNESS=r'''
typedef int64_t (*ag_fn_t)(const int64_t*, size_t, int64_t);
static ag_fn_t volatile ag_functions[3];
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
static uint64_t sample(ag_fn_t f, const int64_t *values, size_t n, size_t iters) {
    uint64_t sum=0, start=now_ns();
    for(size_t k=0;k<iters;k++) sum+=(uint64_t)f(values,n,(int64_t)k);
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
    for(unsigned dist=0;dist<6;dist++) for(size_t j=0;j<12;j++) {
        size_t n=sizes[j];
        fill(v,n,dist);
        int64_t expected=ag_ref_two_pass(v,n,3);
        for(unsigned k=0;k<3;k++) {
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
        for(unsigned k=0;k<3;k++) if(ag_functions[k](v,n,0)!=expected) abort();
    }
}
int main(int argc,char **argv) {
    static int64_t values[4096];
    ag_functions[0]=ag_generated;
    ag_functions[1]=ag_ref_better;
    ag_functions[2]=ag_ref_equal;
    verify_all(values);
    if(argc>1 && strcmp(argv[1],"--verify-only")==0) {
        puts("NATIVE_VERIFICATION_PASS"); return 0;
    }
    unsigned reps=5;
    size_t elements_per_sample=500000;
    if(argc>1) {
        long a=strtol(argv[1],NULL,10);
        if(a<1 || a>100) return 2;
        reps=(unsigned)a;
    }
    if(argc>2) {
        long a=strtol(argv[2],NULL,10);
        if(a<10000 || a>20000000) return 2;
        elements_per_sample=(size_t)a;
    }
    unsigned mask=(1u<<18)-1u;
    if(argc>3) {
        char *end=NULL;
        unsigned long parsed=strtoul(argv[3],&end,10);
        if(!argv[3][0] || *end || parsed==0 || parsed>=(1ul<<18)) return 2;
        mask=(unsigned)parsed;
    }
    if(argc>4) {
        char *end=NULL;
        unsigned long long parsed=strtoull(argv[4],&end,10);
        if(!argv[4][0] || *end || parsed==0) return 2;
        ag_rng=(uint64_t)parsed;
    }
    static const char *names[]={"uniform","duplicates","all_equal","increasing","decreasing","alternating"};
    static const size_t sizes[]={16,128,1024};
    puts("distribution,length,repeat,generated_ns,better_first_ns,equal_first_ns");
    for(size_t j=0;j<3;j++) for(unsigned dist=0;dist<6;dist++) {
        if(!(mask & (1u << (j*6+dist)))) continue;
        size_t n=sizes[j];
        fill(values,n,dist);
        size_t iters=elements_per_sample/n;
        if(iters<100) iters=100;
        int64_t expected=ag_ref_two_pass(values,n,0);
        for(unsigned k=0;k<3;k++) {
            if(ag_functions[k](values,n,0)!=expected) abort();
            sample(ag_functions[k],values,n,256);
        }
        for(unsigned rep=0;rep<reps;rep++) {
            uint64_t timings[3]={0,0,0};
            for(unsigned k=0;k<3;k++) {
                unsigned idx=(k+rep+dist+(unsigned)j)%3;
                timings[idx]=sample(ag_functions[idx],values,n,iters);
            }
            printf("%s,%zu,%u,%.6f,%.6f,%.6f\n",names[dist],n,rep,
                   (double)timings[0]/iters,(double)timings[1]/iters,
                   (double)timings[2]/iters);
        }
    }
    if(ag_sink==UINT64_C(0x9badda12345)) fprintf(stderr,"checksum edge\n");
    return 0;
}
'''


def native_source(genome,task):
    if task not in TASKS:raise ValueError('unsupported native task')
    return (compile_genome(genome) +
            '\n#define TASK_MAX '+str(int(task.endswith('max')))+
            '\n#define TASK_SUM '+str(int(task.startswith('sum')))+'\n'+
            REFERENCE+HARNESS)


def _run(command, *, timeout=120):
    proc=subprocess.run(command,capture_output=True,text=True,timeout=timeout,check=False)
    if proc.returncode:
        raise RuntimeError('native command failed %s: %s' % (
            ' '.join(map(str,command)),proc.stderr[-2500:]))
    return proc.stdout


def run_benchmark(task='count_max',*,genome_json=None,compiler='gcc',
                  repetitions=5,elements_per_sample=500000,output_dir=None,
                  cells=None,data_seed=None):
    if (task not in TASKS or type(repetitions) is not int or
            not 1<=repetitions<=100 or type(elements_per_sample) is not int or
            not 10000<=elements_per_sample<=20000000):
        raise ValueError('invalid native benchmark arguments')
    if cells is None:
        cells=ALL_CELLS
    if not isinstance(cells,(set,frozenset)) or not cells or not cells<=ALL_CELLS:
        raise ValueError('invalid native cell partition')
    if data_seed is not None and (type(data_seed) is not int or not 0<data_seed<1<<64):
        raise ValueError('invalid native data seed')
    requested_cells=frozenset(cells)
    cell_mask=sum(1<<(j*6+k) for j,n in enumerate(NATIVE_LENGTHS)
                  for k,d in enumerate(NATIVE_DISTRIBUTIONS) if (n,d) in requested_cells)
    if not shutil.which(compiler):
        raise RuntimeError('C compiler not found: '+compiler)
    if genome_json is None:
        from genome_headtail_v33 import discover_headtail
        genome=discover_headtail(task).genome
        origin='v3.3 generated AST'
    else:
        artifact=json.loads(Path(genome_json).read_text(encoding='utf-8'))
        if artifact.get('task')!=task:
            raise ValueError('input genome artifact task mismatch')
        genome=decode_genome(artifact['candidate'])
        origin='v3.3 preserved CI JSON AST'
    source=native_source(genome,task)
    flags=['-std=c11','-O3','-fno-lto','-Wall','-Wextra','-Werror',
           '-D_POSIX_C_SOURCE=200809L']
    version=_run([compiler,'--version']).splitlines()[0]
    with tempfile.TemporaryDirectory(prefix='algogenesis-v34-') as tmp:
        path=Path(tmp)/'generated.c'
        path.write_text(source,encoding='utf-8')
        executable=Path(tmp)/'bench'
        _run([compiler,*flags,str(path),'-o',str(executable)])
        if 'NATIVE_VERIFICATION_PASS' not in _run([str(executable),'--verify-only']):
            raise AssertionError('native correctness gate missing')
        sanitized=Path(tmp)/'sanitized'
        _run([compiler,*flags,'-O1','-fsanitize=undefined',
              '-fno-sanitize-recover=all',str(path),'-o',str(sanitized)])
        if 'NATIVE_VERIFICATION_PASS' not in _run([str(sanitized),'--verify-only']):
            raise AssertionError('undefined behavior sanitizer gate failed')
        command=[str(executable),str(repetitions),str(elements_per_sample),str(cell_mask)]
        if data_seed is not None:
            command.append(str(data_seed))
        raw=_run(command)
    rows=list(csv.DictReader(io.StringIO(raw)))
    if len(rows)!=len(requested_cells)*repetitions:
        raise AssertionError('missing raw native samples')
    cells=[]
    for n in NATIVE_LENGTHS:
        for dist in NATIVE_DISTRIBUTIONS:
            if (n,dist) not in requested_cells:
                continue
            samples=[r for r in rows if r['distribution']==dist and int(r['length'])==n]
            values={key:statistics.median(float(r[key]) for r in samples)
                    for key in ('generated_ns','better_first_ns','equal_first_ns')}
            stronger=min(values['better_first_ns'],values['equal_first_ns'])
            if stronger<=0:raise AssertionError('invalid native measurement')
            cells.append({'length':n,'distribution':dist,
                          'median_ns_per_call':values,'strong_reference_ns':stronger,
                          'ratio_to_strong':values['generated_ns']/stronger,
                          'samples':samples})
    ratios=[c['ratio_to_strong'] for c in cells]
    report={'task':task,'status':'native_validated','compiler':version,
            'compiler_flags':flags,'platform':platform.platform(),
            'machine':platform.machine(),'cpu':platform.processor(),
            'source_sha256':sha256(source.encode()).hexdigest(),
            'program_origin':origin,'ubsan':'passed',
            'repetitions':repetitions,'elements_per_sample':elements_per_sample,
            'cell_mask':cell_mask,'requested_cells':[list(c) for c in sorted(requested_cells)],
            'data_seed':data_seed,
            'raw_samples':len(rows),'cells':cells,
            'summary':{'median_ratio_to_strong':statistics.median(ratios),
                       'cells_faster_than_strong':sum(r<1 for r in ratios),
                       'cells_slower_than_strong':sum(r>1 for r in ratios),
                       'cells_total':len(ratios)},
            'native_baselines':['better-first','equal-first','two-pass verification oracle'],
            'global_sota_claim':False,'novel_algorithm_claim':False,
            'limitations':['repeated warm same-array microbenchmark',
                'the caller controls cell isolation and seed provenance',
                'limited 4-task family and compiler machine',
                'no native global optimum or hardware-speed proof']}
    if output_dir is not None:
        path=Path(output_dir);path.mkdir(parents=True,exist_ok=True)
        (path/('v34_'+task+'.c')).write_text(source,encoding='utf-8')
        (path/('v34_'+task+'.csv')).write_text(raw,encoding='utf-8')
        (path/('v34_'+task+'.json')).write_text(
            json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description='Native verification and comparison of generated AlgoGenesis genomes')
    p.add_argument('--task',choices=TASKS,default='count_max')
    p.add_argument('--genome-json')
    p.add_argument('--compiler',default='gcc')
    p.add_argument('--repetitions',type=int,default=5)
    p.add_argument('--elements-per-sample',type=int,default=500000)
    p.add_argument('--output-dir',default='native_v34_evidence')
    a=p.parse_args()
    report=run_benchmark(a.task,genome_json=a.genome_json,compiler=a.compiler,
                         repetitions=a.repetitions,
                         elements_per_sample=a.elements_per_sample,
                         output_dir=a.output_dir)
    print(json.dumps({'task':report['task'],'status':report['status'],
                      'summary':report['summary'],'compiler':report['compiler'],
                      'ubsan':report['ubsan']},sort_keys=True))


if __name__=='__main__':
    main()
