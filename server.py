import hashlib
import sqlite3
import string
import random
import asyncio
import threading
import hashlib
import time
# Related to coin signing
from blspy import G2Element
from chia.types.blockchain_format.program import Program
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


# ========================================================
# GLOBAL VARIABLES
# ========================================================


config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
wallet_host = "localhost"
wallet_rpc_port = config["wallet"]["rpc_port"]
node_rpc_port = config["full_node"]["rpc_port"]

sqlite3_path = 'db\mojobattle.db'
mincoinvalue=100
# ========================================================
# HELPER METHODS
# ========================================================
#open db connection
async def open_sqlite3_connection(db_path):
    try:
        con = sqlite3.connect(db_path)
        return con

    except:
        raise Exception( "Error en open_sqlite3_connection")
#close db connection
async def close_sqlite3_connection(connection):
        try:
            connection.close()
            return "CLOSED"

        except:
            raise Exception( "Error en close_sqlite3_connection")
#create db tables
async def setup_db():
    con = await open_sqlite3_connection(sqlite3_path)
    cursorObj = con.cursor()
    #cursorObj.execute("CREATE TABLE puzzle_hashs(id integer PRIMARY KEY AUTOINCREMENT, puzhash text, password text, wallet text, attack integer, masterwallet text, puzwallet text)")


    #con.commit()

    cursorObj.execute("CREATE TABLE coins (id integer PRIMARY KEY AUTOINCREMENT,coin_id text, amount integer, puzhash_id integer, state integer, opponent_id integer, tr text, result integer)")

    con.commit()
    await close_sqlite3_connection(con)
#return random password
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
#add new created coins to local db and update status
async def update_coins():
    try:
        #create chia node connection
        full_node_rpc_client = await open_blockchain_connection()

        #create local db connection
        sqlconnection = await open_sqlite3_connection(sqlite3_path)

        cursorObj = sqlconnection.cursor()
        #get all puzzle hash calculated by webapp. to do get only used fields
        sentence = 'SELECT * FROM puzzle_hashs'

        result = cursorObj.execute(sentence)
        rows = cursorObj.fetchall()
        coins_added=0
        coins_updated=0
        for row in rows:



            # Get variables from the DB
            password = row[2]
            masterwallet = row[5]
            attack = row[4]
            mywallet = row[3]

            # create tree hash.... ¿it is saved in db?

            coin_treehash = row[1]#create_coin_treehash(
                #create_coin_password_hash_from_string(password),decode_puzzle_hash(masterwallet),decode_puzzle_hash(mywallet),int(attack))
            #get all coins created with this treehash. to do get only from last blocks.
            coin_records = await full_node_rpc_client.get_coin_records_by_puzzle_hash(coin_treehash)

            for coin_record in coin_records:

                # check if coin is in DB. to do use coin name, no parent info
                sentence= 'SELECT * FROM coins WHERE coin_id = '+'"'+str(coin_record.coin.parent_coin_info)+'"'

                select_coin = cursorObj.execute(sentence)
                coin= select_coin.fetchone()
                #if coin is spent state is 1
                if coin_record.spent == True:
                    state=1
                else:
                    state=0
                #  if coin exists in db update state field, to do only if is diferent.
                if coin:
                    #if coin is spent and state is pendig update it
                    if coin[4] == 3 and state == 1:
                        #print(coin_record.coin)
                        #print(hashlib.sha256(coin_record.coin.parent_coin_info +
                        #coin_record.coin.puzzle_hash + bytes(str(coin_record.coin.amount),"utf8")).hexdigest())

                        entities = (state,coin[0])

                        cursorObj.execute('UPDATE coins SET state = ? WHERE id = ?',entities)

                        sqlconnection.commit()
                        coins_updated +=1
                else:
                    #if coin is not in db add it.
                    entities = (None, str(coin_record.coin.parent_coin_info), coin_record.coin.amount, row[0], state)
                    cursorObj.execute('INSERT INTO coins(id, coin_id, amount, puzhash_id, state) VALUES(?, ?, ?, ?, ?)', entities)
                    sqlconnection.commit()
                    coins_added += 1
        print("coins updated: "+str(coins_updated))
        print("coins added: "+str(coins_added))

    except:
        raise Exception( "Error en update_coins")

    finally:
        #close connections
        await close_sqlite3_connection(sqlconnection)
        await close_blockchain_connection(full_node_rpc_client)

#spend a coin (coin to spend, opponent coin, puzzle of coin 1, puzzle of coin2, connection to db)
async def spend_battle(coin1,coin2,puzzle1,puzzle2,sqlconnection):

    #get all parameters
    mywallet = puzzle1[3]
    password = puzzle1[2]
    masterwallet = puzzle1[5]
    attack = puzzle1[4]
    amount = coin1[2]
    oponentwallet = puzzle2[3]
    oponentattack = puzzle2[4]


    try:
        #open blockchain conection
        full_node_rpc_client= await open_blockchain_connection()
        # Get Spend Bundle Parameters
        coin_reveal = create_coin_puzzle(
            create_coin_password_hash_from_string(password),decode_puzzle_hash(masterwallet),decode_puzzle_hash(mywallet),int(attack))
        coin_treehash = create_coin_treehash(
            create_coin_password_hash_from_string(password),decode_puzzle_hash(masterwallet),decode_puzzle_hash(mywallet),int(attack))
        coin_records = await full_node_rpc_client.get_coin_records_by_puzzle_hash(coin_treehash)


        coin_to_spend = None
        #search coin with parent_coin_info to spend. to do use coin name sha256(parent_coin_info, puzzle_hash,amount) not working
        for coin_record in coin_records:
            #print(coin1[1])
            #print(str(coin_record.coin.parent_coin_info))
            if str(coin_record.coin.parent_coin_info) == coin1[1]:
                coin_to_spend = coin_record
                break

        # If there's no coin
        if coin_to_spend == None or coin_to_spend.spent == True:
            print("NO COIN AVAILABLE")
            # TODO: Show error on client

        else:
            # Get the coin solution
            #print(coin_to_spend)
            #decoded_address = decode_puzzle_hash(address)
            coin_solution = solution_for_password(
                password,int(amount),decode_puzzle_hash(oponentwallet),int(oponentattack))

            # Put together our spend bundle
            tx_spend_bundle = SpendBundle(
                [
                    CoinSpend(
                        coin_to_spend.coin,
                        coin_reveal,
                        coin_solution,
                    )
                ],
                G2Element(),
            )

            # Try to send the spend bundle to the network

            await full_node_rpc_client.push_tx(tx_spend_bundle)

            # calcular ataque y actualizar bd
            #print(transaction)
            result=0
            if attack == oponentattack:
                result=0
            else:
                if (attack == (oponentattack + 1)) or (attack == 1 and oponentattack == 3 ):
                    result=1
                else:
                    result=2
            cursorObj = sqlconnection.cursor()
            entities = (3,coin2[0],result,coin1[0])
            print(entities)
            cursorObj.execute('UPDATE coins SET state = ?, opponent_id = ?, result = ? WHERE id = ?',entities)

            sqlconnection.commit()
    except:
        raise Exception( "Error en spend_battle coin: "+coin1[0])
    finally:
        #close node conection
        await close_blockchain_connection(full_node_rpc_client)

#pair coins to fight
async def mojobattle():

    try:
        #open bd connection
        sqlconnection=await open_sqlite3_connection(sqlite3_path)

        cursorObj = sqlconnection.cursor()
        #get all coins not spent. to do get onlu usued fields
        sentence = 'SELECT * FROM coins WHERE state = 0'

        result = cursorObj.execute(sentence)
        rows = cursorObj.fetchall()
        # init all values to null
        coin1=None
        coin2=None
        puzzle1=None
        puzzle2=None
        for row in rows:
            #get first coin if none
            if not coin1 and row[2] >= mincoinvalue:
                coin1=row
                #get puzzlehass values (password etc)
                sentence= 'SELECT * FROM puzzle_hashs WHERE id = '+str(coin1[3])
                #entities=(str(coin1[3]))
                select_puzz = cursorObj.execute(sentence)
                puzzle1=select_puzz.fetchone()
                #print (coin1[0])
            else:
                # get coin 2 if one is selected
                coin2=row
                #get puzzle hash of coin 2
                sentence= 'SELECT * FROM puzzle_hashs WHERE id = '+str(coin2[3])
                #entities=(str(coin2[3]))
                select_puzz = cursorObj.execute(sentence)
                puzzle2=select_puzz.fetchone()
                #if wallet of 2 coins is diferent do fight, else get next coin as coin2
                if not puzzle1[3] == puzzle2[3] and row[2] >= mincoinvalue:
                    #spend coin1
                    print("send coins "+str(coin1[0])+" and "+str(coin2[0]))
                    await spend_battle(coin1,coin2,puzzle1,puzzle2,sqlconnection)
                    time.sleep(2)
                    #spend coin 2
                    await spend_battle(coin2,coin1,puzzle2,puzzle1,sqlconnection)
                    #reset all values to pair next two
                    coin1=None
                    coin2=None
                    puzzle1=None
                    puzzle2=None
    except:
        raise Exception( "Error en mojobattle")
    finally:
        #close local db connection
        await close_sqlite3_connection(sqlconnection)
#open node connection
async def open_blockchain_connection():
    try:
        full_node_rpc_client = await FullNodeRpcClient.create(wallet_host, node_rpc_port, DEFAULT_ROOT_PATH, config)
        return full_node_rpc_client

    except:
        raise Exception( "Error en opencon")
#clos node conection
async def close_blockchain_connection(connection):
        try:
            connection.close()
            return "CLOSED"

        except:
            raise Exception( "Error en opencon")



#setup_db(con)
async def check_coins():
    try:
        #create chia node connection
        full_node_rpc_client = await open_blockchain_connection()

        #create local db connection
        sqlconnection = await open_sqlite3_connection(sqlite3_path)

        cursorObj = sqlconnection.cursor()
        #get all puzzle hash calculated by webapp. to do get only used fields
        sentence = 'SELECT * FROM puzzle_hashs'

        result = cursorObj.execute(sentence)
        rows = cursorObj.fetchall()
        coins_added=0
        coins_updated=0

        for row in rows:

            print(row)

            # Get variables from the DB
            password = row[2]
            masterwallet = row[5]
            attack = row[4]
            mywallet = row[3]

            # create tree hash.... ¿it is saved in db?

            coin_treehash = row[1]#create_coin_treehash(
                #create_coin_password_hash_from_string(password),decode_puzzle_hash(masterwallet),decode_puzzle_hash(mywallet),int(attack))
            #get all coins created with this treehash. to do get only from last blocks.
            coin_records = await full_node_rpc_client.get_coin_records_by_puzzle_hash(coin_treehash)
            print(coin_records)
            for coin_record in coin_records:

                # check if coin is in DB. to do use coin name, no parent info
                sentence= 'SELECT * FROM coins WHERE coin_id = '+'"'+str(coin_record.coin.parent_coin_info)+'"'

                select_coin = cursorObj.execute(sentence)
                coin= select_coin.fetchone()
                #if coin is spent state is 1
                if coin_record.spent == True:
                    state=1
                else:
                    state=0
                #  if coin exists in db update state field, to do only if is diferent.
                if coin:
                    #if coin is spent and state is pendig update it
                    print(coin)
                    print(str(state))
                    coins_updated +=1
                else:
                    #if coin is not in db add it.
                    entities = (None, str(coin_record.coin.parent_coin_info), coin_record.coin.amount, row[0], state)
                    cursorObj.execute('INSERT INTO coins(id, coin_id, amount, puzhash_id, state) VALUES(?, ?, ?, ?, ?)', entities)
                    sqlconnection.commit()
                    coins_added += 1
        print("coins updated: "+str(coins_updated))
        print("coins added: "+str(coins_added))

    except:
        raise Exception( "Error en update_coins")

    finally:
        #close connections
        await close_sqlite3_connection(sqlconnection)
        await close_blockchain_connection(full_node_rpc_client)


#loop process may this is not best way
loop = asyncio.get_event_loop()
while True:
    loop.run_until_complete(setup_db())
    #loop.run_until_complete(check_coins())
    loop.run_until_complete(update_coins())
    print("end 1")
    time.sleep(20)

    loop.run_until_complete(mojobattle())
    print("end 2")
    time.sleep(20)

loop.close()
