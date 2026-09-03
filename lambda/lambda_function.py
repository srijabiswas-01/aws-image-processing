import json
import boto3
import os
import urllib.parse
import time
from PIL import Image, ImageOps
import pymysql


# =========================================================
# AWS CLIENTS
# =========================================================

s3 = boto3.client("s3")
sns = boto3.client("sns")


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME", "image_processing")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))

MAX_SIZE = (800, 800)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10
    )


# =========================================================
# PRESIGNED URL
# =========================================================

def make_presigned_url(bucket, key):
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": key
        },
        ExpiresIn=3600
    )


# =========================================================
# IMAGE SAVE
# =========================================================

def save_image(img, output_path, extension):

    if extension in [".jpg", ".jpeg"]:

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        img.save(
            output_path,
            "JPEG",
            quality=85,
            optimize=True
        )

    else:

        img.save(
            output_path,
            "PNG",
            optimize=True
        )


# =========================================================
# FIND IMAGE RECORD
# =========================================================

def find_image_record(connection, original_s3_key):

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT
                id,
                user_id,
                original_filename,
                stored_filename,
                original_s3_key,
                resized_s3_key,
                bw_s3_key,
                overall_status
            FROM images
            WHERE original_s3_key = %s
            LIMIT 1
            """,
            (original_s3_key,)
        )

        return cursor.fetchone()


# =========================================================
# ADD PROCESSING EVENT
# =========================================================

def add_processing_event(
    connection,
    image_id,
    event_type,
    status,
    message
):

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
# UPDATE IMAGE STATUS
# =========================================================

def update_image_status(
    connection,
    image_id,
    status
):

    with connection.cursor() as cursor:

        if status == "PROCESSING":

            cursor.execute(
                """
                UPDATE images
                SET
                    overall_status = 'PROCESSING',
                    processing_started_at = NOW()
                WHERE id = %s
                """,
                (image_id,)
            )

        elif status == "COMPLETED":

            cursor.execute(
                """
                UPDATE images
                SET
                    overall_status = 'COMPLETED',
                    processing_completed_at = NOW()
                WHERE id = %s
                """,
                (image_id,)
            )

        elif status == "FAILED":

            cursor.execute(
                """
                UPDATE images
                SET
                    overall_status = 'FAILED'
                WHERE id = %s
                """,
                (image_id,)
            )


# =========================================================
# PROCESSING JOB
# =========================================================

def create_processing_job(
    connection,
    image_id,
    lambda_request_id,
    sqs_message_id
):

    with connection.cursor() as cursor:

        cursor.execute(
            """
            INSERT INTO processing_jobs
            (
                image_id,
                lambda_request_id,
                sqs_message_id,
                status,
                started_at
            )
            VALUES
            (
                %s,
                %s,
                %s,
                'PROCESSING',
                NOW()
            )
            """,
            (
                image_id,
                lambda_request_id,
                sqs_message_id
            )
        )

        return cursor.lastrowid


# =========================================================
# COMPLETE PROCESSING JOB
# =========================================================

def complete_processing_job(
    connection,
    job_id,
    duration_ms
):

    with connection.cursor() as cursor:

        cursor.execute(
            """
            UPDATE processing_jobs
            SET
                status = 'COMPLETED',
                completed_at = NOW(),
                processing_duration_ms = %s
            WHERE id = %s
            """,
            (
                duration_ms,
                job_id
            )
        )


# =========================================================
# FAIL PROCESSING JOB
# =========================================================

def fail_processing_job(
    connection,
    job_id,
    error_message,
    duration_ms
):

    with connection.cursor() as cursor:

        cursor.execute(
            """
            UPDATE processing_jobs
            SET
                status = 'FAILED',
                completed_at = NOW(),
                processing_duration_ms = %s,
                error_message = %s
            WHERE id = %s
            """,
            (
                duration_ms,
                error_message[:2000],
                job_id
            )
        )


# =========================================================
# LAMBDA HANDLER
# =========================================================

def lambda_handler(event, context):

    print("=================================================")
    print("SRIJA IMAGE PROCESSING LAMBDA")
    print("=================================================")

    print("Received event:")
    print(json.dumps(event))

    lambda_request_id = (
        context.aws_request_id
        if context
        else "unknown"
    )

    for sqs_record in event.get("Records", []):

        sqs_message_id = sqs_record.get(
            "messageId",
            "unknown"
        )

        connection = None
        job_id = None
        image_id = None
        start_time = time.time()

        try:

            # =================================================
            # READ SQS BODY
            # =================================================

            body = json.loads(
                sqs_record["body"]
            )

            if "Records" not in body:

                print(
                    "No S3 records found in SQS message."
                )

                continue

            # =================================================
            # PROCESS S3 RECORDS
            # =================================================

            for record in body["Records"]:

                bucket = (
                    record["s3"]["bucket"]["name"]
                )

                key = urllib.parse.unquote_plus(
                    record["s3"]["object"]["key"]
                )

                print(
                    f"Processing S3 object: s3://{bucket}/{key}"
                )

                # =================================================
                # ONLY PROCESS uploads/
                # =================================================

                if not key.startswith("uploads/"):

                    print(
                        f"Skipping non-upload object: {key}"
                    )

                    continue

                filename = os.path.basename(key)

                name, extension = os.path.splitext(
                    filename
                )

                extension = extension.lower()

                if extension not in [
                    ".jpg",
                    ".jpeg",
                    ".png"
                ]:

                    print(
                        f"Unsupported image format: {extension}"
                    )

                    continue

                # =================================================
                # DATABASE CONNECTION
                # =================================================

                connection = get_db_connection()

                print(
                    "Connected to RDS successfully."
                )

                # =================================================
                # FIND IMAGE
                # =================================================

                image = find_image_record(
                    connection,
                    key
                )

                if not image:

                    print(
                        f"No RDS image record found for {key}"
                    )

                    add_processing_event(
                        connection,
                        0,
                        "IMAGE_RECORD_NOT_FOUND",
                        "FAILED",
                        f"No image database record found for S3 key: {key}"
                    )

                    connection.close()
                    connection = None

                    continue

                image_id = image["id"]

                print(
                    f"RDS image ID: {image_id}"
                )

                # =================================================
                # UPDATE IMAGE → PROCESSING
                # =================================================

                update_image_status(
                    connection,
                    image_id,
                    "PROCESSING"
                )

                add_processing_event(
                    connection,
                    image_id,
                    "PROCESSING_STARTED",
                    "PROCESSING",
                    "Lambda started image processing."
                )

                # =================================================
                # CREATE PROCESSING JOB
                # =================================================

                job_id = create_processing_job(
                    connection,
                    image_id,
                    lambda_request_id,
                    sqs_message_id
                )

                print(
                    f"Processing job created: {job_id}"
                )

                # =================================================
                # FILE NAMES
                # =================================================

                output_ext = (
                    ".jpg"
                    if extension == ".jpeg"
                    else extension
                )

                input_path = (
                    f"/tmp/{filename}"
                )

                resized_filename = (
                    f"{name}_resized{output_ext}"
                )

                bw_filename = (
                    f"{name}_bw{output_ext}"
                )

                resized_path = (
                    f"/tmp/{resized_filename}"
                )

                bw_path = (
                    f"/tmp/{bw_filename}"
                )

                resized_key = (
                    f"processed/{resized_filename}"
                )

                bw_key = (
                    f"processed/{bw_filename}"
                )

                # =================================================
                # DOWNLOAD ORIGINAL
                # =================================================

                print(
                    "Downloading original image..."
                )

                s3.download_file(
                    bucket,
                    key,
                    input_path
                )

                original_size = os.path.getsize(
                    input_path
                )

                # =================================================
                # OPEN IMAGE
                # =================================================

                with Image.open(input_path) as source:

                    source = ImageOps.exif_transpose(
                        source
                    )

                    original_width, original_height = (
                        source.size
                    )

                    # =================================================
                    # RESIZE
                    # =================================================

                    resized = source.copy()

                    resized.thumbnail(
                        MAX_SIZE
                    )

                    processed_width, processed_height = (
                        resized.size
                    )

                    save_image(
                        resized,
                        resized_path,
                        output_ext
                    )

                    # =================================================
                    # BLACK AND WHITE
                    # =================================================

                    bw = resized.convert(
                        "L"
                    )

                    save_image(
                        bw,
                        bw_path,
                        output_ext
                    )

                resized_size = os.path.getsize(
                    resized_path
                )

                bw_size = os.path.getsize(
                    bw_path
                )

                # =================================================
                # COMMON METADATA
                # =================================================

                common_metadata = {

                    "original-width":
                        str(original_width),

                    "original-height":
                        str(original_height),

                    "processed-width":
                        str(processed_width),

                    "processed-height":
                        str(processed_height),

                    "original-size":
                        str(original_size),

                    "processing-status":
                        "completed"
                }

                content_type = (
                    "image/jpeg"
                    if output_ext == ".jpg"
                    else "image/png"
                )

                # =================================================
                # UPLOAD RESIZED IMAGE
                # =================================================

                print(
                    f"Uploading resized image: {resized_key}"
                )

                s3.upload_file(
                    resized_path,
                    bucket,
                    resized_key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "Metadata": {
                            **common_metadata,
                            "processed-size":
                                str(resized_size),
                            "variant":
                                "resized-colour"
                        }
                    }
                )

                # =================================================
                # UPLOAD B&W IMAGE
                # =================================================

                print(
                    f"Uploading B&W image: {bw_key}"
                )

                s3.upload_file(
                    bw_path,
                    bucket,
                    bw_key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "Metadata": {
                            **common_metadata,
                            "processed-size":
                                str(bw_size),
                            "variant":
                                "black-and-white"
                        }
                    }
                )

                print(
                    "Both processed images uploaded successfully."
                )

                # =================================================
                # PROCESSING DURATION
                # =================================================

                duration_ms = int(
                    (time.time() - start_time) * 1000
                )

                # =================================================
                # UPDATE IMAGES TABLE
                # =================================================

                with connection.cursor() as cursor:

                    cursor.execute(
                        """
                        UPDATE images
                        SET
                            resized_s3_key = %s,
                            bw_s3_key = %s,
                            original_width = %s,
                            original_height = %s,
                            resized_width = %s,
                            resized_height = %s,
                            resized_size_bytes = %s,
                            bw_width = %s,
                            bw_height = %s,
                            bw_size_bytes = %s,
                            original_size_bytes = %s,
                            overall_status = 'COMPLETED',
                            processing_completed_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            resized_key,
                            bw_key,

                            original_width,
                            original_height,

                            processed_width,
                            processed_height,
                            resized_size,

                            processed_width,
                            processed_height,
                            bw_size,

                            original_size,

                            image_id
                        )
                    )

                # =================================================
                # COMPLETE JOB
                # =================================================

                complete_processing_job(
                    connection,
                    job_id,
                    duration_ms
                )

                # =================================================
                # PROCESSING EVENT
                # =================================================

                add_processing_event(
                    connection,
                    image_id,
                    "PROCESS_COMPLETED",
                    "SUCCESS",
                    (
                        "Image successfully resized and "
                        "converted to black-and-white."
                    )
                )

                # =================================================
                # SNS NOTIFICATION
                # =================================================

                if SNS_TOPIC_ARN:

                    resized_url = (
                        make_presigned_url(
                            bucket,
                            resized_key
                        )
                    )

                    bw_url = (
                        make_presigned_url(
                            bucket,
                            bw_key
                        )
                    )

                    message = f"""
Image processing completed successfully.

Original:
s3://{bucket}/{key}

Original dimensions:
{original_width} x {original_height}

Processed dimensions:
{processed_width} x {processed_height}

Original size:
{original_size} bytes

Resized image:
{resized_url}

Black-and-white image:
{bw_url}

Processing duration:
{duration_ms} ms

RDS Image ID:
{image_id}

Processing Job ID:
{job_id}

Status:
SUCCESS

The download links expire in approximately 1 hour.
"""

                    response = sns.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject=(
                            "Srija Image Processing Completed"
                        ),
                        Message=message
                    )

                    print(
                        "SNS notification sent."
                    )

                    print(
                        "SNS MessageId:",
                        response.get("MessageId")
                    )

                # =================================================
                # CLEANUP
                # =================================================

                try:

                    if os.path.exists(input_path):
                        os.remove(input_path)

                    if os.path.exists(resized_path):
                        os.remove(resized_path)

                    if os.path.exists(bw_path):
                        os.remove(bw_path)

                except Exception as cleanup_error:

                    print(
                        "Cleanup warning:",
                        cleanup_error
                    )

                print(
                    f"Image {image_id} completed successfully."
                )

                connection.close()
                connection = None

        except Exception as error:

            duration_ms = int(
                (time.time() - start_time) * 1000
            )

            print(
                "================================================="
            )

            print(
                "IMAGE PROCESSING ERROR"
            )

            print(
                str(error)
            )

            print(
                "================================================="
            )

            # =================================================
            # RECORD FAILURE IN RDS
            # =================================================

            if connection and image_id:

                try:

                    update_image_status(
                        connection,
                        image_id,
                        "FAILED"
                    )

                    if job_id:

                        fail_processing_job(
                            connection,
                            job_id,
                            str(error),
                            duration_ms
                        )

                    add_processing_event(
                        connection,
                        image_id,
                        "PROCESS_FAILED",
                        "FAILED",
                        str(error)[:2000]
                    )

                except Exception as db_error:

                    print(
                        "Failed to record RDS error:",
                        db_error
                    )

            # =================================================
            # CLOSE CONNECTION
            # =================================================

            if connection:

                try:
                    connection.close()
                except Exception:
                    pass

                connection = None

            # =================================================
            # RAISE ERROR
            #
            # IMPORTANT:
            # Raising the error tells Lambda/SQS that
            # processing failed, so the message can be retried.
            # =================================================

            raise

    return {
        "statusCode": 200,
        "body": json.dumps(
            "Image processing completed successfully"
        )
    }