"""v4.0: synthesize typed streaming algorithms from an external task spec.

No task name selects a solution or grammar. A finite, task-neutral DSL
enumerates executable loop programs, checks labeled examples, refines with
counterexamples, and emits the winning AST plus standalone C source.
Finite evidence is never a universal correctness or novelty claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path
from typing import Callable

from algorithm_genome_v30 import (Expr, Genome, Machine, Stmt, atom, integer,
                                  op, to_dict, type_check, InvalidGenome,
                                  FuelExhausted)
from native_codegen_v34 import compile_genome


NAME=re.compile(r'^[a-z][a-z0-9_]{0,47}$')
MIN64=-(1<<63)
MAX64=(1<<63)-1
PROTOCOL='spec-driven-streaming-v40-1'


@dataclass(frozen=True)
class Case:
    values:tuple[int,...]
    key:int
    expected:int

    @classmethod
    def parse(cls,raw):
        if not isinstance(raw,dict) or set(raw)!={'values','key','expected'}:
            raise ValueError('invalid labeled case shape')
        values=raw['values']
        if (not isinstance(values,list) or len(values)>128 or
                any(type(x) is not int or not MIN64<=x<=MAX64 for x in values)):
            raise ValueError('case values require up to 128 signed int64 integers')
        if any(type(raw[k]) is not int or not MIN64<=raw[k]<=MAX64
               for k in ('key','expected')):
            raise ValueError('case key/result outside signed int64')
        return cls(tuple(values),raw['key'],raw['expected'])


@dataclass(frozen=True)
class TaskSpec:
    name:str
    training:tuple[Case,...]
    validation:tuple[Case,...]
    challenge:tuple[Case,...]
    holdout:tuple[Case,...]

    @classmethod
    def parse(cls,raw):
        if not isinstance(raw,dict) or set(raw)!={'name','training','validation','challenge','holdout'}:
            raise ValueError('invalid task specification shape')
        if not isinstance(raw['name'],str) or not NAME.fullmatch(raw['name']):
            raise ValueError('invalid task name')
        parts=[]
        seen={}
        for label in ('training','validation','challenge','holdout'):
            values=raw[label]
            if not isinstance(values,list) or len(values)>1000 or (label!='challenge' and not values):
                raise ValueError('missing or oversized task partition: '+label)
            cases=tuple(Case.parse(v) for v in values)
            for case in cases:
                identity=(case.values,case.key)
                if identity in seen:
                    raise ValueError('duplicate input across task partitions')
                seen[identity]=case.expected
            parts.append(cases)
        return cls(raw['name'],*parts)


@dataclass(frozen=True)
class OracleDomain:
    alphabet:tuple[int,...]=(-2,0,2)
    keys:tuple[int,...]=(0,2)
    max_length:int=3

    def cases(self,oracle:Callable[[tuple[int,...],int],int]):
        if (type(self.max_length) is not int or not 0<=self.max_length<=5 or
                not self.alphabet or not self.keys or
                len(self.alphabet)>5 or len(self.keys)>5 or
                any(type(x) is not int or not MIN64<=x<=MAX64
                    for x in (*self.alphabet,*self.keys))):
            raise ValueError('invalid bounded oracle domain')
        for n in range(self.max_length+1):
            for values in product(self.alphabet,repeat=n):
                for key in self.keys:
                    expected=oracle(values,key)
                    if type(expected) is not int or not MIN64<=expected<=MAX64:
                        raise ValueError('oracle result outside signed int64')
                    yield Case(values,key,expected)


def _guards():
    item,key,acc,index=atom('item'),atom('key'),atom('acc'),atom('index')
    zero=integer(0)
    even=op('eq',op('band',index,integer(1)),zero)
    odd=op('eq',op('band',index,integer(1)),integer(1))
    basic=(op('eq',item,key),op('lt',item,key),op('lt',key,item),
           op('lt',item,zero),op('lt',zero,item),op('eq',item,zero),
           op('lt',acc,item),op('lt',item,acc),op('eq',item,acc),even,odd)
    combined=[]
    # Compositions of independent input/index predicates. This is generic
    # Boolean closure, not a special case for the demonstration task.
    for left,right in product(basic[:6],(even,odd)):
        combined.extend((op('and',left,right),op('or',left,right)))
    return tuple(dict.fromkeys((*basic,*combined)))


def candidates():
    """Enumerate task-independent typed loop and update structures."""
    acc,item,key=atom('acc'),atom('item'),atom('key')
    zero,one,negative=integer(0),integer(1),integer(-1)
    deltas=(one,negative,item,op('sub',zero,item),key)
    updates=[op('add',acc,x) for x in deltas]
    updates.extend((item,key,zero,one,acc))
    for guard in _guards():
        for delta in deltas:
            updates.append(op('add',acc,op('select',guard,delta,zero)))
            updates.append(op('select',guard,op('add',acc,delta),acc))
            updates.append(op('select',guard,delta,acc))
        for a,b in ((item,op('sub',zero,item)),(one,negative)):
            updates.append(op('add',acc,op('select',guard,a,b)))
    updates=tuple(dict.fromkeys(updates))
    for initial in (zero,one,negative,'first'):
        registers=(('acc','int',zero if initial=='first' else initial),)
        prefix=(Stmt('if',cond=op('lt',zero,atom('length')),
                     then=(Stmt('set',name='acc',expr=Expr('read',(zero,))),)),) if initial=='first' else ()
        start=1 if initial=='first' else 0
        for reverse in (False,True):
            for update in updates:
                body=(Stmt('set',name='acc',expr=update),)
                yield Genome(registers,prefix+(Stmt('foreach',start=start,
                    reverse=reverse,then=body),),acc,'int')


def _match(vm,genome,cases):
    for case in cases:
        output=vm.run(genome,case.values,case.key)
        if output.value!=case.expected or output.final_array!=case.values:
            return False
    return True


def _score(vm,genome,cases):
    outputs=[vm.run(genome,c.values,c.key) for c in cases]
    return (genome.nodes(),sum(o.comparisons for o in outputs),
            sum(o.steps for o in outputs),repr(to_dict(genome)))


def _int_literal(value):
    if value==MIN64:
        return '(-INT64_C(9223372036854775807)-INT64_C(1))'
    return 'INT64_C('+str(value)+')'


def verify_native(source, cases, *, compiler='gcc'):
    """Compile and execute the generated C on all supplied labeled inputs."""
    if not isinstance(compiler,str) or not shutil.which(compiler):
        raise RuntimeError('native compiler unavailable: '+str(compiler))
    if not cases:
        raise ValueError('native verification needs labeled cases')
    lines=['\n#include <stdio.h>','int main(void) {']
    for i,case in enumerate(cases):
        initializer=','.join(_int_literal(v) for v in case.values) or 'INT64_C(0)'
        lines.append(f'    static const int64_t v_{i}[] = {{{initializer}}};')
        lines.append(f'    if (ag_generated(v_{i}, {len(case.values)}, '
                     f'{_int_literal(case.key)}) != {_int_literal(case.expected)}) {{')
        lines.append(f'        fprintf(stderr,"native mismatch case {i}\\n"); return 3;')
        lines.append('    }')
    lines.extend(['    puts("NATIVE_SPEC_PASS");','    return 0;','}'])
    full_source=source+'\n'.join(lines)+'\n'
    flags=['-std=c11','-O3','-Wall','-Wextra','-Werror',
           '-D_POSIX_C_SOURCE=200809L']
    with tempfile.TemporaryDirectory(prefix='ag-v40-') as tmp:
        path=Path(tmp)/'generated.c'
        path.write_text(full_source,encoding='utf-8')
        for suffix,extra in (('optimized',()),
                             ('ubsan',('-O1','-fsanitize=undefined',
                                       '-fno-sanitize-recover=all'))):
            binary=Path(tmp)/suffix
            build=subprocess.run([compiler,*flags,*extra,str(path),'-o',str(binary)],
                                 capture_output=True,text=True,timeout=120)
            if build.returncode:
                raise RuntimeError('generated C compilation failed: '+build.stderr[-2000:])
            run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=120)
            if run.returncode or 'NATIVE_SPEC_PASS' not in run.stdout:
                raise RuntimeError('generated C '+suffix+' verification failed: '+run.stderr[-2000:])
    return {'compiler':compiler,'optimized':'passed','ubsan':'passed',
            'cases':len(cases)}


def synthesize(spec:TaskSpec, *, oracle=None, oracle_domain=OracleDomain(),
               max_candidates=30000, output_dir=None,native_compiler=None):
    if not isinstance(spec,TaskSpec) or not NAME.fullmatch(spec.name):
        raise ValueError('invalid task spec')
    if type(max_candidates) is not int or not 1<=max_candidates<=100000:
        raise ValueError('invalid candidate budget')
    vm=Machine()
    proposals=0
    passing=[]
    for genome in candidates():
        if proposals>=max_candidates:
            break
        proposals+=1
        try:
            type_check(genome)
            if _match(vm,genome,spec.training[:min(4,len(spec.training))]) and \
               _match(vm,genome,spec.training) and _match(vm,genome,spec.validation):
                passing.append(genome)
        except (InvalidGenome,FuelExhausted,IndexError,OverflowError):
            continue
    if not passing:
        raise RuntimeError('no program meets the finite training and validation spec')
    ranked=sorted(passing,key=lambda g:_score(vm,g,spec.validation))
    extra=list(spec.challenge)
    if oracle is not None:
        # The frozen holdout cannot become a counterexample source, even
        # when a caller chooses an oracle domain that overlaps its inputs.
        reserved={(c.values,c.key) for c in spec.holdout}
        extra.extend(c for c in oracle_domain.cases(oracle)
                     if (c.values,c.key) not in reserved)
    # Counterexample-guided rejection: each failure is retained and used
    # to eliminate other candidates before another one is proposed.
    counterexamples=[]
    remaining=ranked
    while remaining:
        winner=remaining[0]
        failure=None
        try:
            for case in extra:
                if not _match(vm,winner,(case,)):
                    failure=case
                    break
        except (InvalidGenome,FuelExhausted,IndexError,OverflowError):
            failure=case
        if failure is None:
            break
        counterexamples.append(failure)
        filtered=[]
        for genome in remaining[1:]:
            try:
                if _match(vm,genome,(failure,)):
                    filtered.append(genome)
            except (InvalidGenome,FuelExhausted,IndexError,OverflowError):
                pass
        remaining=filtered
    if not remaining:
        raise RuntimeError('all candidate algorithms falsified by challenge/oracle cases')
    winner=remaining[0]
    if not _match(vm,winner,spec.holdout):
        raise RuntimeError('frozen generated program failed held-out cases')
    source=compile_genome(winner)
    native=None
    if native_compiler is not None:
        native=verify_native(source,(*spec.training,*spec.validation,*extra,*spec.holdout),
                             compiler=native_compiler)
    report={'protocol':PROTOCOL,'task':spec.name,
            'status':'finite_spec_synthesis_complete',
            'grammar_proposals':proposals,
            'training_validation_survivors':len(passing),
            'counterexamples_added':len(counterexamples),
            'counterexamples':[{'values':list(c.values),'key':c.key,'expected':c.expected}
                               for c in counterexamples],
            'challenge_cases':len(extra),'holdout_cases':len(spec.holdout),
            'genome':to_dict(winner),
            'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'native_verification':native,
            'finite_correctness_only':True,
            'global_novelty_claim':False,'global_sota_claim':False,
            'limitations':['bounded streaming fold grammar and signed-int64 domain',
                           'examples and bounded oracle challenges cannot prove universal correctness',
                           'source generation does not establish performance or literature novelty']}
    if output_dir is not None:
        root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
        (root/f'v40_{spec.name}.c').write_text(source,encoding='utf-8')
        (root/f'v40_{spec.name}.json').write_text(
            json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',required=True,help='JSON task specification')
    parser.add_argument('--max-candidates',type=int,default=30000)
    parser.add_argument('--native-compiler',default='gcc',
                        help='C compiler; use none to skip native verification')
    parser.add_argument('--output-dir',default='v40_generated')
    args=parser.parse_args()
    spec=TaskSpec.parse(json.loads(Path(args.spec).read_text(encoding='utf-8')))
    report=synthesize(spec,max_candidates=args.max_candidates,output_dir=args.output_dir,
                      native_compiler=None if args.native_compiler=='none' else args.native_compiler)
    print(json.dumps({k:report[k] for k in ('task','status','grammar_proposals',
                                           'training_validation_survivors',
                                           'counterexamples_added','holdout_cases')},sort_keys=True))


if __name__=='__main__':
    main()
