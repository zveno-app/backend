from enum import Enum
import base64
from dataclasses import dataclass
import typing
import random

import flask
import jsons

import PySpice.Probe.WaveForm
from PySpice.Spice.Netlist import Circuit

EPS = 1e-6

class BlockOr(Enum):
    V = 'v'
    H = 'h'

    def other(self):
        if self == BlockOr.V:
            return BlockOr.H
        else:
            return BlockOr.V

@dataclass()
class CircuitState:
    cir: Circuit
    last_name: int
    nodes: dict[tuple[int, int], str]

    def new_name(self):
        self.last_name += 1
        return str(self.last_name)

    def connect(self, u: tuple[int, int], v: tuple[int, int], r: float):
        if u not in self.nodes.keys():
            self.nodes[u] = self.new_name()
        if v not in self.nodes.keys():
            self.nodes[v] = self.new_name()
        
        if r >= 0.0:
            self.cir.R(f"r_{self.new_name()}", self.nodes[u], self.nodes[v], r)

class Block:
    _WS = 10000000
    _WIRE = 100000
    _NEXT_DIV_P = 0.7
    _MAX_CHILDREN = 4
    _TEMP_MUL = 0.6
    _BASE_TEMP = 2.0
    _BASE_R_TEMP = 2.0
    _R_PROB = 1.0

    def __init__(self, orient: BlockOr, complexity: float):
        self.orient = orient
        self.children: list[Block] = []
        self.complexity = complexity

        self.freeRight = False
        self.freeLeft = False
        self.freeUp = False
        self.freeDown = False

        self.leftR = -1.0
        self.rightR = -1.0
        self.upR = -1.0
        self.downR = -1.0

        self.startV = 0.0

        self._cs = CircuitState(Circuit('Test'), 0, {})
        self._answer = None

    def populate(self, prng, temp=_BASE_TEMP):
        while prng.random() < self.complexity * self._NEXT_DIV_P * temp / (len(self.children) + 1) and len(self.children) < self._MAX_CHILDREN:
            newB = Block(self.orient.other(), self.complexity)
            newB2 = Block(self.orient.other(), self.complexity)
            newB.populate(prng, temp * self._TEMP_MUL)
            newB2.populate(prng, temp * self._TEMP_MUL)
            self.children.extend([newB, newB2])

    def placeResistors(self, prng, temp=_BASE_R_TEMP):
        if len(self.children) > 0:
            self.leftR = -1.0
            self.rightR = -1.0
            self.upR = -1.0
            self.downR = -1.0
            if self.orient == BlockOr.V:
                for i in range(len(self.children) - 1):
                    if len(self.children[i+1].children) < len(self.children[i].children):
                        self.children[i].freeRight = True
                    else:
                        self.children[i+1].freeLeft = True
                self.children[0].freeLeft = self.freeLeft
                self.children[-1].freeRight = self.freeRight

                for child in self.children:
                    child.freeUp = self.freeUp
                    child.freeDown = self.freeDown
                    
                    child.placeResistors(prng, temp * self._TEMP_MUL)
            else:
                for i in range(len(self.children) - 1):
                    if len(self.children[i+1].children) < len(self.children[i].children):
                        self.children[i].freeDown = True
                    else:
                        self.children[i+1].freeUp = True
                self.children[0].freeUp = self.freeUp
                self.children[-1].freeDown = self.freeDown

                for child in self.children:
                    child.freeLeft = self.freeLeft
                    child.freeRight = self.freeRight
                    
                    child.placeResistors(prng, temp * self._TEMP_MUL)
        else:
            if self.freeLeft and prng.random() * temp < self._R_PROB:
                self.leftR = 1.0
            if self.freeRight and prng.random() * temp < self._R_PROB:
                self.rightR = 1.0
            if self.freeUp and prng.random() * temp < self._R_PROB:
                self.upR = 1.0
            if self.freeDown and prng.random() * temp < self._R_PROB:
                self.downR = 1.0
    
    @staticmethod
    def default(prng: random.Random, complexity: float, orient: BlockOr = BlockOr.V):
        new = Block(orient, complexity)
        new.populate(prng)
        new.freeDown = True
        new.freeUp = True
        new.freeLeft = True
        new.freeRight = True
        new.placeResistors(prng)
        new.startV = 1.0
        return new


    def to_circuit(self, off_x, off_y, s_x, s_y):
        if self.upR >= 0.0:
            self._cs.connect((off_x, off_y), (off_x + s_x, off_y), self.upR)
        if self.downR >= 0.0:
            self._cs.connect((off_x, off_y + s_y), (off_x + s_x, off_y + s_y), self.downR)
        if self.leftR >= 0.0:
            self._cs.connect((off_x, off_y), (off_x, off_y + s_y), self.leftR)
        if self.rightR >= 0.0:
            self._cs.connect((off_x + s_x, off_y), (off_x + s_x, off_y + s_y), self.rightR)

        if len(self.children) == 0:
            return

        cw = s_x / len(self.children)
        ch = s_y / len(self.children)

        for i in range(len(self.children)):
            self.children[i]._cs = self._cs
            if self.orient == BlockOr.H:
                self.children[i].to_circuit(off_x, off_y + ch * i, s_x, ch)
            else:
                self.children[i].to_circuit(off_x + cw * i, off_y, cw, s_y)
    def solve(self):
        self._cs.nodes[(0, self._WS)] = 'inp'
        self._cs.nodes[(self._WS, 0)] = self._cs.cir.gnd
        self._cs.cir.V('input', 'inp', self._cs.cir.gnd, 1.0)
        self.to_circuit(0, 0, self._WS, self._WS)
        print(self._cs.cir)
        sim = self._cs.cir.simulator(temperature=25, nominal_temperature=25)
        op = typing.cast(PySpice.Probe.WaveForm.OperatingPoint, sim.operating_point())
        self._answer = 1 / abs(op['Vinput'][0])
        print(self._answer)
        return self._answer 

app = flask.Flask(__name__)

db: dict[str, Block] = {}

def answer(dct, status: int):
    result = flask.jsonify(dct)
    result.status = status
    return result

@app.route('/block/<id>/check', methods=['GET'])
def check(id: str):
    user_ans = flask.request.args.get('answer', default=None, type=float)
    if user_ans is None:
        return answer({'error': 'Answer not provided'}, 400)
    if id not in db.keys():
        return answer({'error': 'Circuit not found'}, 404)
    ent = db[id]
    if ent._answer is None:
        ent._answer = 0.0
        ent.solve()
    return answer({'error': None, 'result': abs(ent._answer - user_ans) < EPS}, 200)

@app.route('/block', methods=['POST'])
def create() -> flask.Response:
    prng = random.Random()
    id = (base64.b32encode(prng.randbytes(8))).decode('utf-8')
    db[id] = Block.default(prng, flask.request.args.get('complexity', default=0.5, type=float))
    db[id].solve()
    return answer({'error': None, 'id': id}, 200)

@app.route('/block/<id>', methods=['GET'])
def get(id: str):
    if id in db.keys():
        return answer(jsons.dump(db[id], strip_privates=True), 200)
    else:
        return answer({"error": "Not found"}, 404)


if __name__ == '__main__':
    from os import getenv
    app.run(host=getenv('HOST', '127.0.0.1'), port=int(getenv('PORT', '8080')))
