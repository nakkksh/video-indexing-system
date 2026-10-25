import os
import sqlite3
from flask import Flask, render_template, request, redirect, g, send_from_directory

# Initialize Flask App
app = Flask(__name__)

# Define Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "video_database.db")
VIDEO_FOLDER = os.path.join(BASE_DIR, "videos") 

# Function to get a database connection
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

# initialize the database and create the videos table if it doesn't exist
def initialize_database():
    os.makedirs(VIDEO_FOLDER, exist_ok=True)

    connection = sqlite3.connect(DATABASE)

    connection.execute('''CREATE TABLE IF NOT EXISTS videos (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            description TEXT,

            filename TEXT NOT NULL UNIQUE
        )
    ''')
    connection.commit()
    connection.close()

# insert a sample video entry into the database
def add_sample_videos():
    connection = sqlite3.connect(DATABASE)
    
    Sample_videos = [
    (
        "Sample Video",
        "This is a sample video for testing.",
        "sample.mp4"
    )
 ]

    for video in Sample_videos:
        connection.execute('INSERT OR IGNORE INTO videos (title, description, filename) VALUES (?, ?, ?)', video)
    connection.commit()
    connection.close()

# Search Route
@app.route('/')
def index():
    search_query = request.args.get('q', '').strip()

    db = get_db()
    if search_query:
        search_pattern = f"%{search_query}%"
        videos = db.execute('SELECT * FROM videos WHERE title LIKE ? OR description LIKE ? ORDER BY title', (
            search_pattern,
            search_pattern
        )).fetchall()
    else:
        videos = db.execute('SELECT id, title, description, filename FROM videos ORDER BY title').fetchall()

    return render_template('index.html', videos=videos, search_query=search_query)

    
# video playback route
@app.route('/video/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

if __name__ == '__main__':
    initialize_database()
    add_sample_videos()
    app.run(debug=True, host='127.0.0.1', port=5001)
