import sqlite3
conn = sqlite3.connect("/opt/rewiredDB.db")
pointer = conn.cursor()
pointer.execute('drop table if exists wiredIndex;')
conn.commit()
conn.execute("vacuum")
conn.commit()
conn.close()
