import os
import psycopg2
import re
from datetime import datetime
from flask import Flask, render_template, request, url_for, redirect, jsonify

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
def loginPage():
    return render_template('loginPage.html')

@app.route("/home/")
def home():
    return render_template('UI.html')

@app.route("/browse/")
def browse():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM item;')
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('browse.html', items=items)

@app.route('/lostitem/', methods=('GET', 'POST'))
def lostitem():
   
        
    return render_template('lost_claim.html')

@app.route('/foundItem/', methods=('GET', 'POST'))
def founditem():
    if request.method == 'POST':
        process()
        return render_template('found_claim.html')
    else:

        return render_template('found_claim.html')

@app.route('/api/item-type')
def ReturnJSON():
    conn = get_db_connection()
    cur = conn.cursor()
    data = cur.execute('SELECT * FROM itemtype')
    items = cur.fetchall()
    conn.close()
    return jsonify(items)
  

@app.route('/api/returnAttributes')
def returnAttributes():
    var1=  request.args.get('var1')
    var2 = request.args.get('var2')
    conn = get_db_connection()
    cur = conn.cursor()
    print("Var1 : " + var1)
    print("Var2 : " + var2)
    data = cur.execute('select i.itemtype_id, i.itemtype, a.attributetype_id, a.attributetype, a.description, ia.itemtype_id, ia.attributetype_id from itemtype i, item_attribute ia, attributetype a where i.itemtype_id = ia.itemtype_id and a.attributetype_id = ia.attributetype_id and i.itemtype_id =' + var1 + " and a.attributetype = '" + var2 + "'")
    items = cur.fetchall()
    conn.close()
    return jsonify(items)


def process():
    itemType = request.form['available-items']
    print("item: " + itemType)
    clothingType = request.form['clothing-types']
    print("clothingtype: " + clothingType)
    brand = request.form['brands']
    print("brand: " + brand)
    model = request.form['models']
    print("model: " + model)
    color = request.form['color']
    print("color: " + color)
    size = request.form['size']
    print(size)
    stickers = request.form['stickers']
    print("stickers: " +stickers)
    book = request.form['book']
    print("book: " + book)
    location = request.form['location']
    print("location: " + location)

    



@app.route('/createItem/', methods=('GET', 'POST'))
def create():
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
    return render_template('createitem.html')
        

        
       
        
    
    
    
@app.route("/removeItem")
def removeItem():
    return "Removing item" 

@app.route("/USD")
def USD():
    return render_template('USDtemp.html')
   

