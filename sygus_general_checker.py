"""Independent SMT-LIB verification of *external* SyGuS solver results.

Unlike AlgoGenesis' restricted in-house candidate parser, this module accepts
pure SMT-LIB define-fun candidate bodies containing 'let', 'ite', arithmetic,
Boolean guards and helper functions. These are reserialized from balanced
s-expressions; NO source-provided SMT commands are executed except a narrow
allowlist. The source constraints are preserved as original ASTs.

This is a verification-only pathway; it adds no synthesis capability.
Only Z3 UNSAT for the negation of *every original constraint* is a proof.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess
from time import perf_counter_ns

from sygus_clia import Unsupported, parse_sexpressions
from sygus_smt_bridge import SMTCheck

_SYMBOL = re.compile(r'[A-Za-z_][A-Za-z_0-9.\-]*\Z', re.ASCII)
_NUMERIC = re.compile(r'[0-9]+\Z', re.ASCII)
_ALLOWED_OPERATORS = frozenset((
    '+', '-', '*', '<', '<=', '>', '>=', '=', 'and', 'or', 'not', '=>',
    'ite', 'let', 'div', 'mod', 'abs', 'distinct', 'xor',
))
_RESERVED = _ALLOWED_OPERATORS | {'true', 'false', 'Int', 'Bool', 'as'}


def _name(atom):
    if not isinstance(atom,str) or not _SYMBOL.fullmatch(atom) or atom in _RESERVED:
        raise Unsupported('invalid or reserved SMT symbol')
    return atom


def _sort(atom):
    if atom not in ('Int','Bool'):
        raise Unsupported('only Int/Bool functions supported')
    return atom


def _params(value):
    if not isinstance(value,list):
        raise Unsupported('malformed argument signature')
    names=set()
    for item in value:
        if not isinstance(item,list) or len(item)!=2:
            raise Unsupported('malformed argument entry')
        name,sort=item
        _name(name)
        _sort(sort)
        if name in names:raise Unsupported('duplicate argument')
        names.add(name)
    return tuple((p[0],p[1]) for p in value)


def _sexpr(node):
    if isinstance(node,list):
        return '('+' '.join(_sexpr(v) for v in node)+')'
    if not isinstance(node,str):
        raise Unsupported('malformed expression node')
    # Symbols / decimal numerals / accepted SMT operators; zero
    # untrusted commands can escape the parsed s-expression.
    if (node in _ALLOWED_OPERATORS or node in ('Int','Bool','true','false')
            or _NUMERIC.fullmatch(node) or _SYMBOL.fullmatch(node)):
        return node
    raise Unsupported('unsupported SMT token')


def _validate_term(expr, names, *, depth=0):
    """Deny all unknown functions/operators; SMT solver owns type checking."""
    if depth>256:
        raise Unsupported('expression nesting limit exceeded')
    if isinstance(expr,str):
        if (expr in names or expr in ('true','false') or
                _NUMERIC.fullmatch(expr)):
            return
        raise Unsupported('unbound term symbol')
    if not isinstance(expr,list) or not expr or not isinstance(expr[0],str):
        raise Unsupported('malformed term')
    op,*args=expr
    if op=='let':
        if len(args)!=2 or not isinstance(args[0],list) or not args[0]:
            raise Unsupported('invalid let binding')
        local=set(names)
        new=set()
        for item in args[0]:
            if not isinstance(item,list) or len(item)!=2:
                raise Unsupported('malformed let entry')
            name,val=item
            _name(name)
            if name in new or name in local:
                raise Unsupported('duplicate/shadowed let binding')
            # SMT-LIB let bindings are simultaneous; RHS cannot refer to new names.
            _validate_term(val,names,depth=depth+1)
            new.add(name)
        local.update(new)
        _validate_term(args[1],local,depth=depth+1)
    else:
        if op not in _ALLOWED_OPERATORS and op not in names:
            raise Unsupported('unknown function/operator in term: '+op)
        if not args:
            raise Unsupported('missing term operands')
        for a in args:
            _validate_term(a,names,depth=depth+1)


def _parse_def(expr,expected_name=None):
    if (not isinstance(expr,list) or len(expr)!=5 or
            expr[0]!='define-fun'):
        raise Unsupported('expected define-fun')
    _,name,params,result_sort,body=expr
    _name(name)
    _sort(result_sort)
    signature=_params(params)
    if expected_name is not None and name!=expected_name:
        raise Unsupported('candidate function mismatch')
    return name,signature,result_sort,body


def _solution_definitions(solution, expected: dict):
    roots=list(parse_sexpressions(solution))
    if len(roots)==1 and isinstance(roots[0],list) and roots[0] and isinstance(roots[0][0],list):
        roots=roots[0]
    if not roots:
        raise Unsupported('no solution definitions')
    definitions={}
    for root in roots:
        name,params,sort,body=_parse_def(root)
        if name not in expected or name in definitions:
            raise Unsupported('unknown or duplicate synthesized function')
        if (params,sort)!=expected[name]:
            raise Unsupported('synthesized function signature mismatch')
        definitions[name]=root
    if set(definitions)!=set(expected):
        raise Unsupported('missing synthesized function definition')
    return definitions


def build_external_query(source: str, solution: str) -> str:
    """Exact negation of source constraints for the recognized SyGuS-IF subset.

    Restricts top-level source/solution commands, forbids assertions/options,
    reserializes bodies from s-expressions, and has Z3 independently typecheck.
    """
    commands=parse_sexpressions(source)
    helpers=[]
    synth={}
    declared=set()
    constraints=[]
    used=set()
    check_count=0
    found_logic=False
    for command in commands:
        if not isinstance(command,list) or not command:
            raise Unsupported('malformed source command')
        key=command[0]
        if key=='set-logic':
            if found_logic or command!=['set-logic','LIA']:
                raise Unsupported('requires exactly one LIA logic')
            found_logic=True
        elif key=='synth-fun':
            if len(command)!=4 or command[3] not in ('Int','Bool'):
                raise Unsupported('grammar-free Int/Bool synth-fun required')
            name=_name(command[1])
            if name in used:raise Unsupported('duplicate top-level function')
            used.add(name)
            synth[name]=(_params(command[2]),_sort(command[3]))
        elif key=='declare-var':
            if len(command)!=3:
                raise Unsupported('malformed declaration')
            name=_name(command[1]);_sort(command[2])
            if name in declared or name in used:
                raise Unsupported('duplicate declaration')
            declared.add(name)
            helpers.append(['declare-const',name,command[2]])
        elif key=='define-fun':
            name,params,sort,body=_parse_def(command)
            if name in used or name in declared:
                raise Unsupported('duplicate helper function')
            used.add(name)
            helpers.append(command)
        elif key=='constraint':
            if len(command)!=2 or check_count:
                raise Unsupported('invalid source constraint')
            constraints.append(command[1])
        elif key=='check-synth':
            if len(command)!=1 or check_count:
                raise Unsupported('invalid check-synth')
            check_count+=1
        elif key=='set-info':
            # Metadata only; never emit it in the independent query.
            continue
        else:
            raise Unsupported('unsupported SyGuS source command: '+str(key))
    if not found_logic or not synth or not constraints or check_count!=1:
        raise Unsupported('missing logic/synthesis/constraint/check-synth')
    defs=_solution_definitions(solution,synth)
    # Validate ASTs; the solver independently enforces correct types/sorts.
    function_names=set(synth)|used
    for h in helpers:
        if h[0]=='define-fun':
            _,params,_,body=_parse_def(h)
            local={name for name,sort in params}
            _validate_term(body,function_names|declared|local)
    for name,defn in defs.items():
        _,params,_,body=_parse_def(defn)
        local={param for param,_ in params}
        _validate_term(body,function_names|declared|local)
    for c in constraints:
        _validate_term(c,function_names|declared)
    lines=['(set-logic QF_LIA)']
    # Safe wrapper: all source helper functions occur as command-level
    # define-fun, candidate definitions occur as define-fun; original
    # constraints are only emitted under one negated assertion.
    lines.extend(_sexpr(h) for h in helpers)
    lines.extend(_sexpr(defs[name]) for name in synth)
    conjs=constraints[0] if len(constraints)==1 else ['and',*constraints]
    lines.extend(['(assert (not '+_sexpr(conjs)+'))','(check-sat)','(exit)'])
    return '\n'.join(lines)+'\n'


def check_external_solution(source: str, solution: str,
                            *,timeout_seconds: float=15.0) -> SMTCheck:
    if (type(timeout_seconds) not in (int,float) or not
            0<timeout_seconds<=3600):
        raise ValueError('invalid solver timeout')
    query=build_external_query(source,solution)
    if not shutil.which('z3'):
        return SMTCheck('unavailable','z3',0,'external Z3 executable missing')
    start=perf_counter_ns()
    try:
        p=subprocess.run(['z3','-in','-smt2'],input=query,text=True,
                         capture_output=True,timeout=timeout_seconds,check=False)
    except subprocess.TimeoutExpired:
        return SMTCheck('timeout','z3',perf_counter_ns()-start,'external timeout')
    except OSError as exc:
        return SMTCheck('error','z3',perf_counter_ns()-start,str(type(exc).__name__))
    elapsed=perf_counter_ns()-start
    output=p.stdout.strip().splitlines()
    if p.returncode != 0 or len(output)!=1:
        return SMTCheck('error','z3',elapsed,
                        'SMT parser/type error or malformed solver output: '+
                        (p.stderr or p.stdout)[:160])
    if output[0].strip()=='unsat':
        return SMTCheck('proved','z3',elapsed,
                        'original SyGuS source constraints externally verified')
    if output[0].strip()=='sat':
        return SMTCheck('counterexample','z3',elapsed,
                        'candidate violates an original constraint')
    if output[0].strip()=='unknown':
        return SMTCheck('unknown','z3',elapsed,'solver returned unknown')
    return SMTCheck('error','z3',elapsed,'unrecognized SMT output')
