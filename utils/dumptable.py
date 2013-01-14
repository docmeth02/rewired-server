import sqlite3
conn = sqlite3.connect("wiredDB.db")
try:
	pointer = conn.cursor()
	pointer.execute("SELECT * FROM wiredUsers")
	data = pointer.fetchall()
except sqlite3.OperationalError, msg:
    print msg
print data
conn.close()