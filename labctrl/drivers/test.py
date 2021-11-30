import random
from labctrl.instrument import Instrument
from labctrl.parameter import Parameter

class RNG(Instrument):
    """ """

    seed = Parameter()
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
    rng = RNG(name="RNG", id="X", seed=1)
    print(rng.snapshot())
