import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-in-production")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET_NAME = os.environ.get("S3_BUCKET", "srija-biswas")
UPLOAD_PREFIX = "uploads/"
PROCESSED_PREFIX = "processed/"

s3 = boto3.client("s3", region_name=AWS_REGION)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def presigned_url(key, expires=3600):
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=expires,
        )
    except ClientError:
        return None

def object_exists(key):
    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except ClientError:
        return False

def display_name_from_upload_key(key):
    filename = key.split("/")[-1]
    stem, ext = os.path.splitext(filename)
    # Remove UUID suffix from UI name when present.
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and len(parts[1]) == 8:
        stem = parts[0]
    return stem + ext

def processed_keys(upload_key):
    filename = upload_key.split("/")[-1]
    stem, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    return (
        f"{PROCESSED_PREFIX}{stem}_resized{ext}",
        f"{PROCESSED_PREFIX}{stem}_bw{ext}",
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        flash("Please choose an image.")
        return redirect(url_for("index"))

    file = request.files["image"]

    if not file or file.filename == "":
        flash("Please choose an image.")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Only JPG, JPEG and PNG files are supported.")
        return redirect(url_for("index"))

    original_name = os.path.basename(file.filename)
    stem, ext = os.path.splitext(original_name)
    safe_stem = "".join(c for c in stem if c.isalnum() or c in ("-", "_")).strip("_-") or "image"
    unique = uuid.uuid4().hex[:8]
    key = f"{UPLOAD_PREFIX}{safe_stem}_{unique}{ext.lower()}"

    content_type = file.mimetype or "application/octet-stream"

    s3.upload_fileobj(
        file,
        BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )

    flash("Image uploaded. AWS is processing the resized and black-and-white versions.")
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=UPLOAD_PREFIX,
    )

    items = []

    for obj in sorted(response.get("Contents", []), key=lambda x: x["LastModified"], reverse=True):
        key = obj["Key"]
        if key.endswith("/"):
            continue

        resized_key, bw_key = processed_keys(key)
        resized_ready = object_exists(resized_key)
        bw_ready = object_exists(bw_key)

        items.append(
            {
                "upload_key": key,
                "name": display_name_from_upload_key(key),
                "uploaded_at": obj["LastModified"],
                "original_url": presigned_url(key),
                "resized_key": resized_key,
                "resized_url": presigned_url(resized_key) if resized_ready else None,
                "bw_key": bw_key,
                "bw_url": presigned_url(bw_key) if bw_ready else None,
                "status": "Completed" if resized_ready and bw_ready else "Processing",
            }
        )

    return render_template("dashboard.html", items=items)

@app.route("/delete", methods=["POST"])
def delete():
    upload_key = request.form.get("upload_key", "")

    if not upload_key.startswith(UPLOAD_PREFIX):
        flash("Invalid object.")
        return redirect(url_for("dashboard"))

    resized_key, bw_key = processed_keys(upload_key)

    for key in (upload_key, resized_key, bw_key):
        try:
            s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        except ClientError:
            pass

    flash("Original and processed images deleted.")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
