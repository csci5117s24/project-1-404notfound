import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('EXTERNAL_DATABASE_URL')
#delete all value in table descriptions

TABLES_SETUP_SQL = [
    """
DROP TABLE IF EXISTS image_preference ;
"""
    """
    CREATE TABLE image_preference (
    preference_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    image_id INT NOT NULL,
    score FLOAT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (image_id) REFERENCES images(image_id) ON DELETE CASCADE
);


    """
]


def setup_database():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
    except Exception as e:
        print("Error connecting to the database: ", e)
        return
    
    for sql_statement in TABLES_SETUP_SQL:
        cursor.execute(sql_statement)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Database setup completed successfully.")

if __name__ == "__main__":
    setup_database()