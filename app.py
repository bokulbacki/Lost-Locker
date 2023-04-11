import os
import psycopg2
import re
from datetime import datetime
from flask import Flask, render_template, request, url_for, redirect, jsonify
import uuid
from PIL import Image
from io import BytesIO
import traceback
from psycopg2 import Binary
import glob


from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)

#tyler branch
# def get_db_connection():
#     conn = psycopg2.connect(host='localhost',
#                             database='postgres',
#                             user=os.getenv('DB_USERNAME'),
#                             password=os.getenv('DB_PASSWORD'))
#     return conn 

#connection to LostLocker AWS DB
def get_db_connection():
    conn = psycopg2.connect(database='initial_db', user='postgres', password='notlostbutfound', host='my-ll-db.cw9eo1fjiaor.us-west-2.rds.amazonaws.com', port='5432')
    return conn  


#login page route
@app.route("/")
def loginPage():
    
    return render_template('loginPage.html')


#home page route
@app.route("/home/")
def home():
    return render_template('UI.html')



@app.route('/images/<path:path>')
def serve_static(path):
    return app.send_static_file(path)


#return all items, and their characteristics, that are in the locker (found items)
@app.route("/api/getFilteredItems")
def getFilteredItems():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('select DISTINCT item_id from locker_items;')
    item_ids = cur.fetchall()
   
    items_dict = {}
    count = 0
    for item in item_ids:

        cur.execute("select description from locker_items\
                    where item_id =" + str(item[0]) + ";")
        
        items = cur.fetchall()
        items_dict[count] = items
        count += 1
    
      

#this route renders and displays the basics of all items that are in the locker 
@app.route("/browse/")
def browse():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('select DISTINCT item_id from locker_items;')
    item_ids = cur.fetchall()
  
    result_dict = {}
    
    for item in item_ids:

        cur.execute("select item_id, attributetype, description,itemtype from locker_items\
                    where item_id =" + str(item[0]) + ";")
        
        items = cur.fetchall()

        
        for row in items:
           
            item_id = row[0]
            attr_type = row[1]
            desc = row[2]
    
            if item_id not in result_dict:
                result_dict[item_id] = {}
    
            result_dict[item_id][attr_type] = desc
        result_dict[item_id]['Item Type'] = row[3]
        
    cur.close()
    conn.close()
    return render_template('browse4.html', result_dict=result_dict)


#route to submit a lost item request
@app.route('/lostitem/', methods=('GET', 'POST'))
def lostitem():
    if request.method == 'POST':
        status = 'Lost'
        process(status)
   
        
        return render_template('lost_claim.html')
    else:

        return render_template('lost_claim.html')
    

#route to submit a found item request
@app.route('/foundItem/', methods=('GET', 'POST', 'PUT'))
def founditem():
    if request.method == 'POST' or request.method == 'PUT':
        status = 'Found'
        
        process(status)
        return render_template('found_claim.html')
    else:

        return render_template('found_claim.html')


#api that returns all item types from DB (used for dropdown)
@app.route('/api/item-type')
def ReturnJSON():
    conn = get_db_connection()
    cur = conn.cursor()
    data = cur.execute('SELECT * FROM itemtype')
    items = cur.fetchall()
    conn.close()
    return jsonify(items)
  

#api with special query to return the attributes applicable to the specified item type (used for dropdown)
@app.route('/api/returnAttributes')
def returnAttributes():
    var1=  request.args.get('var1')
    var2 = request.args.get('var2')
    conn = get_db_connection()
    cur = conn.cursor()
    
    data = cur.execute('select i.itemtype_id, i.itemtype, a.attributetype_id, a.attributetype, a.description, ia.itemtype_id, ia.attributetype_id from itemtype i, item_attribute ia, attributetype a where i.itemtype_id = ia.itemtype_id and a.attributetype_id = ia.attributetype_id and i.itemtype_id =' + var1 + " and a.attributetype = '" + var2 + "'")
    items = cur.fetchall()
    conn.close()
    return jsonify(items)


#processes user input from lost item, inserts into DB, matching function should also be called in here to find potential match
def process(status):
    conn = get_db_connection()
    cur = conn.cursor()
   
    #store all input into variables
    itemTypeID = request.form['available-items']
    clothingType = request.form['clothing-types']
    brand = request.form['brands']    
    model = request.form['models']
    color = request.form['color']
    size = request.form['size']
    stickers = request.form['stickers']
    book = request.form['book']
    location = request.form['location']
    file = request.files['image-upload']
   

    print("entered!!")
    #tries to open image file
    try:
        buffer = BytesIO()
        file.save(buffer)
        buffer.seek(0)
        img = Image.open(buffer)
        img.load()
    except Exception as e:
        print(traceback.format_exc())
        return 'Invalid file type!' 
    

    filename = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ['.jpg', '.jpeg', '.png', '.heic']:
       
        return 'Invalid file type!'
    

    notes = "..."
    user = "John"
    current_date = datetime.now().strftime('%Y-%m-%d')
    cur.execute('INSERT INTO item (location, notes, submitted_by_user, datefound, status)'
                      'VALUES (%s, %s, %s, %s, %s)',
                        (location, notes, user, current_date, status))
    



    cur.execute("SELECT currval('item_item_id_seq')")
    new_id = cur.fetchone()[0]

    filename = str(new_id) + ext
    buffer.seek(0)  # Move the buffer cursor back to the beginning
    with open(os.path.join('static/styles/images', filename), 'wb') as f:
        f.write(buffer.read())  # Write the buffer contents to the file

    
    if ext in ('.jpg', '.jpeg'):
        img.save(buffer, format='JPEG')
    elif ext in('.png'):
        img.save(buffer, format='PNG')
    image_data = buffer.getvalue()


    attributes_d = {"Item Type": itemTypeID, "Clothing Type": clothingType, "Brand": brand, "Model": model, "Color": color, "Size": size, "Stickers": stickers, "Book": book, "Location": location}
   
    #matching(attributes_d)

    attributes = [clothingType, brand, model, color, size, stickers, book, location]

  
    

    

    for item in attributes:
        
        if item != '':
            
            cur.execute("SELECT attributeType_id FROM attributeType WHERE description ='" + item + "'")
            result = cur.fetchone()[0]
            cur.execute('INSERT INTO item_detail (item_id, itemType_id, attributetype_id)'
                        'VALUES (%s, %s, %s)',
                        (new_id, itemTypeID, result))
        
    buffer.close()
    conn.commit()
    cur.close()
    conn.close()
    







def matching(attributes_d):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('drop view IF EXISTS locker_items')
    cur.execute("create view locker_items as\
                Select i.item_id, i.location, i.status, a.attributetype, a.description, it.itemtype\
                from item i, item_detail id, itemtype it, item_attribute ia, attributetype a\
                where i.item_id = id.item_id\
                and it.itemtype_id = id.itemtype_id\
                and ia.attributetype_id = id.attributetype_id\
                and ia.itemtype_id = id.itemtype_id\
                and ia.attributetype_id = a.attributetype_id\
                and i.status = 'Found'\
                order by item_id")
    

     #if its clothing
    if attributes_d['Item Type'] == '1':


        #return ranked items by if clothing type match and if (brand or size or color match)
        cur.execute("Select count(item_id) as rank, item_id\
                    from locker_items\
                    where itemtype = 1\
                    and description = '" + attributes_d['Cothing Type'] + "' and (description = '" + attributes_d['Brand'] + "' or description = '" + attributes_d['Color'] + "' or description = '" + attributes_d['Size'] + "')\
                    group by item_id\
                    order by item_id;")
        
        
    #     #if its a water bottle    
    elif attributes_d['Item Type'] == '2':
        

        #if brand or color or stickers match
        cur.execute("Select count(item_id) as rank, item_id\
                    from locker_items\
                    where itemtype = 'Bottle'\
                    and (description = '" + attributes_d['Brand'] + "' or description = '" + attributes_d['Color'] + "' or description = '" + attributes_d['Stickers'] + "')\
                    group by item_id\
                    order by item_id;")
        
       
        ranked_items = cur.fetchall()
        
    
    elif attributes_d['Item Type'] == '3':

        #if brand or color or stickers match
        cur.execute("Select count(item_id) as rank, item_id\
                    from locker_items\
                    where itemtype = 1\
                    and (description = '" + attributes_d['Brand'] + "' and description = '" + attributes_d['Model'] + "')\
                    group by item_id\
                    order by item_id;")
        
    
    elif attributes_d['Item Type'] == '4':

        #if brand or color or stickers match
        cur.execute("Select count(item_id) as rank, item_id\
                    from locker_items\
                    where itemtype = 1\
                    and (description = '" + attributes_d['Brand'] + "' or description = '" + attributes_d['Color'] + "')\
                    group by item_id\
                    order by item_id;")
        

    elif attributes_d['Item Type'] == '5':

        return None 


    
    
    conn.commit()
    cur.close()
    conn.close()
            
       




        
       
        
    
    
    
@app.route("/delete_item/<item_id>", methods=('GET', 'POST'))
def delete_item(item_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM item WHERE item_id =" + str(item_id) + ";")
    conn.commit()

    folder_path = os.path.join(os.getcwd(), 'static', 'styles', 'images')
    file_pattern = os.path.join(folder_path, f'{item_id}.*')
    filename_list = glob.glob(file_pattern)
    if filename_list:
        os.remove(filename_list[0])
        print("deleted")
    else:
        print("none")
    

    cur.execute('select DISTINCT item_id from locker_items;')
    item_ids = cur.fetchall()
  
  
    print(item_ids)
    result_dict = {}
    
    for item in item_ids:
        cur.execute("select item_id, attributetype, description,itemtype from locker_items\
                    where item_id =" + str(item[0]) + ";")
        items = cur.fetchall()
        for row in items:   
            item_id = row[0]
            attr_type = row[1]
            desc = row[2]
            if item_id not in result_dict:
                result_dict[item_id] = {}
            result_dict[item_id][attr_type] = desc
        result_dict[item_id]['Item Type'] = row[3]
        
    cur.close()
    conn.close()
    return render_template('browse4.html', result_dict=result_dict)

   

@app.route("/USD")
def USD():
    return render_template('USDtemp.html')
   

