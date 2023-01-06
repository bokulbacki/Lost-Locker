import os
import psycopg2

from dotenv import load_dotenv
load_dotenv()



conn = psycopg2.connect(
        host="localhost",
        database="postgres",
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"))

# Open a cursor to perform database operations
cur = conn.cursor()

# Execute a command: this creates a new table
cur.execute('DROP TABLE IF EXISTS item;')
cur.execute('CREATE TABLE item (id serial PRIMARY KEY,'
                                'item_type varchar (150) NOT NULL,'
                                'type2 varchar (150) NOT NULL,'
                                'brand varchar (150) NOT NULL,'
                                'color varchar (150) NOT NULL,'
                                'location varchar (150) NOT NULL,'
                                'status varchar (150) NOT NULL,'
                                'date_added date DEFAULT CURRENT_TIMESTAMP);'
                                )

# Insert data into the table

cur.execute('INSERT INTO item (item_type, type2, brand, color, location, status)'
        'VALUES (%s, %s, %s, %s, %s, %s)',
        ('Clothing',
        'T-shirt',
        'billabong',
        'Black',
        'library',
        'lost')
        )


cur.execute('INSERT INTO item (item_type, type2, brand, color, location, status)'
        'VALUES (%s, %s, %s, %s, %s, %s)',
        ('Clothing',
        'T-shirt',
        'Lulu',
        'Blue',
        'library',
        'lost')
        )


cur.execute('INSERT INTO item (item_type, type2, brand, color, location, status)'
        'VALUES (%s, %s, %s, %s, %s, %s)',
        ('Clothing',
        'T-shirt',
        'vuori',
        'green',
        'library',
        'lost')
        )

cur.execute('INSERT INTO item (item_type, type2, brand, color, location, status)'
        'VALUES (%s, %s, %s, %s, %s, %s)',
        ('Clothing',
        'T-shirt',
        'Lulu',
        'Black',
        'library',
        'lost')
        )

cur.execute('INSERT INTO item (item_type, type2, brand, color, location, status)'
        'VALUES (%s, %s, %s, %s, %s, %s)',
        ('Clothing',
        'T-shirt',
        'Lulu',
        'Yellow',
        'slp',
        'lost')
        )

conn.commit()

cur.close()
conn.close()