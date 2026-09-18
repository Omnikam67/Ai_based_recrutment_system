import os
import mysql.connector

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "Avinash@2006"),
        database=os.getenv("DB_NAME", "talent_acquisition")
    )
