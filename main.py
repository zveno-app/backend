from enum import Enum
import random

import flask
import jsons

from PySpice.Spice.Netlist import Circuit


class BlockOr(Enum):
    V = 'v'
    H = 'h'

    def other(self):
        if self == BlockOr.V:
            return BlockOr.H
        else:
            return BlockOr.V


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

        self.leftR = 0.0
        self.rightR = 0.0
        self.upR = 0.0
        self.downR = 0.0

        self.startV = 0.0

        self._lastnode = 0
        self._nodes = {}
        self._circuit = Circuit('Test')

    def populate(self, prng, temp=_BASE_TEMP):
        while prng.random() < self.complexity * self._NEXT_DIV_P * temp / (len(self.children) + 1) and len(
                self.children) < self._MAX_CHILDREN:
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
                    if len(self.children[i + 1].children) < len(self.children[i].children):
                        self.children[i].freeRight = True
                    else:
                        self.children[i + 1].freeLeft = True
                self.children[0].freeLeft = self.freeLeft
                self.children[-1].freeRight = self.freeRight

                for child in self.children:
                    child.freeUp = self.freeUp
                    child.freeDown = self.freeDown

                    child.placeResistors(prng, temp * self._TEMP_MUL)
            else:
                for i in range(len(self.children) - 1):
                    if len(self.children[i + 1].children) < len(self.children[i].children):
                        self.children[i].freeDown = True
                    else:
                        self.children[i + 1].freeUp = True
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
        return new

    def _new_name(self):
        self._lastnode += 1
        return self._lastnode

    def _connect(self, u, v, r):
        if u not in self._nodes.keys():
            self._nodes[u] = self._new_name()
        if v not in self._nodes.keys():
            self._nodes[v] = self._new_name()

        if r >= 0.0:
            self._circuit.R(f"r_{self._new_name()}", self._nodes[u], self._nodes[v], r)

    def to_circuit(self, off_x, off_y, s_x, s_y):
        if self.upR >= 0.0:
            self._connect((off_x, off_y), (off_x + self._WIRE, off_y), self.upR)
        if self.downR >= 0.0:
            self._connect((off_x, off_y + self._WIRE), (off_x + self._WIRE, off_y + self._WIRE), self.downR)
        if self.leftR >= 0.0:
            self._connect((off_x, off_y), (off_x, off_y + self._WIRE), self.leftR)
        if self.rightR >= 0.0:
            self._connect((off_x + self._WIRE, off_y), (off_x + self._WIRE, off_y + self._WIRE), self.rightR)

        if len(self.children) == 0:
            return

        cw = s_x / len(self.children)
        ch = s_y / len(self.children)

        for i in range(len(self.children)):
            if self.orient == BlockOr.H:
                self.children[i].to_circuit(off_x, off_y + ch * i, s_x, ch)
            else:
                self.children[i].to_circuit(off_x + cw * i, off_y, cw, s_y)

    def answer(self):
        n1 = self._nodes[(0, self._WS)] = self._new_name()
        n2 = self._nodes[(self._WS, 0)] = self._new_name()
        self.to_circuit(0, 0, self._WS, self._WS)
        self._circuit.V('input', n1, n2, 10)
        print(self._circuit)
        sim = self._circuit.simulator()
        sim.
        dcv = sim.dc(Vinput=slice(10, 10, 0))
        cur = dcv['input']
        return cur


app = flask.Flask(__name__)

db: dict[str, Block] = {}


def answer(dct, status: int):
    result = flask.jsonify(dct)
    result.status = status
    return result


@app.route('/block/<id>', methods=['POST'])
def create(id: str) -> flask.Response:
    if id in db.keys():
        return answer({"error": "Circuit already present"}, 409)
    prng = random.Random()
    db[id] = Block.default(prng, flask.request.args.get('complexity', default=0.5, type=float))
    try:
        print(db[id].answer())
    except:
        pass
    return answer({'error': None}, 200)


@app.route('/block/<id>', methods=['GET'])
def get(id: str):
    if id in db.keys():
        return answer(jsons.dump(db[id], strip_privates=True), 200)
    else:
        return answer({"error": "Not found"}, 404)