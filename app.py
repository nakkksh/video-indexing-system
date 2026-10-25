import os
import sqlite3
import uuid

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from flask import (
    Flask, render_template, request, redirect, g, send_from_directory,
    url_for, flash, abort
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-in-render-environment")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "video_database.db")
VIDEO_FOLDER = os.path.join(BASE_DIR, "videos")
app.config["VIDEO_FOLDER"] = VIDEO_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

# Configure Cloudinary from Render Environment Variables.
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def initialize_database():
    os.makedirs(VIDEO_FOLDER, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL UNIQUE
        )
        """
    )
    connection.commit()
    connection.close()


# Initialize the table when the app starts (including when Render runs gunicorn).
initialize_database()


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/")
def index():
    search_query = request.args.get("q", "").strip()
    page = request.args.get("page", "home")
    db = get_db()

    if search_query:
        page = "search"
        search_pattern = f"%{search_query}%"
        videos = db.execute(
            """
            SELECT id, title, description, filename
            FROM videos
            WHERE title LIKE ? OR description LIKE ?
            ORDER BY title
            """,
            (search_pattern, search_pattern),
        ).fetchall()
    else:
        videos = db.execute(
            """
            SELECT id, title, description, filename
            FROM videos
            ORDER BY title
            """
        ).fetchall()

    return render_template(
        "index.html",
        videos=videos,
        search_query=search_query,
        page=page,
    )


@app.route("/video/<path:filename>")
def serve_video(filename):
    # New records store Cloudinary public IDs; older local records still work
    # if their video file exists in the local videos/ directory.
    local_path = os.path.join(VIDEO_FOLDER, filename)
    if os.path.isfile(local_path):
        return send_from_directory(VIDEO_FOLDER, filename)

    # Cloudinary public IDs can include a folder path.
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    if not cloud_name or not os.environ.get("CLOUDINARY_API_KEY") or not os.environ.get("CLOUDINARY_API_SECRET"):
        abort(503, description="Cloudinary is not configured on the server.")

    video_url, _ = cloudinary.utils.cloudinary_url(
        filename,
        resource_type="video",
        secure=True,
        format="mp4",
    )
    return redirect(video_url, code=302)


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

    if not all(
        os.environ.get(name)
        for name in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    ):
        flash("Cloudinary is not configured. Please check Render Environment Variables.")
        return redirect(url_for("index"))

    connection = None
    try:
        connection = sqlite3.connect(DATABASE)
        # A generated public ID avoids collisions between files with the same name.
        public_id = f"video-indexing-system/{uuid.uuid4().hex}"

        result = cloudinary.uploader.upload(
            file.stream,
            resource_type="video",
            public_id=public_id,
            overwrite=False,
            chunk_size=6_000_000,
        )
        cloudinary_public_id = result["public_id"]

        connection.execute(
            """
            INSERT INTO videos (title, description, filename)
            VALUES (?, ?, ?)
            """,
            (title, description, cloudinary_public_id),
        )
        connection.commit()
        flash("Video uploaded successfully!")
    except Exception as exc:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Video upload failed")
        flash("Video upload failed. Check the Render logs and Cloudinary usage limits.")
    finally:
        if connection is not None:
            connection.close()

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
