# -*- coding: utf-8
#
# Copyright (C) 2019 Peter Rowlands <peter@pmrowla.com>
# Copyright (C) 2014 tinfoil <https://bitbucket.org/tinfoil/>
#
# This file is a part of pylivemaker.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
"""LiveMaker scramble (encryption) module."""

import math
import struct

import numpy as np


# constant XOR key for LM3
LIVEMAKER3_SCRAMBLE_KEY = 0xF8EA


class LMScramble(object):
    """PRNG used for LM TScramble encryption.

    RE'd from TScrambleInts, TGetRandom classes in LM3 code.
    """

    # constants for LM3
    FACTORS = (
        0x7DD4FFC7,
        0x000005D4,
        0x000006F0,
        0x000013FB,
    )

    def __init__(self, seed=0):
        if seed == 0:
            seed = 0xFFFFFFFF
        seed = np.uint32(seed & 0xFFFFFFFF)
        self.seed = seed
        self.state = []
        for i in range(5):
            seed ^= seed << np.uint32(13) & 0xFFFFFFFF
            seed ^= seed >> np.uint32(17) & 0xFFFFFFFF
            seed ^= seed << np.uint32(5) & 0xFFFFFFFF
            self.state.append(np.uint32(seed))
        for i in range(19):
            self.rand()

    def rand(self):
        """Return a random integer in the range [0, uint32_max)."""
        x = np.sum(
            [
                np.multiply(np.uint64(self.state[3]), self.FACTORS[0], dtype=np.uint64),
                np.multiply(self.state[2], self.FACTORS[1], dtype=np.uint64),
                np.multiply(self.state[1], self.FACTORS[2], dtype=np.uint64),
                np.multiply(self.state[0], self.FACTORS[3], dtype=np.uint64),
                self.state[4],
            ],
            dtype=np.uint64,
        )
        self.state[4] = np.uint32((x >> np.uint64(32)) & np.uint64(0xFFFFFFFF))
        self.state[3] = self.state[2]
        self.state[2] = self.state[1]
        self.state[1] = self.state[0]
        self.state[0] = np.uint32(x & np.uint64(0xFFFFFFFF))
        return self.state[0]

    def random(self):
        """Return a random float in the range [0.0, 1.0)."""
        return self.rand() / 0x100000000

    def randint(self, low, high):
        """Return a random integer in the range [low, high]."""
        if low > high:
            raise ValueError("invalid range")
        return low + int(self.random() * (high - low + 1))

    @classmethod
    def randseq(self, count, seed):
        """Generate a random sequence of the specified length."""
        scramble = LMScramble(seed)
        values = list(range(count))
        seq = [0] * count
        i = 0
        while values:
            if len(values) == 1:
                n = 0
            else:
                n = scramble.randint(0, len(values) - 2)
            seq[values.pop(n)] = i
            i += 1
        return seq


def decrypt(data):
    """Unscramble the specified data stream and return the result."""
    if len(data) < 8:
        return data
    chunk_size, seed = struct.unpack("<iI", data[:8])
    total_chunks = math.ceil((len(data) - 8) / chunk_size)
    chunks = []
    for i in LMScramble.randseq(total_chunks, seed ^ LIVEMAKER3_SCRAMBLE_KEY):
        offset = 8 + i * chunk_size
        chunk = data[offset : offset + chunk_size]
        chunks.append(chunk)
    out = b"".join(chunks)
    if len(out) != len(data) - 8:
        raise ValueError("data mismatch")
    return out
