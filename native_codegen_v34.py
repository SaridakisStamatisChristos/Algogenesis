"""v3.4 conservative C11 code generation for typed read-only algorithm genomes.

Only bounded signed-int64 and overflow-free input domains have an exact
cross-language semantics contract. Reject unsupported operations.
"""
from __future__ import annotations
from dataclasses import fields
import re
from algorithm_genome_v30 import Expr, Stmt, Genome, type_check, InvalidGenome

IDENT=re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
MIN64=-(1<<63)
MAX64=(1<<63)-1


class UnsupportedNativeGenome(ValueError):
    pass


def _shape(raw, cls):
    if not isinstance(raw,dict) or set(raw)!={f.name for f in fields(cls)}:
        raise UnsupportedNativeGenome('invalid serialized AST shape')


def decode_genome(raw:dict)->Genome:
    """Strict JSON decoder: static type check after deserialization."""
    def expr(obj):
        if obj is None:return None
        _shape(obj,Expr)
        if not isinstance(obj['args'],list):
            raise UnsupportedNativeGenome('invalid argument list')
        return Expr(obj['op'],tuple(expr(v) for v in obj['args']),obj['value'])
    def stmt(obj):
        _shape(obj,Stmt)
        if not all(isinstance(obj[k],list) for k in ('then','otherwise')):
            raise UnsupportedNativeGenome('invalid statement block')
        return Stmt(op=obj['op'],name=obj['name'],expr=expr(obj['expr']),
                    cond=expr(obj['cond']),then=tuple(stmt(v) for v in obj['then']),
                    otherwise=tuple(stmt(v) for v in obj['otherwise']),
                    reverse=obj['reverse'],stop_if=expr(obj['stop_if']),
                    other=expr(obj['other']),start=obj['start'])
    _shape(raw,Genome)
    if not isinstance(raw['registers'],list) or not isinstance(raw['statements'],list):
        raise UnsupportedNativeGenome('invalid register/program block')
    regs=[]
    for item in raw['registers']:
        if not isinstance(item,list) or len(item)!=3:
            raise UnsupportedNativeGenome('invalid register record')
        regs.append((item[0],item[1],expr(item[2])))
    genome=Genome(tuple(regs),tuple(stmt(s) for s in raw['statements']),
                  expr(raw['result']),raw['output_type'])
    try:
        type_check(genome)
    except InvalidGenome as exc:
        raise UnsupportedNativeGenome('ill-typed serialized genome') from exc
    return genome


class _Emitter:
    def __init__(self,genome):
        type_check(genome)
        if genome.output_type!='int':
            raise UnsupportedNativeGenome('native compiler supports only int64 output')
        self.g=genome
        self.names={'key':'key','length':'((int64_t)n)'}
        self.loop=0
        self.lines=[]
        for name,kind,_ in genome.registers:
            if kind!='int' or not isinstance(name,str) or len(name)>60 or not IDENT.fullmatch(name):
                raise UnsupportedNativeGenome('invalid native register')
            self.names[name]='reg_'+name

    def add(self,depth,s):
        self.lines.append('    '*depth+s)

    def expr(self,e,names):
        if e.op=='int':
            if type(e.value) is not int or not MIN64<=e.value<=MAX64:
                raise UnsupportedNativeGenome('integer literal exceeds int64')
            if e.value==MIN64:
                return '(-INT64_C(9223372036854775807)-INT64_C(1))'
            return 'INT64_C('+str(e.value)+')'
        if e.op=='bool':
            return '1' if e.value else '0'
        if e.op=='var':
            if e.value not in names:
                raise UnsupportedNativeGenome('unbound variable in native emission')
            return names[e.value]
        args=[self.expr(x,names) for x in e.args]
        if e.op=='read':return 'ag_read(data,n,'+args[0]+')'
        if e.op=='select':return '(('+args[0]+') ? ('+args[1]+') : ('+args[2]+'))'
        if e.op=='not':return '(!'+args[0]+')'
        if e.op=='btoi':return '(('+args[0]+') ? 1 : 0)'
        ops={'add':'+','sub':'-','band':'&','eq':'==','lt':'<','and':'&&','or':'||'}
        if e.op not in ops:raise UnsupportedNativeGenome('unsupported expression')
        return '('+args[0]+' '+ops[e.op]+' '+args[1]+')'

    def statements(self,seq,depth,names):
        for s in seq:
            if s.op=='set':
                valid={n for n,_,_ in self.g.registers}
                if s.name not in valid:
                    raise UnsupportedNativeGenome('assignment to read-only input')
                self.add(depth,names[s.name]+' = '+self.expr(s.expr,names)+';')
            elif s.op=='if':
                self.add(depth,'if ('+self.expr(s.cond,names)+') {')
                self.statements(s.then,depth+1,names)
                if s.otherwise:
                    self.add(depth,'} else {')
                    self.statements(s.otherwise,depth+1,names)
                self.add(depth,'}')
            elif s.op=='foreach':
                if type(s.start) is not int or not 0<=s.start<=10000:
                    raise UnsupportedNativeGenome('invalid loop start')
                self.loop+=1
                serial=str(self.loop)
                it='loop_'+serial
                if s.reverse:
                    self.add(depth,'for (size_t '+it+' = n; '+it+'-- > '+str(s.start)+';) {')
                else:
                    self.add(depth,'for (size_t '+it+' = '+str(s.start)+'; '+it+' < n; ++'+it+') {')
                self.add(depth+1,'const int64_t idx_'+serial+' = (int64_t)'+it+';')
                self.add(depth+1,'(void)idx_'+serial+';')
                self.add(depth+1,'const int64_t item_'+serial+' = data['+it+'];')
                self.add(depth+1,'(void)item_'+serial+';')
                inner={**names,'index':'idx_'+serial,'item':'item_'+serial}
                self.statements(s.then,depth+1,inner)
                if s.stop_if is not None:
                    self.add(depth+1,'if ('+self.expr(s.stop_if,inner)+') break;')
                self.add(depth,'}')
            else:
                raise UnsupportedNativeGenome('store/swap/unknown statements unsupported by read-only compiler')

    def render(self):
        self.add(0,'AG_NOINLINE int64_t ag_generated(const int64_t *data, size_t n, int64_t key) {')
        self.add(1,'if (n > 4096 || (n && data == NULL)) abort();')
        self.add(1,'(void)key;')
        for name,_,init in self.g.registers:
            self.add(1,'int64_t reg_'+name+' = '+self.expr(init,self.names)+';')
        self.statements(self.g.statements,1,self.names)
        self.add(1,'return '+self.expr(self.g.result,self.names)+';')
        self.add(0,'}')
        return '\n'.join(self.lines)


def compile_genome(genome:Genome)->str:
    body=_Emitter(genome).render()
    return """/* Generated from typed AlgoGenesis AST, without manually inserted solution. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#if defined(__GNUC__) || defined(__clang__)
#define AG_NOINLINE __attribute__((noinline))
#else
#define AG_NOINLINE
#endif
static inline int64_t ag_read(const int64_t *data, size_t n, int64_t idx) {
    if (idx < 0 || (uint64_t)idx >= n) abort();
    return data[idx];
}
""" + body + '\n'
