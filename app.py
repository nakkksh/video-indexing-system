import os
import sqlite3
from flask import Flask, render_template, request, redirect, g, send_from_directory, redirect, url_for, flash

# Initialize Flask App
app = Flask(__name__)
app.secret_key = '1122334455'  # Required for flash messages

# Define Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "video_database.db")
VIDEO_FOLDER = os.path.join(BASE_DIR, "videos")
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Limit upload size to 100MB

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

# Upload Route
@app.route("/upload", methods=["POST"])
def upload_video():

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    file = request.files.get("video")

    if not title or not file or not file.filename:
        flash("Please enter a title and select a video.")
        return redirect(url_for("index"))

    if not file.filename.lower().endswith(".mp4"):
        flash("Please upload an MP4 file.")
        return redirect(url_for("index"))

    filename = os.path.basename(file.filename)

    try:
        connection = sqlite3.connect(DATABASE)

        existing = connection.execute(
            "SELECT id FROM videos WHERE filename = ?",
            (filename,)
        ).fetchone()

        if existing:
            connection.close()
            flash("A video with this filename already exists.")
            return redirect(url_for("index"))

        file_path = os.path.join(VIDEO_FOLDER, filename)
        file.save(file_path)

        connection.execute(
            """
            INSERT INTO videos (title, description, filename)
            VALUES (?, ?, ?)
            """,
            (title, description, filename)
        )

        connection.commit()
        connection.close()

        flash("Video uploaded successfully!")

    except sqlite3.Error:
        if os.path.exists(file_path):
            os.remove(file_path)

        flash("Database error. Please try again.")

    return redirect(url_for("index"))


# Close the database connection after each request
if __name__ == '__main__':
    initialize_database()
    add_sample_videos()
    app.run(debug=True, host='127.0.0.1', port=5001)
