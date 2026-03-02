import sqlite3

def init_db():
    connection = sqlite3.connect("smartcart.db")
    
    with open("schema.sql") as f:
        connection.executescript(f.read())
    
    connection.commit()
    connection.close()
    print("Database created successfully!")

if __name__ == "__main__":
    init_db()