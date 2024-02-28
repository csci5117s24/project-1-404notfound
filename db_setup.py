import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('EXTERNAL_DATABASE_URL')
TABLES_SETUP_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id SERIAL PRIMARY KEY,
        auth0_user_id VARCHAR(255) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'regular',
        profile_pic_url VARCHAR(255),
        user_name VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS images (
        image_id SERIAL PRIMARY KEY,
        user_id INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        image_url TEXT NOT NULL,
        prompt TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS comments (
        comment_id SERIAL PRIMARY KEY,
        image_id INT NOT NULL,
        user_id INT NOT NULL,
        comment TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (image_id) REFERENCES images(image_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS follows (
        follow_id SERIAL PRIMARY KEY,
        follower_id INT NOT NULL,
        following_id INT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (follower_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (following_id) REFERENCES users(user_id) ON DELETE CASCADE,
        UNIQUE (follower_id, following_id)
    );
    """
     """
    CREATE TABLE IF NOT EXISTS image_interactions (
        interaction_id SERIAL PRIMARY KEY,
        user_id INT NOT NULL,
        image_id INT NOT NULL,
        viewed BOOLEAN DEFAULT FALSE,
        liked BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (image_id) REFERENCES images(image_id) ON DELETE CASCADE,
        UNIQUE (user_id, image_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS image_similarities (
        image1_id INT NOT NULL,
        image2_id INT NOT NULL,
        similarity DECIMAL(5, 4) NOT NULL,
        PRIMARY KEY (image1_id, image2_id),
        FOREIGN KEY (image1_id) REFERENCES images(image_id) ON DELETE CASCADE,
        FOREIGN KEY (image2_id) REFERENCES images(image_id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS descriptions (
        description_id SERIAL PRIMARY KEY,
        user_id INT NOT NULL,
        description TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
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
