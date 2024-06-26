import rsa
from hashlib import sha256
from itertools import combinations
from random import SystemRandom
from oblivious_transfer.next_prime import next_prime
from oblivious_transfer.mulinv import mulinv

RSA_bits = 512

cryptorand = SystemRandom()
def randint(n):
    return cryptorand.randrange(n)

def moddiv(a, b, n):
    return a * mulinv(b, n) % n

def prod(x, G):
    p = 1
    for i in x:
        p *= i
    return p

def hasher(b):
    return sha256(b).hexdigest()

def lagrange(x, y, G):
    assert len(x) == len(y) and len(x) > 0, "Lengths of x and y must equal and non-zero."
    x_len = len(x)
    f = [0] * x_len
    for i in range(x_len):
        partial = []
        combo_list = list(x)
        combo_list.pop(i)
        for j in range(x_len):
            c = 0
            for k in combinations(combo_list, j):
                c += prod(map(lambda q: -q, k), G)
            partial.append(c)
        d = 1
        for j in range(x_len):
            if j != i:
                d *= x[i] - x[j]

        partial = map(lambda q: moddiv(q * y[i], d, G), partial)
        f = [(m + n) % G for m, n in zip(f, partial)] # also needs % G

    for i in range(x_len):
        assert compute_poly(f, x[i], G) == y[i], i
    return f

def bytes_to_int(m):
    return int.from_bytes(m, byteorder="big")

def int_to_bytes(i):
    return i.to_bytes(RSA_bits//8, byteorder="big")

def strip_padding(b, secret_length):
    return b[(RSA_bits//8 - secret_length):]

def compute_poly(f, x, m):
    y = 0
    for i in range(len(f)):
        y += f[i] * pow(x, len(f) - 1 - i, m)
    return y % m

class Alice:
    def __init__(self, M: [bytes], t: int):
        """
        Args:
            M: list of messages that Bob will choose from
            t: number of messages that Bob can choose
        """
        secret_length = len(M[0])
        assert secret_length < RSA_bits//8, "Secret length too long for RSA key size"
        for m in M:
            assert len(m) == secret_length, "Messages must all be same length"
        self.M = M
        self.t = t
        self.secret_length = secret_length

        (pubkey, privkey) = rsa.newkeys(RSA_bits)
        self.pubkey = pubkey
        self.privkey = privkey
        self.G = next_prime(self.pubkey.n)

        self.hashes = []

        for m in self.M:
            self.hashes.append(hasher(m))

    def setup(self):
        return {
            "pubkey": {"e": self.pubkey.e, "n": self.pubkey.n},
            "hashes": self.hashes,
            "secret_length": self.secret_length
        }

    def transmit(self, f):
        assert len(f) == self.t, "Bob is requesting a different number of messages than expected"

        G = []
        for i in range(len(self.M)):
            F = pow(compute_poly(f, i, self.G), self.privkey.d, self.pubkey.n)
            G.append((F * bytes_to_int(self.M[i])) % self.pubkey.n)

        return G


class Bob:
    def __init__(self, des_messages):
        """
        Args:
            des_messages: the indices of the messages Bob wants to obtain
        """
        self.num_des_messages = len(des_messages)
        self.des_messages = des_messages

    def setup(self, pubkey_e, pubkey_n, hashes, secret_length):

        self.pubkey = rsa.PublicKey(pubkey_n, pubkey_e)
        self.hashes = hashes
        self.secret_length = secret_length

        self.R = []
        T = []
        for j in range(self.num_des_messages):
            r = randint(self.pubkey.n)
            self.R.append(r)
            T.append(pow(r, self.pubkey.e, self.pubkey.n)) # the encrypted random value

        G = next_prime(self.pubkey.n)
        f = lagrange(self.des_messages, T, G)

        return f

    def receive(self, G):
        decrypted = []
        for j in range(self.num_des_messages):
            d = moddiv(G[self.des_messages[j]], self.R[j], self.pubkey.n)
            dec_bytes = int_to_bytes(d)
            decrypted.append(strip_padding(dec_bytes, self.secret_length))

            if hasher(decrypted[j]) != self.hashes[self.des_messages[j]]:
                print("Hashes don't match. Either something messed up or Alice is up to something.")

        self.decrypted = decrypted
        return decrypted


if __name__ == "__main__":
    import random
    secret_length = 63 # length of the keys (the messages Alice has) in bytes
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    #secrets = [bytes("".join(random.choice(alphabet) for _ in range(secret_length)), "ASCII") for __ in range(8)]
    secrets = [b'Secret message 1', b'Secret message 2', b'Secret message 3']
    secret_length = len(secrets[0])
    t = 2
    alice = Alice(secrets, t, secret_length)
    bob = Bob([0, 2])

    alice.setup()
    bob.setup()
    alice.transmit()
    M_prime = bob.receive()
    print(M_prime)

