# import os
# import uuid
# from functools import wraps

# import boto3
# from botocore.exceptions import ClientError
# from dotenv import load_dotenv
# from flask import (
#     Flask,
#     flash,
#     redirect,
#     render_template,
#     request,
#     session,
#     url_for,
# )
# from werkzeug.security import generate_password_hash, check_password_hash

# from database import get_db_connection


# # =========================================================
# # ENVIRONMENT
# # =========================================================

# load_dotenv()


# # =========================================================
# # FLASK APP
# # =========================================================

# app = Flask(__name__)

# app.secret_key = os.environ.get(
#     "FLASK_SECRET_KEY",
#     "change-this-in-production"
# )


# # =========================================================
# # AWS CONFIGURATION
# # =========================================================

# AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# BUCKET_NAME = os.environ.get("S3_BUCKET", "srija-biswas")

# UPLOAD_PREFIX = "uploads/"
# PROCESSED_PREFIX = "processed/"

# s3 = boto3.client(
#     "s3",
#     region_name=AWS_REGION
# )

# ALLOWED_EXTENSIONS = {
#     "jpg",
#     "jpeg",
#     "png"
# }


# # =========================================================
# # HELPER FUNCTIONS
# # =========================================================

# def allowed_file(filename):
#     """
#     Check whether uploaded file extension is supported.
#     """
#     return (
#         "." in filename
#         and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
#     )


# def presigned_url(key, expires=3600):
#     """
#     Generate temporary S3 URL.
#     """
#     if not key:
#         return None

#     try:
#         return s3.generate_presigned_url(
#             "get_object",
#             Params={
#                 "Bucket": BUCKET_NAME,
#                 "Key": key
#             },
#             ExpiresIn=expires,
#         )

#     except ClientError:
#         return None


# def object_exists(key):
#     """
#     Check whether an S3 object exists.
#     """
#     if not key:
#         return False

#     try:
#         s3.head_object(
#             Bucket=BUCKET_NAME,
#             Key=key
#         )

#         return True

#     except ClientError:
#         return False


# def display_name_from_upload_key(key):
#     """
#     Convert stored S3 filename into a cleaner display name.
#     """
#     filename = key.split("/")[-1]

#     stem, ext = os.path.splitext(filename)

#     parts = stem.rsplit("_", 1)

#     if len(parts) == 2 and len(parts[1]) == 8:
#         stem = parts[0]

#     return stem + ext


# def processed_keys(upload_key):
#     """
#     Generate expected resized and B&W object keys.

#     This preserves your CURRENT Lambda naming structure.
#     """
#     filename = upload_key.split("/")[-1]

#     stem, ext = os.path.splitext(filename)

#     ext = ext.lower()

#     if ext == ".jpeg":
#         ext = ".jpg"

#     resized_key = (
#         f"{PROCESSED_PREFIX}"
#         f"{stem}_resized{ext}"
#     )

#     bw_key = (
#         f"{PROCESSED_PREFIX}"
#         f"{stem}_bw{ext}"
#     )

#     return resized_key, bw_key


# def login_required(view_function):
#     """
#     Prevent unauthenticated users from accessing protected pages.
#     """

#     @wraps(view_function)
#     def wrapped_view(*args, **kwargs):

#         if "user_id" not in session:

#             flash(
#                 "Please login to continue.",
#                 "error"
#             )

#             return redirect(
#                 url_for("login")
#             )

#         return view_function(
#             *args,
#             **kwargs
#         )

#     return wrapped_view


# def add_processing_event(
#     image_id,
#     event_type,
#     status,
#     message
# ):
#     """
#     Insert image processing event into RDS.
#     """

#     connection = get_db_connection()

#     try:

#         with connection.cursor() as cursor:

#             cursor.execute(
#                 """
#                 INSERT INTO processing_events
#                 (
#                     image_id,
#                     event_type,
#                     status,
#                     message
#                 )
#                 VALUES (%s, %s, %s, %s)
#                 """,
#                 (
#                     image_id,
#                     event_type,
#                     status,
#                     message
#                 )
#             )

#     finally:
#         connection.close()


# # =========================================================
# # HOME
# # =========================================================

# @app.route("/")
# def index():

#     if "user_id" not in session:
#         return redirect(
#             url_for("login")
#         )

#     return render_template(
#         "index.html"
#     )


# # =========================================================
# # REGISTER
# # =========================================================

# @app.route(
#     "/register",
#     methods=["GET", "POST"]
# )
# def register():

#     if "user_id" in session:
#         return redirect(
#             url_for("dashboard")
#         )

#     if request.method == "POST":

#         full_name = (
#             request.form
#             .get("full_name", "")
#             .strip()
#         )

#         email = (
#             request.form
#             .get("email", "")
#             .strip()
#             .lower()
#         )

#         password = request.form.get(
#             "password",
#             ""
#         )

#         # -----------------------------------------
#         # Validation
#         # -----------------------------------------

#         if (
#             not full_name
#             or not email
#             or not password
#         ):

#             flash(
#                 "All fields are required.",
#                 "error"
#             )

#             return redirect(
#                 url_for("register")
#             )

#         if len(password) < 8:

#             flash(
#                 "Password must contain at least 8 characters.",
#                 "error"
#             )

#             return redirect(
#                 url_for("register")
#             )

#         connection = get_db_connection()

#         try:

#             with connection.cursor() as cursor:

#                 # Check existing account
#                 cursor.execute(
#                     """
#                     SELECT id
#                     FROM users
#                     WHERE email = %s
#                     """,
#                     (email,)
#                 )

#                 existing_user = cursor.fetchone()

#                 if existing_user:

#                     flash(
#                         "An account with this email already exists.",
#                         "error"
#                     )

#                     return redirect(
#                         url_for("register")
#                     )

#                 # Hash password
#                 password_hash = generate_password_hash(
#                     password
#                 )

#                 # Create user
#                 cursor.execute(
#                     """
#                     INSERT INTO users
#                     (
#                         full_name,
#                         email,
#                         password_hash
#                     )
#                     VALUES (%s, %s, %s)
#                     """,
#                     (
#                         full_name,
#                         email,
#                         password_hash
#                     )
#                 )

#             flash(
#                 "Registration successful. Please login.",
#                 "success"
#             )

#             return redirect(
#                 url_for("login")
#             )

#         except Exception as error:

#             print(
#                 "Registration error:",
#                 error
#             )

#             flash(
#                 "Registration failed. Please try again.",
#                 "error"
#             )

#             return redirect(
#                 url_for("register")
#             )

#         finally:
#             connection.close()

#     return render_template(
#         "register.html"
#     )


# # =========================================================
# # LOGIN
# # =========================================================

# @app.route(
#     "/login",
#     methods=["GET", "POST"]
# )
# def login():

#     if "user_id" in session:

#         return redirect(
#             url_for("dashboard")
#         )

#     if request.method == "POST":

#         email = (
#             request.form
#             .get("email", "")
#             .strip()
#             .lower()
#         )

#         password = request.form.get(
#             "password",
#             ""
#         )

#         if not email or not password:

#             flash(
#                 "Email and password are required.",
#                 "error"
#             )

#             return redirect(
#                 url_for("login")
#             )

#         connection = get_db_connection()

#         try:

#             with connection.cursor() as cursor:

#                 cursor.execute(
#                     """
#                     SELECT
#                         id,
#                         full_name,
#                         email,
#                         password_hash,
#                         account_status
#                     FROM users
#                     WHERE email = %s
#                     """,
#                     (email,)
#                 )

#                 user = cursor.fetchone()

#                 # -----------------------------------------
#                 # Invalid credentials
#                 # -----------------------------------------

#                 if not user:

#                     flash(
#                         "Invalid email or password.",
#                         "error"
#                     )

#                     return redirect(
#                         url_for("login")
#                     )

#                 if user["account_status"] != "ACTIVE":

#                     flash(
#                         "Your account is disabled.",
#                         "error"
#                     )

#                     return redirect(
#                         url_for("login")
#                     )

#                 if not check_password_hash(
#                     user["password_hash"],
#                     password
#                 ):

#                     flash(
#                         "Invalid email or password.",
#                         "error"
#                     )

#                     return redirect(
#                         url_for("login")
#                     )

#                 # -----------------------------------------
#                 # Create session
#                 # -----------------------------------------

#                 session.clear()

#                 session["user_id"] = user["id"]
#                 session["user_name"] = user["full_name"]
#                 session["user_email"] = user["email"]

#                 # Update last login
#                 cursor.execute(
#                     """
#                     UPDATE users
#                     SET last_login_at = NOW()
#                     WHERE id = %s
#                     """,
#                     (user["id"],)
#                 )

#             flash(
#                 f"Welcome {user['full_name']}.",
#                 "success"
#             )

#             return redirect(
#                 url_for("dashboard")
#             )

#         except Exception as error:

#             print(
#                 "Login error:",
#                 error
#             )

#             flash(
#                 "Unable to login.",
#                 "error"
#             )

#             return redirect(
#                 url_for("login")
#             )

#         finally:
#             connection.close()

#     return render_template(
#         "login.html"
#     )


# # =========================================================
# # LOGOUT
# # =========================================================

# @app.route("/logout")
# def logout():

#     session.clear()

#     flash(
#         "You have been logged out.",
#         "success"
#     )

#     return redirect(
#         url_for("login")
#     )


# # =========================================================
# # UPLOAD IMAGE
# # =========================================================

# @app.route(
#     "/upload",
#     methods=["POST"]
# )
# @login_required
# def upload():

#     if "image" not in request.files:

#         flash(
#             "Please choose an image.",
#             "error"
#         )

#         return redirect(
#             url_for("index")
#         )

#     file = request.files["image"]

#     if not file or file.filename == "":

#         flash(
#             "Please choose an image.",
#             "error"
#         )

#         return redirect(
#             url_for("index")
#         )

#     if not allowed_file(file.filename):

#         flash(
#             "Only JPG, JPEG and PNG files are supported.",
#             "error"
#         )

#         return redirect(
#             url_for("index")
#         )

#     # =====================================================
#     # PREPARE FILE NAME
#     # =====================================================

#     original_name = os.path.basename(
#         file.filename
#     )

#     stem, ext = os.path.splitext(
#         original_name
#     )

#     safe_stem = "".join(
#         character
#         for character in stem
#         if character.isalnum()
#         or character in ("-", "_")
#     )

#     safe_stem = (
#         safe_stem.strip("_-")
#         or "image"
#     )

#     unique = uuid.uuid4().hex[:8]

#     stored_filename = (
#         f"{safe_stem}_{unique}"
#         f"{ext.lower()}"
#     )

#     upload_key = (
#         f"{UPLOAD_PREFIX}"
#         f"{stored_filename}"
#     )

#     content_type = (
#         file.mimetype
#         or "application/octet-stream"
#     )

#     # =====================================================
#     # GET FILE SIZE
#     # =====================================================

#     try:

#         file.seek(
#             0,
#             os.SEEK_END
#         )

#         original_size = file.tell()

#         file.seek(0)

#     except Exception:

#         original_size = None

#     connection = None
#     image_id = None

#     try:

#         # =================================================
#         # CREATE DATABASE RECORD
#         # =================================================

#         connection = get_db_connection()

#         with connection.cursor() as cursor:

#             cursor.execute(
#                 """
#                 INSERT INTO images
#                 (
#                     user_id,
#                     original_filename,
#                     stored_filename,
#                     original_s3_key,
#                     content_type,
#                     original_size_bytes,
#                     overall_status
#                 )
#                 VALUES
#                 (
#                     %s,
#                     %s,
#                     %s,
#                     %s,
#                     %s,
#                     %s,
#                     'UPLOADING'
#                 )
#                 """,
#                 (
#                     session["user_id"],
#                     original_name,
#                     stored_filename,
#                     upload_key,
#                     content_type,
#                     original_size
#                 )
#             )

#             image_id = cursor.lastrowid

#             cursor.execute(
#                 """
#                 INSERT INTO processing_events
#                 (
#                     image_id,
#                     event_type,
#                     status,
#                     message
#                 )
#                 VALUES
#                 (
#                     %s,
#                     'IMAGE_UPLOAD_STARTED',
#                     'PROCESSING',
#                     'Image upload started'
#                 )
#                 """,
#                 (image_id,)
#             )

#         # =================================================
#         # UPLOAD ORIGINAL IMAGE TO S3
#         # =================================================

#         s3.upload_fileobj(
#             file,
#             BUCKET_NAME,
#             upload_key,
#             ExtraArgs={
#                 "ContentType": content_type
#             },
#         )

#         # =================================================
#         # EXPECTED PROCESSED KEYS
#         # =================================================

#         resized_key, bw_key = processed_keys(
#             upload_key
#         )

#         # =================================================
#         # UPDATE DATABASE AFTER S3 SUCCESS
#         # =================================================

#         with connection.cursor() as cursor:

#             cursor.execute(
#                 """
#                 UPDATE images
#                 SET
#                     resized_s3_key = %s,
#                     bw_s3_key = %s,
#                     overall_status = 'UPLOADED',
#                     uploaded_at = NOW()
#                 WHERE id = %s
#                 """,
#                 (
#                     resized_key,
#                     bw_key,
#                     image_id
#                 )
#             )

#             cursor.execute(
#                 """
#                 INSERT INTO processing_events
#                 (
#                     image_id,
#                     event_type,
#                     status,
#                     message
#                 )
#                 VALUES
#                 (
#                     %s,
#                     'S3_UPLOAD_COMPLETED',
#                     'SUCCESS',
#                     'Original image uploaded to Amazon S3'
#                 )
#                 """,
#                 (image_id,)
#             )

#         flash(
#             "Image uploaded successfully. AWS is processing "
#             "the resized and black-and-white versions.",
#             "success"
#         )

#         return redirect(
#             url_for("dashboard")
#         )

#     except Exception as error:

#         print(
#             "Upload error:",
#             error
#         )

#         # ---------------------------------------------
#         # Record failed upload
#         # ---------------------------------------------

#         if connection and image_id:

#             try:

#                 with connection.cursor() as cursor:

#                     cursor.execute(
#                         """
#                         UPDATE images
#                         SET overall_status = 'FAILED'
#                         WHERE id = %s
#                         """,
#                         (image_id,)
#                     )

#                     cursor.execute(
#                         """
#                         INSERT INTO processing_events
#                         (
#                             image_id,
#                             event_type,
#                             status,
#                             message
#                         )
#                         VALUES
#                         (
#                             %s,
#                             'IMAGE_UPLOAD_FAILED',
#                             'FAILED',
#                             %s
#                         )
#                         """,
#                         (
#                             image_id,
#                             str(error)[:1000]
#                         )
#                     )

#             except Exception as db_error:

#                 print(
#                     "Failed to update upload error:",
#                     db_error
#                 )

#         flash(
#             "Image upload failed.",
#             "error"
#         )

#         return redirect(
#             url_for("index")
#         )

#     finally:

#         if connection:
#             connection.close()


# # =========================================================
# # DASHBOARD
# # =========================================================

# @app.route("/dashboard")
# @login_required
# def dashboard():

#     connection = get_db_connection()

#     items = []

#     try:

#         with connection.cursor() as cursor:

#             # Only current user's images
#             cursor.execute(
#                 """
#                 SELECT
#                     id,
#                     original_filename,
#                     stored_filename,
#                     original_s3_key,
#                     resized_s3_key,
#                     bw_s3_key,
#                     content_type,
#                     original_width,
#                     original_height,
#                     original_size_bytes,
#                     resized_width,
#                     resized_height,
#                     resized_size_bytes,
#                     bw_width,
#                     bw_height,
#                     bw_size_bytes,
#                     overall_status,
#                     uploaded_at,
#                     processing_started_at,
#                     processing_completed_at,
#                     created_at
#                 FROM images
#                 WHERE user_id = %s
#                 ORDER BY created_at DESC
#                 """,
#                 (
#                     session["user_id"],
#                 )
#             )

#             images = cursor.fetchall()

#             for image in images:

#                 upload_key = image[
#                     "original_s3_key"
#                 ]

#                 resized_key = image[
#                     "resized_s3_key"
#                 ]

#                 bw_key = image[
#                     "bw_s3_key"
#                 ]

#                 # Fallback for old records
#                 if (
#                     not resized_key
#                     or not bw_key
#                 ):

#                     resized_key, bw_key = processed_keys(
#                         upload_key
#                     )

#                 resized_ready = object_exists(
#                     resized_key
#                 )

#                 bw_ready = object_exists(
#                     bw_key
#                 )

#                 # -----------------------------------------
#                 # Check whether Lambda has completed
#                 # -----------------------------------------

#                 if (
#                     resized_ready
#                     and bw_ready
#                     and image["overall_status"] != "COMPLETED"
#                 ):

#                     cursor.execute(
#                         """
#                         UPDATE images
#                         SET
#                             overall_status = 'COMPLETED',
#                             processing_completed_at = NOW(),
#                             resized_s3_key = %s,
#                             bw_s3_key = %s
#                         WHERE id = %s
#                         """,
#                         (
#                             resized_key,
#                             bw_key,
#                             image["id"]
#                         )
#                     )

#                     cursor.execute(
#                         """
#                         INSERT INTO processing_events
#                         (
#                             image_id,
#                             event_type,
#                             status,
#                             message
#                         )
#                         VALUES
#                         (
#                             %s,
#                             'PROCESS_COMPLETED',
#                             'SUCCESS',
#                             'Resized and black-and-white images are available'
#                         )
#                         """,
#                         (
#                             image["id"],
#                         )
#                     )

#                     image["overall_status"] = (
#                         "COMPLETED"
#                     )

#                 elif (
#                     image["overall_status"]
#                     in (
#                         "UPLOADED",
#                         "QUEUED"
#                     )
#                 ):

#                     image["overall_status"] = (
#                         "PROCESSING"
#                     )

#                 items.append(
#                     {
#                         "id": image["id"],

#                         "upload_key": upload_key,

#                         "name": (
#                             image["original_filename"]
#                             or
#                             display_name_from_upload_key(
#                                 upload_key
#                             )
#                         ),

#                         "uploaded_at": (
#                             image["uploaded_at"]
#                             or image["created_at"]
#                         ),

#                         "original_url": (
#                             presigned_url(
#                                 upload_key
#                             )
#                         ),

#                         "resized_key": resized_key,

#                         "resized_url": (
#                             presigned_url(
#                                 resized_key
#                             )
#                             if resized_ready
#                             else None
#                         ),

#                         "bw_key": bw_key,

#                         "bw_url": (
#                             presigned_url(
#                                 bw_key
#                             )
#                             if bw_ready
#                             else None
#                         ),

#                         "status": (
#                             image[
#                                 "overall_status"
#                             ]
#                         ),

#                         "original_size": (
#                             image[
#                                 "original_size_bytes"
#                             ]
#                         ),
#                     }
#                 )

#     except Exception as error:

#         print(
#             "Dashboard error:",
#             error
#         )

#         flash(
#             "Unable to load dashboard.",
#             "error"
#         )

#     finally:
#         connection.close()

#     return render_template(
#         "dashboard.html",
#         items=items
#     )


# # =========================================================
# # IMAGE DETAILS
# # =========================================================

# @app.route("/image/<int:image_id>")
# @login_required
# def image_details(image_id):

#     connection = get_db_connection()

#     try:

#         with connection.cursor() as cursor:

#             # Verify current user owns image
#             cursor.execute(
#                 """
#                 SELECT *
#                 FROM images
#                 WHERE id = %s
#                   AND user_id = %s
#                 """,
#                 (
#                     image_id,
#                     session["user_id"]
#                 )
#             )

#             image = cursor.fetchone()

#             if not image:

#                 flash(
#                     "Image not found.",
#                     "error"
#                 )

#                 return redirect(
#                     url_for("dashboard")
#                 )

#             cursor.execute(
#                 """
#                 SELECT
#                     id,
#                     event_type,
#                     status,
#                     message,
#                     event_time
#                 FROM processing_events
#                 WHERE image_id = %s
#                 ORDER BY event_time ASC, id ASC
#                 """,
#                 (
#                     image_id,
#                 )
#             )

#             events = cursor.fetchall()

#             image["original_url"] = (
#                 presigned_url(
#                     image["original_s3_key"]
#                 )
#             )

#             if (
#                 image["resized_s3_key"]
#                 and object_exists(
#                     image["resized_s3_key"]
#                 )
#             ):

#                 image["resized_url"] = (
#                     presigned_url(
#                         image[
#                             "resized_s3_key"
#                         ]
#                     )
#                 )

#             else:

#                 image["resized_url"] = None

#             if (
#                 image["bw_s3_key"]
#                 and object_exists(
#                     image["bw_s3_key"]
#                 )
#             ):

#                 image["bw_url"] = (
#                     presigned_url(
#                         image[
#                             "bw_s3_key"
#                         ]
#                     )
#                 )

#             else:

#                 image["bw_url"] = None

#     finally:
#         connection.close()

#     return render_template(
#         "image_details.html",
#         image=image,
#         events=events
#     )


# # =========================================================
# # DELETE IMAGE
# # =========================================================

# @app.route(
#     "/delete",
#     methods=["POST"]
# )
# @login_required
# def delete():

#     image_id = request.form.get(
#         "image_id"
#     )

#     # Compatibility with your old dashboard form
#     upload_key_from_form = request.form.get(
#         "upload_key",
#         ""
#     )

#     connection = get_db_connection()

#     try:

#         with connection.cursor() as cursor:

#             image = None

#             # -----------------------------------------
#             # New method: image_id
#             # -----------------------------------------

#             if image_id:

#                 cursor.execute(
#                     """
#                     SELECT
#                         id,
#                         original_s3_key,
#                         resized_s3_key,
#                         bw_s3_key
#                     FROM images
#                     WHERE id = %s
#                       AND user_id = %s
#                     """,
#                     (
#                         image_id,
#                         session["user_id"]
#                     )
#                 )

#                 image = cursor.fetchone()

#             # -----------------------------------------
#             # Compatibility with old dashboard
#             # -----------------------------------------

#             elif upload_key_from_form:

#                 cursor.execute(
#                     """
#                     SELECT
#                         id,
#                         original_s3_key,
#                         resized_s3_key,
#                         bw_s3_key
#                     FROM images
#                     WHERE original_s3_key = %s
#                       AND user_id = %s
#                     """,
#                     (
#                         upload_key_from_form,
#                         session["user_id"]
#                     )
#                 )

#                 image = cursor.fetchone()

#             if not image:

#                 flash(
#                     "Image not found or access denied.",
#                     "error"
#                 )

#                 return redirect(
#                     url_for("dashboard")
#                 )

#             upload_key = image[
#                 "original_s3_key"
#             ]

#             resized_key = image[
#                 "resized_s3_key"
#             ]

#             bw_key = image[
#                 "bw_s3_key"
#             ]

#             if not resized_key or not bw_key:

#                 resized_key, bw_key = (
#                     processed_keys(
#                         upload_key
#                     )
#                 )

#             # -----------------------------------------
#             # Delete S3 files
#             # -----------------------------------------

#             for key in (
#                 upload_key,
#                 resized_key,
#                 bw_key
#             ):

#                 if not key:
#                     continue

#                 try:

#                     s3.delete_object(
#                         Bucket=BUCKET_NAME,
#                         Key=key
#                     )

#                 except ClientError as error:

#                     print(
#                         f"S3 delete failed for {key}:",
#                         error
#                     )

#             # -----------------------------------------
#             # Delete database record
#             # processing_events and processing_jobs
#             # automatically delete because of CASCADE
#             # -----------------------------------------

#             cursor.execute(
#                 """
#                 DELETE FROM images
#                 WHERE id = %s
#                   AND user_id = %s
#                 """,
#                 (
#                     image["id"],
#                     session["user_id"]
#                 )
#             )

#         flash(
#             "Original and processed images deleted successfully.",
#             "success"
#         )

#     except Exception as error:

#         print(
#             "Delete error:",
#             error
#         )

#         flash(
#             "Unable to delete image.",
#             "error"
#         )

#     finally:
#         connection.close()

#     return redirect(
#         url_for("dashboard")
#     )


# # =========================================================
# # RUN APPLICATION
# # =========================================================

# if __name__ == "__main__":

#     app.run(
#         debug=True,
#         host="127.0.0.1",
#         port=5000
#     )
import os
import uuid
from functools import wraps

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from database import get_db_connection


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-in-production"
)


# =========================================================
# AWS CONFIGURATION
# =========================================================

AWS_REGION = os.environ.get(
    "AWS_REGION",
    "us-east-1"
)

BUCKET_NAME = os.environ.get(
    "S3_BUCKET",
    "srija-biswas"
)

UPLOAD_PREFIX = "uploads/"
PROCESSED_PREFIX = "processed/"


s3 = boto3.client(
    "s3",
    region_name=AWS_REGION
)


# =========================================================
# ALLOWED FILE TYPES
# =========================================================

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png"
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def allowed_file(filename):
    """
    Check whether the uploaded file has a supported extension.
    """

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_EXTENSIONS
    )


def presigned_url(key, expires=3600):
    """
    Generate a temporary private S3 URL.
    """

    if not key:
        return None

    try:

        return s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": key
            },
            ExpiresIn=expires,
        )

    except ClientError as error:

        print(
            "Presigned URL error:",
            error
        )

        return None


def object_exists(key):
    """
    Check whether an S3 object exists.
    """

    if not key:
        return False

    try:

        s3.head_object(
            Bucket=BUCKET_NAME,
            Key=key
        )

        return True

    except ClientError:

        return False


def display_name_from_upload_key(key):
    """
    Convert stored S3 filename into a cleaner display name.
    """

    filename = key.split("/")[-1]

    stem, ext = os.path.splitext(
        filename
    )

    parts = stem.rsplit(
        "_",
        1
    )

    if (
        len(parts) == 2
        and len(parts[1]) == 8
    ):

        stem = parts[0]

    return stem + ext


def processed_keys(upload_key):
    """
    Generate the expected processed S3 keys.

    This preserves the existing Lambda naming convention.
    """

    filename = upload_key.split("/")[-1]

    stem, ext = os.path.splitext(
        filename
    )

    ext = ext.lower()

    if ext == ".jpeg":
        ext = ".jpg"

    resized_key = (
        f"{PROCESSED_PREFIX}"
        f"{stem}_resized{ext}"
    )

    bw_key = (
        f"{PROCESSED_PREFIX}"
        f"{stem}_bw{ext}"
    )

    return (
        resized_key,
        bw_key
    )


def login_required(view_function):
    """
    Protect routes that require an authenticated user.
    """

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login to continue.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        return view_function(
            *args,
            **kwargs
        )

    return wrapped_view


# =========================================================
# DATABASE EVENT HELPER
# =========================================================

def add_processing_event(
    connection,
    image_id,
    event_type,
    status,
    message
):
    """
    Insert an event into processing_events.

    The connection is passed into the function so that
    the event can participate in the same transaction.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            INSERT INTO processing_events
            (
                image_id,
                event_type,
                status,
                message
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                image_id,
                event_type,
                status,
                message
            )
        )


# =========================================================
# HOME / UPLOAD PAGE
# =========================================================

@app.route("/")
def index():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if "user_id" in session:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        full_name = (
            request.form
            .get(
                "full_name",
                ""
            )
            .strip()
        )

        email = (
            request.form
            .get(
                "email",
                ""
            )
            .strip()
            .lower()
        )

        password = request.form.get(
            "password",
            ""
        )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if (
            not full_name
            or not email
            or not password
        ):

            flash(
                "All fields are required.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        connection = None

        try:

            connection = get_db_connection()

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE email = %s
                    """,
                    (email,)
                )

                existing_user = cursor.fetchone()

                if existing_user:

                    flash(
                        "An account with this email already exists.",
                        "error"
                    )

                    return redirect(
                        url_for("register")
                    )

                password_hash = generate_password_hash(
                    password
                )

                cursor.execute(
                    """
                    INSERT INTO users
                    (
                        full_name,
                        email,
                        password_hash,
                        account_status
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        'ACTIVE'
                    )
                    """,
                    (
                        full_name,
                        email,
                        password_hash
                    )
                )

            connection.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Exception as error:

            if connection:

                try:
                    connection.rollback()
                except Exception:
                    pass

            print(
                "Registration error:",
                error
            )

            flash(
                "Registration failed. Please try again.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        finally:

            if connection:
                connection.close()

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if "user_id" in session:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        email = (
            request.form
            .get(
                "email",
                ""
            )
            .strip()
            .lower()
        )

        password = request.form.get(
            "password",
            ""
        )

        if (
            not email
            or not password
        ):

            flash(
                "Email and password are required.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        connection = None

        try:

            connection = get_db_connection()

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT
                        id,
                        full_name,
                        email,
                        password_hash,
                        account_status
                    FROM users
                    WHERE email = %s
                    """,
                    (email,)
                )

                user = cursor.fetchone()

                if not user:

                    flash(
                        "Invalid email or password.",
                        "error"
                    )

                    return redirect(
                        url_for("login")
                    )

                if user["account_status"] != "ACTIVE":

                    flash(
                        "Your account is disabled.",
                        "error"
                    )

                    return redirect(
                        url_for("login")
                    )

                if not check_password_hash(
                    user["password_hash"],
                    password
                ):

                    flash(
                        "Invalid email or password.",
                        "error"
                    )

                    return redirect(
                        url_for("login")
                    )

                session.clear()

                session["user_id"] = user["id"]
                session["user_name"] = user["full_name"]
                session["user_email"] = user["email"]

                cursor.execute(
                    """
                    UPDATE users
                    SET last_login_at = NOW()
                    WHERE id = %s
                    """,
                    (user["id"],)
                )

            connection.commit()

            flash(
                f"Welcome {user['full_name']}.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        except Exception as error:

            if connection:

                try:
                    connection.rollback()
                except Exception:
                    pass

            print(
                "Login error:",
                error
            )

            flash(
                "Unable to login.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        finally:

            if connection:
                connection.close()

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# UPLOAD IMAGE
# =========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
@login_required
def upload():

    # -----------------------------------------------------
    # CHECK FILE
    # -----------------------------------------------------

    if "image" not in request.files:

        flash(
            "Please choose an image.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    file = request.files["image"]

    if (
        not file
        or file.filename == ""
    ):

        flash(
            "Please choose an image.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    if not allowed_file(
        file.filename
    ):

        flash(
            "Only JPG, JPEG and PNG files are supported.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    # -----------------------------------------------------
    # FILE NAME
    # -----------------------------------------------------

    original_name = os.path.basename(
        file.filename
    )

    stem, ext = os.path.splitext(
        original_name
    )

    safe_stem = "".join(
        character
        for character in stem
        if character.isalnum()
        or character in (
            "-",
            "_"
        )
    )

    safe_stem = (
        safe_stem.strip("_-")
        or "image"
    )

    unique = uuid.uuid4().hex[:8]

    stored_filename = (
        f"{safe_stem}_{unique}"
        f"{ext.lower()}"
    )

    upload_key = (
        f"{UPLOAD_PREFIX}"
        f"{stored_filename}"
    )

    content_type = (
        file.mimetype
        or "application/octet-stream"
    )

    # -----------------------------------------------------
    # FILE SIZE
    # -----------------------------------------------------

    try:

        file.seek(
            0,
            os.SEEK_END
        )

        original_size = file.tell()

        file.seek(0)

    except Exception:

        original_size = None

    connection = None
    image_id = None

    try:

        # =================================================
        # DATABASE CONNECTION
        # =================================================

        connection = get_db_connection()

        # =================================================
        # CREATE IMAGE RECORD
        # =================================================

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO images
                (
                    user_id,
                    original_filename,
                    stored_filename,
                    original_s3_key,
                    content_type,
                    original_size_bytes,
                    overall_status
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'UPLOADING'
                )
                """,
                (
                    session["user_id"],
                    original_name,
                    stored_filename,
                    upload_key,
                    content_type,
                    original_size
                )
            )

            image_id = cursor.lastrowid

        # -------------------------------------------------
        # EVENT: UPLOAD STARTED
        # -------------------------------------------------

        add_processing_event(
            connection,
            image_id,
            "IMAGE_UPLOAD_STARTED",
            "PROCESSING",
            "Image upload started from Flask application"
        )

        # Commit initial database record
        connection.commit()

        # =================================================
        # UPLOAD IMAGE TO S3
        # =================================================

        s3.upload_fileobj(
            file,
            BUCKET_NAME,
            upload_key,
            ExtraArgs={
                "ContentType": content_type
            }
        )

        # =================================================
        # EXPECTED PROCESSED KEYS
        # =================================================

        resized_key, bw_key = processed_keys(
            upload_key
        )

        # =================================================
        # UPDATE IMAGE AFTER S3 UPLOAD
        # =================================================

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE images
                SET
                    resized_s3_key = %s,
                    bw_s3_key = %s,
                    overall_status = 'UPLOADED',
                    uploaded_at = NOW()
                WHERE id = %s
                """,
                (
                    resized_key,
                    bw_key,
                    image_id
                )
            )

        # -------------------------------------------------
        # EVENT: S3 UPLOAD COMPLETED
        # -------------------------------------------------

        add_processing_event(
            connection,
            image_id,
            "S3_UPLOAD_COMPLETED",
            "SUCCESS",
            "Original image successfully uploaded to Amazon S3"
        )

        # -------------------------------------------------
        # EVENT: PROCESSING QUEUED
        # -------------------------------------------------

        add_processing_event(
            connection,
            image_id,
            "PROCESSING_QUEUED",
            "QUEUED",
            "Image is waiting for S3 to SQS to Lambda processing"
        )

        # =================================================
        # CREATE PROCESSING JOB
        # =================================================

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO processing_jobs
                (
                    image_id,
                    status
                )
                VALUES
                (
                    %s,
                    'QUEUED'
                )
                """,
                (
                    image_id,
                )
            )

        connection.commit()

        # =================================================
        # USER MESSAGE
        # =================================================

        flash(
            "Image uploaded successfully. AWS is now processing "
            "the resized and black-and-white versions.",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    except Exception as error:

        print(
            "Upload error:",
            error
        )

        # =================================================
        # DATABASE FAILURE HANDLING
        # =================================================

        if connection and image_id:

            try:

                connection.rollback()

                with connection.cursor() as cursor:

                    cursor.execute(
                        """
                        UPDATE images
                        SET
                            overall_status = 'FAILED'
                        WHERE id = %s
                        """,
                        (image_id,)
                    )

                add_processing_event(
                    connection,
                    image_id,
                    "IMAGE_UPLOAD_FAILED",
                    "FAILED",
                    str(error)[:1000]
                )

                connection.commit()

            except Exception as db_error:

                print(
                    "Failed to record upload failure:",
                    db_error
                )

        flash(
            "Image upload failed.",
            "error"
        )

        return redirect(
            url_for("index")
        )

    finally:

        if connection:
            connection.close()


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    connection = None
    items = []

    try:

        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    i.id,
                    i.original_filename,
                    i.stored_filename,
                    i.original_s3_key,
                    i.resized_s3_key,
                    i.bw_s3_key,
                    i.content_type,
                    i.original_width,
                    i.original_height,
                    i.original_size_bytes,
                    i.resized_width,
                    i.resized_height,
                    i.resized_size_bytes,
                    i.bw_width,
                    i.bw_height,
                    i.bw_size_bytes,
                    i.overall_status,
                    i.uploaded_at,
                    i.processing_started_at,
                    i.processing_completed_at,
                    i.created_at,

                    pj.id AS job_id,
                    pj.status AS job_status,
                    pj.lambda_request_id,
                    pj.sqs_message_id,
                    pj.started_at AS job_started_at,
                    pj.completed_at AS job_completed_at,
                    pj.processing_duration_ms,
                    pj.error_message

                FROM images i

                LEFT JOIN processing_jobs pj
                    ON pj.image_id = i.id

                WHERE i.user_id = %s

                ORDER BY i.created_at DESC
                """,
                (
                    session["user_id"],
                )
            )

            images = cursor.fetchall()

            for image in images:

                upload_key = image[
                    "original_s3_key"
                ]

                resized_key = image[
                    "resized_s3_key"
                ]

                bw_key = image[
                    "bw_s3_key"
                ]

                # -------------------------------------------------
                # FALLBACK FOR OLD RECORDS
                # -------------------------------------------------

                if (
                    not resized_key
                    or not bw_key
                ):

                    resized_key, bw_key = processed_keys(
                        upload_key
                    )

                resized_ready = object_exists(
                    resized_key
                )

                bw_ready = object_exists(
                    bw_key
                )

                # -------------------------------------------------
                # DO NOT CHANGE DATABASE STATUS HERE
                #
                # Lambda is responsible for updating processing
                # status. Dashboard only reads current state.
                # -------------------------------------------------

                items.append(
                    {
                        "id": image["id"],

                        "job_id": image["job_id"],

                        "upload_key": upload_key,

                        "name": (
                            image["original_filename"]
                            or
                            display_name_from_upload_key(
                                upload_key
                            )
                        ),

                        "stored_filename": image[
                            "stored_filename"
                        ],

                        "uploaded_at": (
                            image["uploaded_at"]
                            or image["created_at"]
                        ),

                        "original_url": (
                            presigned_url(
                                upload_key
                            )
                        ),

                        "resized_key": resized_key,

                        "resized_url": (
                            presigned_url(
                                resized_key
                            )
                            if resized_ready
                            else None
                        ),

                        "bw_key": bw_key,

                        "bw_url": (
                            presigned_url(
                                bw_key
                            )
                            if bw_ready
                            else None
                        ),

                        "status": image[
                            "overall_status"
                        ],

                        "job_status": image[
                            "job_status"
                        ],

                        "original_size": image[
                            "original_size_bytes"
                        ],

                        "original_width": image[
                            "original_width"
                        ],

                        "original_height": image[
                            "original_height"
                        ],

                        "resized_width": image[
                            "resized_width"
                        ],

                        "resized_height": image[
                            "resized_height"
                        ],

                        "resized_size": image[
                            "resized_size_bytes"
                        ],

                        "bw_width": image[
                            "bw_width"
                        ],

                        "bw_height": image[
                            "bw_height"
                        ],

                        "bw_size": image[
                            "bw_size_bytes"
                        ],

                        "processing_started_at": image[
                            "processing_started_at"
                        ],

                        "processing_completed_at": image[
                            "processing_completed_at"
                        ],

                        "job_started_at": image[
                            "job_started_at"
                        ],

                        "job_completed_at": image[
                            "job_completed_at"
                        ],

                        "processing_duration_ms": image[
                            "processing_duration_ms"
                        ],

                        "error_message": image[
                            "error_message"
                        ],
                    }
                )

    except Exception as error:

        print(
            "Dashboard error:",
            error
        )

        flash(
            "Unable to load dashboard.",
            "error"
        )

    finally:

        if connection:
            connection.close()

    return render_template(
        "dashboard.html",
        items=items
    )


# =========================================================
# IMAGE DETAILS
# =========================================================

@app.route(
    "/image/<int:image_id>"
)
@login_required
def image_details(image_id):

    connection = None

    try:

        connection = get_db_connection()

        with connection.cursor() as cursor:

            # =================================================
            # IMAGE
            # =================================================

            cursor.execute(
                """
                SELECT
                    *
                FROM images
                WHERE id = %s
                  AND user_id = %s
                """,
                (
                    image_id,
                    session["user_id"]
                )
            )

            image = cursor.fetchone()

            if not image:

                flash(
                    "Image not found.",
                    "error"
                )

                return redirect(
                    url_for("dashboard")
                )

            # =================================================
            # PROCESSING JOB
            # =================================================

            cursor.execute(
                """
                SELECT
                    id,
                    image_id,
                    lambda_request_id,
                    sqs_message_id,
                    status,
                    started_at,
                    completed_at,
                    processing_duration_ms,
                    error_message,
                    created_at
                FROM processing_jobs
                WHERE image_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    image_id,
                )
            )

            job = cursor.fetchone()

            # =================================================
            # PROCESSING EVENTS
            # =================================================

            cursor.execute(
                """
                SELECT
                    id,
                    event_type,
                    status,
                    message,
                    event_time
                FROM processing_events
                WHERE image_id = %s
                ORDER BY event_time ASC, id ASC
                """,
                (
                    image_id,
                )
            )

            events = cursor.fetchall()

            # =================================================
            # S3 URLS
            # =================================================

            image["original_url"] = presigned_url(
                image["original_s3_key"]
            )

            image["resized_url"] = None

            image["bw_url"] = None

            if (
                image["resized_s3_key"]
                and object_exists(
                    image["resized_s3_key"]
                )
            ):

                image["resized_url"] = presigned_url(
                    image["resized_s3_key"]
                )

            if (
                image["bw_s3_key"]
                and object_exists(
                    image["bw_s3_key"]
                )
            ):

                image["bw_url"] = presigned_url(
                    image["bw_s3_key"]
                )

    except Exception as error:

        print(
            "Image details error:",
            error
        )

        flash(
            "Unable to load image details.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )

    finally:

        if connection:
            connection.close()

    return render_template(
        "image_details.html",
        image=image,
        job=job,
        events=events
    )


# =========================================================
# DELETE IMAGE
# =========================================================

@app.route(
    "/delete",
    methods=["POST"]
)
@login_required
def delete():

    image_id = request.form.get(
        "image_id"
    )

    upload_key_from_form = request.form.get(
        "upload_key",
        ""
    )

    connection = None

    try:

        connection = get_db_connection()

        with connection.cursor() as cursor:

            image = None

            # =================================================
            # FIND BY IMAGE ID
            # =================================================

            if image_id:

                cursor.execute(
                    """
                    SELECT
                        id,
                        original_s3_key,
                        resized_s3_key,
                        bw_s3_key
                    FROM images
                    WHERE id = %s
                      AND user_id = %s
                    """,
                    (
                        image_id,
                        session["user_id"]
                    )
                )

                image = cursor.fetchone()

            # =================================================
            # OLD DASHBOARD COMPATIBILITY
            # =================================================

            elif upload_key_from_form:

                cursor.execute(
                    """
                    SELECT
                        id,
                        original_s3_key,
                        resized_s3_key,
                        bw_s3_key
                    FROM images
                    WHERE original_s3_key = %s
                      AND user_id = %s
                    """,
                    (
                        upload_key_from_form,
                        session["user_id"]
                    )
                )

                image = cursor.fetchone()

            if not image:

                flash(
                    "Image not found or access denied.",
                    "error"
                )

                return redirect(
                    url_for("dashboard")
                )

            upload_key = image[
                "original_s3_key"
            ]

            resized_key = image[
                "resized_s3_key"
            ]

            bw_key = image[
                "bw_s3_key"
            ]

            if (
                not resized_key
                or not bw_key
            ):

                resized_key, bw_key = processed_keys(
                    upload_key
                )

            # =================================================
            # DELETE S3 OBJECTS
            # =================================================

            for key in (
                upload_key,
                resized_key,
                bw_key
            ):

                if not key:
                    continue

                try:

                    s3.delete_object(
                        Bucket=BUCKET_NAME,
                        Key=key
                    )

                except ClientError as error:

                    print(
                        f"S3 delete failed for {key}:",
                        error
                    )

            # =================================================
            # DELETE DATABASE RECORD
            #
            # Foreign-key CASCADE should remove:
            # processing_jobs
            # processing_events
            # =================================================

            cursor.execute(
                """
                DELETE FROM images
                WHERE id = %s
                  AND user_id = %s
                """,
                (
                    image["id"],
                    session["user_id"]
                )
            )

        connection.commit()

        flash(
            "Original and processed images deleted successfully.",
            "success"
        )

    except Exception as error:

        if connection:

            try:
                connection.rollback()
            except Exception:
                pass

        print(
            "Delete error:",
            error
        )

        flash(
            "Unable to delete image.",
            "error"
        )

    finally:

        if connection:
            connection.close()

    return redirect(
        url_for("dashboard")
    )


# =========================================================
# APPLICATION START
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )