from __future__ import annotations

import copy
import random


class AlphaCrossover:
    def crossover(self, parent_a, parent_b):
        child = copy.deepcopy(parent_a)
        if not child.children or not parent_b.children:
            return child
        index = random.randrange(len(child.children))
        source = random.choice(parent_b.children)
        child.children[index] = copy.deepcopy(source)
        return child
