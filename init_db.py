import os
import psycopg2



conn = psycopg2.connect(
        host="localhost",
        database="postgres",
        user=os.environ["DB_USERNAME"],
        password=os.environ["DB_PASSWORD"])

# Open a cursor to perform database operations
cur = conn.cursor()

# Execute a command: this creates a new table
cur.execute('DROP TABLE IF EXISTS item;')
cur.execute('CREATE TABLE item (id serial PRIMARY KEY,'
                                'item_type varchar (150) NOT NULL,'
                                'location varchar (150) NOT NULL,'
                                'brand varchar (150) NOT NULL,'
                                'color varchar (150) NOT NULL,'
                                'status varchar (150) NOT NULL,'
                                'date_added date DEFAULT CURRENT_TIMESTAMP);'
                                )

# Insert data into the table

cur.execute('INSERT INTO item (item_type, location, brand, color, status)'
        'VALUES (%s, %s, %s, %s, %s)',
        ('iphone',
        'classroom 1',
        'samsung',
        'silver',
        'lost')
        )


cur.execute('INSERT INTO item (item_type, location, brand, color, status)'
        'VALUES (%s, %s, %s, %s, %s)',
        ('iphone',
        'classroom 2',
        'apple',
        'white',
        'lost')
        )

conn.commit()

cur.close()
conn.close()