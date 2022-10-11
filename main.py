import random
import flask
from enum import Enum


class BlockOr(Enum):
    V = 'v'
    H = 'h'

    def other(self):
        if self == BlockOr.V:
            return BlockOr.H
        else:
            return BlockOr.V


class Block:
    NEXT_DIV_P = 0.5
    MAX_CHILDREN = 4
    TEMP_MUL = 0.5

    def __init__(self, orient: BlockOr):
        self.orient = orient
        self.children = []

        self.freeRight = False
        self.freeLeft = False
        self.freeUp = False
        self.freeDown = False

        self.leftR = 0.0
        self.rightR = 0.0
        self.upR = 0.0
        self.downR = 0.0

    def populate(self, prng, temp):
        while prng.random() < self.NEXT_DIV_P * temp / (len(self.children) + 1) and len(
                self.children) < self.MAX_CHILDREN:
            newB = Block(self.orient.other())
            newB2 = Block(self.orient.other())
            newB.populate(prng, temp * self.TEMP_MUL)
            newB2.populate(prng, temp * self.TEMP_MUL)
            self.children.extend([newB, newB2])

    def placeResistors(self, prng, temp):
        if len(self.children) > 0:
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

                    child.placeResistors(temp * self.TEMP_MUL, prng)
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

                    child.placeResistors(temp * self.TEMP_MUL, prng)


app = flask.Flask(__name__)

db = {}


def answer(dct: dict, status: int):
    result = flask.jsonify(dct)
    result.status = status
    return result


@app.route('/block/<id>', methods=['POST'])
def create(id: str) -> flask.Response:
    if id in db.keys():
        return answer({"error": "Circuit already present"}, 403)
    prng = random.Random()
    block = Block(orient=BlockOr.V)
    block.populate(prng, flask.request.args.get('complexity', default=0.5, type=float))
    db[id] = block
    return answer({'error': None}, 200)


@app.route('/block/<id>', methods=['GET'])
def get(id: str):
    if id in db.keys():
        return answer(db[id], 200)
    else:
        return answer({"error": "Not found"}, 404)