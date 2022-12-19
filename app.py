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
    item = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', item=item)



@app.route('/createItem/', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        item_type = request.form['item_type']
        location = request.form['location']
        brand = request.form['brand']
        color = request.form['color']
        status = request.form['status']

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('Select * From Item Where item_type = %s and status = %s', (item_type, status))

        itemMatch = cur.fetchall()
        if itemMatch:
            print(itemMatch)
            print("Found a match")
            return itemMatch
        else:
            cur.execute('INSERT INTO item (item_type, location, brand, color, status)'
                        'VALUES (%s, %s, %s, %s, %s)',
                        (item_type, location, brand, color, status))


        
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