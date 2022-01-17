import hashlib

from chia.types.blockchain_format.program import Program
from chia.util.bech32m import encode_puzzle_hash
from cdv.util.load_clvm import load_clvm

# Load the Chialisp puzzle code
BATTLE_MOD = load_clvm("mojobattle.clsp", "mojobattle")


def create_coin_puzzle(PASSWORD_HASH, MASTER_PUZZLE_HASH, WALLET, ATTACK):
    """ Return curried version of the puzzle
    """

    return BATTLE_MOD.curry(PASSWORD_HASH, MASTER_PUZZLE_HASH, WALLET, ATTACK)


def create_coin_treehash(PASSWORD_HASH, MASTER_PUZZLE_HASH, WALLET, ATTACK):
    """ Return treehash for the puzzle
    """

    return create_coin_puzzle(PASSWORD_HASH, MASTER_PUZZLE_HASH, WALLET, ATTACK).get_tree_hash()


def create_coin_txaddress(PASSWORD_HASH, MASTER_PUZZLE_HASH, WALLET, ATTACK, address_prefix='txch'):
    """ Return puzzle address
    """

    return encode_puzzle_hash(create_coin_treehash(PASSWORD_HASH, MASTER_PUZZLE_HASH, WALLET, ATTACK), address_prefix)


def create_coin_password_hash_from_string(password):
    """ Return password hash
    """

    return bytes.fromhex(hashlib.sha256(password.encode()).hexdigest())

def create_bytes_hash_from_string(anystring):
    """ Return password hash
    """

    return bytes.fromhex(hashlib.sha256(anystring.encode()).hexdigest())

def solution_for_password(password, oponent_wallet):
    """ Return puzzle solution
    """

    return Program.to([password, oponent_wallet])
