from numbers import Real
import random
from labctrl.instrument import Instrument
from labctrl.parameter import Parameter

def errorcheck(fn):
    print(fn)
    
class RNG(Instrument):
    """ """

    seed = Parameter(bounds=[Real, [1e9, 5e9]])
    number = Parameter()

    def connect(self):
        print(f"connected to {self}")

    @seed.setter
    def seed(self, value):
        random.seed(value)

    @number.getter
    def number(self):
        return random.random()

if __name__ == "__main__":
    rng = RNG(name="RNG", id="X", seed=4000000000)
    print(f"{rng.number = }")
