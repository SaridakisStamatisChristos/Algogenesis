"""Small, total, typed register-machine DSL with explicit bounded execution.

Registers contain integers; predicates return booleans; statements return a new
register state. Loops have literal nonnegative bounds; fuel limits total steps.
No eval/exec, I/O, external calls, recursion, or unbounded loops.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class IntExpr:
    op: str
    args: tuple['IntExpr', ...] = ()
    atom: str | int | None = None

@dataclass(frozen=True)
class Predicate:
    op: str
    left: IntExpr
    right: IntExpr

@dataclass(frozen=True)
class Statement:
    op: str
    name: str | None = None
    expr: IntExpr | None = None
    condition: Predicate | None = None
    body: tuple['Statement', ...] = ()
    otherwise: tuple['Statement', ...] = ()
    count: int = 0

class FuelExhausted(RuntimeError):
    pass

class Interpreter:
    def __init__(self, fuel=1000):
        if fuel < 1:
            raise ValueError('fuel must be positive')
        self.fuel = fuel

    def _tick(self):
        self.fuel -= 1
        if self.fuel < 0:
            raise FuelExhausted('execution budget exhausted')

    def integer(self, e: IntExpr, state: dict[str,int]) -> int:
        self._tick()
        if e.op == 'literal':
            if type(e.atom) is not int:
                raise TypeError('literal must be an integer')
            return e.atom
        if e.op == 'register':
            if not isinstance(e.atom,str):
                raise TypeError('register name must be a string')
            return state[e.atom]
        if e.op in ('neg','abs') and len(e.args)==1:
            x=self.integer(e.args[0],state)
            return -x if e.op=='neg' else abs(x)
        if e.op in ('add','sub','min','max') and len(e.args)==2:
            a,b=(self.integer(x,state) for x in e.args)
            return {'add':lambda:a+b,'sub':lambda:a-b,'min':lambda:min(a,b),'max':lambda:max(a,b)}[e.op]()
        raise ValueError('invalid integer expression')

    def predicate(self, p: Predicate, state: dict[str,int]) -> bool:
        a,b=self.integer(p.left,state),self.integer(p.right,state)
        if p.op=='lt': return a<b
        if p.op=='le': return a<=b
        if p.op=='eq': return a==b
        raise ValueError('invalid predicate')

    def statements(self, program: tuple[Statement,...], state: dict[str,int]) -> dict[str,int]:
        for s in program:
            self._tick()
            if s.op=='assign':
                if not isinstance(s.name,str) or s.expr is None:
                    raise ValueError('invalid assignment')
                state[s.name]=self.integer(s.expr,state)
            elif s.op=='if':
                if s.condition is None: raise ValueError('missing condition')
                self.statements(s.body if self.predicate(s.condition,state) else s.otherwise,state)
            elif s.op=='repeat':
                count = self.integer(s.expr,state) if s.expr is not None else s.count
                if type(count) is not int or not 0<=count<=10000:
                    raise ValueError('repeat bound must be in [0,10000]')
                for _ in range(count):
                    self.statements(s.body,state)
            else:
                raise ValueError('invalid statement')
        return state

    def run(self, program: tuple[Statement,...], inputs: dict[str,int]) -> dict[str,int]:
        if any(type(v) is not int for v in inputs.values()):
            raise TypeError('inputs must be integers')
        return self.statements(program,dict(inputs))
