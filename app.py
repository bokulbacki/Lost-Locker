import os
import psycopg2
import re
from datetime import datetime
from flask import Flask, render_template, request, url_for, redirect


app = Flask(__name__)


def get_db_connection():
    conn = psycopg2.connect(host='localhost',
                            database='postgres',
                            user=os.environ['DB_USERNAME'],
                            password=os.environ['DB_PASSWORD'])
    return conn 



@app.route("/")
def home():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM item;')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', items=items)



@app.route('/createItem/', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':


        conn = get_db_connection()
        cur = conn.cursor()
        
        if request.form['item_type'] == "clothing":
            
            item_type = request.form['item_type']
            clothing_type = request.form['type2']
            brand = request.form['brand']
            color = request.form['color']
            location = request.form['location']

            if location == None:
                lost_item_data = [item_type, clothing_type, brand, color]
            else:
                lost_item_data = [item_type, clothing_type, brand, color, location]


            #chnge lost status
            cur.execute('Select * From Item Where item_type = %s and status = %s', (item_type, "lost"))
            itemMatch = cur.fetchall()

           
            
            if itemMatch:

                dictionary = {}
                similarity_dictionary = {}
                itemMatchArrays = []
                for entry in itemMatch:
                    dictionary[entry[0]] = [entry[1], entry[2], entry[3], entry[4], entry[5]]
                itemMatchArrays.append(dictionary)

                print(lost_item_data)

                for key in dictionary:
                    common_characteristics = len(set(lost_item_data) & set(dictionary[key]))
                    print(dictionary[key])
                    
                    similarity_dictionary[key] = common_characteristics


                max_key = max(similarity_dictionary, key=similarity_dictionary.get)
                print(max_key)
                return dictionary[max_key]

           

            



                

        elif request.form['item_type'] == "waterbottle":
            item_type = request.form['item_type']
            
            brand = request.form['brand']
            color = request.form['color']
            stickers = request.form['stickers']
            location = request.form['location']

            if location == None:
                lost_item_data = [item_type, brand, color, stickers]
            else:
                lost_item_data = [item_type, brand, color, stickers, location]

        elif request.form['item_type'] == "device":

            item_type = request.form['item_type']
            device_type = request.form['type2']
            brand = request.form['brand']
            color = request.form['color']
            stickers = request.form['stickers']
            location = request.form['location']

            if location == None:
                lost_item_data = [item_type, device_type, brand, color, stickers]
            else:
                lost_item_data = [item_type, device_type, brand, color, stickers, location]
        

        elif request.form['item_type'] == "bag":

            item_type = request.form['item_type']
            bag_type = request.form['type2']
            brand = request.form['brand']
            color = request.form['color']
            stickers = request.form['stickers']
            location = request.form['location']

            if location == None:
                lost_item_data = [item_type, bag_type, brand, color, stickers]
            else:
                lost_item_data = [item_type, bag_type, brand, color, stickers, location]
        

        elif request.form['item_type'] == "wallet/purse":

            item_type = request.form['item_type']
            walletpurse_type = request.form['type2']
            brand = request.form['brand']
            color = request.form['color']
            stickers = request.form['stickers']
            location = request.form['location']

            if location == None:
                lost_item_data = [item_type, walletpurse_type, brand, color, stickers]
            else:
                lost_item_data = [item_type, walletpurse_type, brand, color, stickers, location]
        

        #elif request.form['item_type'] == "other":


        

        status = "lost"

        #create characteristics array for jaccard comparison
        

         
        
        cur.execute('INSERT INTO item (item_type, type2, brand, color, location, status)'
                        'VALUES (%s, %s, %s, %s, %s, %s)',
                        (item_type, clothing_type, brand, color, location, status))


        
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('home'))
    return render_template('createItem.html')
        

        
       
        
    
    
    
    # data = request.get_json()
    # name = data["brand"]

    # init_db.connect()
    
    # test = init_db.cur.fetchone()
    # return test

@app.route("/removeItem")
def removeItem():
    return "Removing item" 

@app.route("/USD")
def USD():
    return render_template('USDtemp.html')
   

@app.route("/hello/<name>")
def hello_there(name):
    now = datetime.now()
    formatted_now = now.strftime("%A, %d %B, %Y at %X")

    # Filter the name argument to letters only using regular expressions. URL arguments
    # can contain arbitrary text, so we restrict to safe characters only.
    match_object = re.match("[a-zA-Z]+", name)

    if match_object:
        clean_name = match_object.group(0)
    else:
        clean_name = "Friend"

    content = "Hello there, " + clean_name + "! It's " + formatted_now
    return content