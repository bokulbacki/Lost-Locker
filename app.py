import os
import psycopg2
import re
from datetime import datetime
from flask import Flask, render_template, request, url_for, redirect

from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)


def get_db_connection():
    conn = psycopg2.connect(host='localhost',
                            database='postgres',
                            user=os.getenv('DB_USERNAME'),
                            password=os.getenv('DB_PASSWORD'))
    return conn 



@app.route("/")
def home():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM item;')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('UI.html', items=items)

@app.route("/clothingClaim/", methods=('GET', 'POST'))
def clothing():
    return render_template('clothing_claim.html')

@app.route("/browse/")
def browse():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM item;')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('browse.html', items=items)

@app.route('/foundItem/', methods=('GET', 'POST'))
def found():
    if request.method == 'POST':


        conn = get_db_connection()
        cur = conn.cursor()
        
        print(request.form)

        
        item = None
        clothing_type = None
        brand = None
        color = None
        location = "library"
        status = "lost"


        if request.form['item_type'] == "Clothing":
            print("entered")
            item = "Clothing"
            return render_template('clothing_claim.html')
        conn.commit()
        cur.close()
        conn.close()
        
    return render_template('found_claim.html')

@app.route('/lostItem/', methods=('GET', 'POST'))
def lost():
    if request.method == 'POST':


        conn = get_db_connection()
        cur = conn.cursor()
        
        print(request.form)

        
        item = None
        clothing_type = None
        brand = None
        color = None
        location = "library"
        status = "lost"


        if request.form['item_type'] == "Clothing":
            print("entered")
            item = "Clothing"
            clothing_type = request.form['ClothingType']
            brand = request.form['ClothingBrand']
            color = request.form['Color']
            

            if location == None:
                lost_item_data = [item, clothing_type, brand, color]
            else:
                lost_item_data = [item, clothing_type, brand, color, location]


            #chnge lost status
            cur.execute('Select * From Item Where item_type = %s and status = %s', (item, "lost"))
            typeMatch = cur.fetchall()

            
           
            
            if typeMatch:
                print(len(typeMatch))
                found_items_dictionary = {}
                similarity_dictionary = {}
                itemMatchArrays = []

                #for all found items of the same  item type (clothing, waterbottle)
                for entry in typeMatch:
                    print(entry)
                    found_items_dictionary[entry[0]] = [entry[1], entry[2], entry[3], entry[4], entry[5]]
                itemMatchArrays.append(found_items_dictionary)

                print(lost_item_data)

                for item_id in found_items_dictionary:
                    print(item_id)
                    common_characteristics = len(set(lost_item_data) & set(found_items_dictionary[item_id]))
                   
                    
                    similarity_dictionary[item_id] = common_characteristics


                best_match = max(similarity_dictionary, key=similarity_dictionary.get)
                print(best_match)
                if best_match > 3:

                    return found_items_dictionary[best_match]

           

            



                

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

            item = request.form['item_type']
            bag_type = request.form['type2']
            brand = request.form['brand']
            color = request.form['color']
            stickers = request.form['stickers']
            location = request.form['location']

            if location == None:
                lost_item_data = [item, bag_type, brand, color, stickers]
            else:
                lost_item_data = [item, bag_type, brand, color, stickers, location]
        

        elif request.form['item_type'] == "wallet/purse":

            item = request.form['item_type']
            walletpurse_type = request.form['type2']
            brand = request.form['brand']
            color = request.form['color']
            stickers = request.form['stickers']
            location = request.form['location']

            if location == None:
                lost_item_data = [item, walletpurse_type, brand, color, stickers]
            else:
                lost_item_data = [item, walletpurse_type, brand, color, stickers, location]
        

        #elif request.form['item_type'] == "other":


      
        #create characteristics array for jaccard comparison
        

         
        
        cur.execute('INSERT INTO item (item_type, type2, brand, color, location, status)'
                        'VALUES (%s, %s, %s, %s, %s, %s)',
                        (item, clothing_type, brand, color, location, status))


        
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('home'))
    return render_template('lost_claim.html')
        
@app.route('/presentOptionsForLostItemClaim/', methods=('GET', 'POST'))
def presentOptionsForLostItemClaim():
    """
    Assumptions:
    - User is logged into LostLocker **
    - User has lost an item around campus and hopes to find it
    - They have chosen to create a lost item claim based on known information about it

    1. User is presented with initial question
        - Type of Item 
            -Backend: 1-5 (clothing, bottle, backpack, device, etc) 
    2. Using ItemType we present the full list of relevant attirubute types based on the item_attribute table
        - Differetiate betweeen the different categories based on codes
            1XX (Brand)
            2XX (Colors)
            4XX (model)
            5XX (Size)
            6XX (Location)
            7XX (Stickers)
            8XX (Cap Type)
        - Ideally one dropdown button per applicable category (reference item_attribute table)
    3. Gather all results and add them to the item_detail table using the original unique item_id
    4. Complete the item table entry
        fields:
            - item_id     unique
            - location (6XX) entry 
            - notes ??
            - submitted_by_user (automatic via logged in **)
            - datefound (automatic? **)
            - status (LOST)
    """
        
       
        
    
    
    
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