import hashlib

import sqlite3
import string
import random
# Related to coin signing
from blspy import G2Element

from chia.rpc.wallet_rpc_client import WalletRpcClient
from chia.rpc.full_node_rpc_client import FullNodeRpcClient

from chia.util.config import load_config
from chia.util.bech32m import decode_puzzle_hash
from chia.util.default_root import DEFAULT_ROOT_PATH

from chia.types.coin_spend import CoinSpend
from chia.types.spend_bundle import SpendBundle

from mojobattle.battle_driver import (
    create_coin_puzzle,
    create_coin_treehash,
    create_coin_txaddress,
    solution_for_password,
    create_coin_password_hash_from_string
)
import asyncio

from quart import Quart, render_template, request, url_for, redirect

# Instantiate the app
app = Quart(__name__)

# ========================================================
# GLOBAL VARIABLES
# ========================================================
full_node_rpc_client = None
wallet_rpc_client = None
sqlconnection = None
config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
wallet_host = "localhost"
wallet_rpc_port = config["wallet"]["rpc_port"]
node_rpc_port = config["full_node"]["rpc_port"]

# ========================================================
# HELPER METHODS
# ========================================================

#create 1 global connection for all users in app... to do test simultaneus connections
async def setup_blockchain_connection():
    global full_node_rpc_client, wallet_rpc_client

    # Should not create new connection if already connected
    if full_node_rpc_client is not None and wallet_rpc_client is not None:
        return

    # Setup the RPC connections
    full_node_rpc_client = await FullNodeRpcClient.create(wallet_host, node_rpc_port, DEFAULT_ROOT_PATH, config)
    wallet_rpc_client = await WalletRpcClient.create(wallet_host, wallet_rpc_port, DEFAULT_ROOT_PATH, config)

async def setup_sqlite3_connection():
    global sqlconnection
    try:
        if sqlconnection is None:

            sqlconnection = sqlite3.connect('db\mojobattle.db')


    except:

        print("Error sql")

def generate_random_password():
    ## characters to generate password from
    characters = list(string.ascii_letters + string.digits + "!@#$%^&*()")
	## length of password from the user
    length = int(20)

	## shuffling the characters
    random.shuffle(characters)

	## picking random characters from the list
    password = []
    for i in range(length):
        password.append(random.choice(characters))

	## shuffling the resultant password
    random.shuffle(password)

	## converting the list to string

    result = "".join(password)
    return result



# ========================================================
# QUART APPLICATION
# ========================================================


@app.route('/')
async def index():
    #create global connections
    #await setup_blockchain_connection()
    await setup_sqlite3_connection()

    #wallets = await wallet_rpc_client.get_wallets()
    #balance = await wallet_rpc_client.get_wallet_balance(wallets[0]["id"])

    return await render_template('index.html')#, balances=[balance['confirmed_wallet_balance'] / 1000000000000])

#create coin address with random password
@app.route('/create', methods=('GET', 'POST'))
async def create():
    #await setup_blockchain_connection()
    await setup_sqlite3_connection()
    # If a post request was made
    if request.method == 'POST':
        # Get variables from the form
        password = generate_random_password()
        masterwallet = 'txch1e7axrqvsjj3pa0km9uyf77zep03kka3rhfecse0ze2l0j6rudvgqf7k30t'
        mywallet = (await request.form)['mywallet']
        attack = (await request.form)['attack']
        if mywallet:
            # Get information for coin transaction
            coin_txaddress = create_coin_txaddress(
                create_coin_password_hash_from_string(password),decode_puzzle_hash(masterwallet),decode_puzzle_hash(mywallet),int(attack))
            #print(coin_txaddress)
            coin_treehash = create_coin_treehash(
                create_coin_password_hash_from_string(password),decode_puzzle_hash(masterwallet),decode_puzzle_hash(mywallet),int(attack))
            #print (coin_treehash)
            #save generated puzzle_hash with password and attack in DB and show it in web
            cursorObj = sqlconnection.cursor()
            entities = (None, coin_treehash, password, mywallet, attack, masterwallet,coin_txaddress)
            cursorObj.execute('INSERT INTO puzzle_hashs(id, puzhash, password, wallet, attack, masterwallet, puzwallet) VALUES(?, ?, ?, ?, ?, ?,?)', entities)
            sqlconnection.commit()

            # Redirect back to the home page on success
            return await render_template('index.html', coin_txaddress=coin_txaddress)

    # Show the create from template
    # For GET method
    return await render_template('create.html')




#show your address battles
@app.route('/search', methods=('GET', 'POST'))
async def search():
    await setup_sqlite3_connection()

    # If a post request was made
    if request.method == 'POST':
        mywallet = (await request.form)['mywallet']
        if mywallet:
            cursorObj = sqlconnection.cursor()
            # get all the puzzle hashgenerated for your wallet. to do get only used fields
            sentence = 'SELECT * FROM puzzle_hashs WHERE wallet = ' + '"' + mywallet + '"'

            result = cursorObj.execute(sentence)
            rows = cursorObj.fetchall()
            coins=[]
            for row in rows:
                #get all cains created with this puzzlehash. to do get only used fields
                sentence = 'SELECT * FROM coins WHERE puzhash_id = ' + str(row[0])

                result = cursorObj.execute(sentence)
                puzzlecoins = cursorObj.fetchall()
                #append all coins to coins list.
                for coin in puzzlecoins:

                    if coin[5]:
                        #add attack field of puzzle_hash to coin tuple. to do add opponet info
                        sentence = 'SELECT * FROM coins WHERE id = ' + str(coin[5])

                        result = cursorObj.execute(sentence)
                        #get transaction and puzzhash
                        opponentcoin = cursorObj.fetchone()
                        sentence = 'SELECT * FROM puzzle_hashs WHERE id = ' + str(opponentcoin[3])

                        result = cursorObj.execute(sentence)
                        opponentpuzz = cursorObj.fetchone()

                        coin = coin + (row[4],opponentpuzz[4])
                    else:
                        coin = coin + (row[4],None)
                    #print(coin)
                    coins.append(coin)


                # Redirect back to search page with coins list

            return await render_template('search.html', coins=coins)
    # Show the spend form template
    # If GET method
    return await render_template('search.html')

# This will run the app when this file is runned
app.run()
