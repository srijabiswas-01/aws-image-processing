import json
import boto3
import os
import urllib.parse
from PIL import Image, ImageOps

s3 = boto3.client("s3")
sns = boto3.client("sns")

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
MAX_SIZE = (800, 800)

def make_presigned_url(bucket, key):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600
    )

def save_image(img, output_path, extension):
    if extension in [".jpg", ".jpeg"]:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(output_path, "JPEG", quality=85, optimize=True)
    else:
        img.save(output_path, "PNG", optimize=True)

def lambda_handler(event, context):
    print("Received event:")
    print(json.dumps(event))

    for sqs_record in event.get("Records", []):
        body = json.loads(sqs_record["body"])

        if "Records" not in body:
            print("No S3 records found")
            continue

        for record in body["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

            if not key.startswith("uploads/"):
                print(f"Skipping non-upload object: {key}")
                continue

            filename = os.path.basename(key)
            name, extension = os.path.splitext(filename)
            extension = extension.lower()

            if extension not in [".jpg", ".jpeg", ".png"]:
                print(f"Unsupported image format: {extension}")
                continue

            # Normalise JPEG output extension so the Flask app can predict the key.
            output_ext = ".jpg" if extension == ".jpeg" else extension

            input_path = f"/tmp/{filename}"
            resized_filename = f"{name}_resized{output_ext}"
            bw_filename = f"{name}_bw{output_ext}"
            resized_path = f"/tmp/{resized_filename}"
            bw_path = f"/tmp/{bw_filename}"

            resized_key = f"processed/{resized_filename}"
            bw_key = f"processed/{bw_filename}"

            s3.download_file(bucket, key, input_path)
            original_size = os.path.getsize(input_path)

            with Image.open(input_path) as source:
                source = ImageOps.exif_transpose(source)
                original_width, original_height = source.size

                resized = source.copy()
                resized.thumbnail(MAX_SIZE)
                processed_width, processed_height = resized.size
                save_image(resized, resized_path, output_ext)

                bw = resized.convert("L")
                save_image(bw, bw_path, output_ext)

            resized_size = os.path.getsize(resized_path)
            bw_size = os.path.getsize(bw_path)

            common_metadata = {
                "original-width": str(original_width),
                "original-height": str(original_height),
                "processed-width": str(processed_width),
                "processed-height": str(processed_height),
                "original-size": str(original_size),
                "processing-status": "completed"
            }

            s3.upload_file(
                resized_path,
                bucket,
                resized_key,
                ExtraArgs={
                    "ContentType": "image/jpeg" if output_ext == ".jpg" else "image/png",
                    "Metadata": {
                        **common_metadata,
                        "processed-size": str(resized_size),
                        "variant": "resized-colour"
                    }
                }
            )

            s3.upload_file(
                bw_path,
                bucket,
                bw_key,
                ExtraArgs={
                    "ContentType": "image/jpeg" if output_ext == ".jpg" else "image/png",
                    "Metadata": {
                        **common_metadata,
                        "processed-size": str(bw_size),
                        "variant": "black-and-white"
                    }
                }
            )

            print(f"Resized image uploaded: s3://{bucket}/{resized_key}")
            print(f"Black-and-white image uploaded: s3://{bucket}/{bw_key}")

            if SNS_TOPIC_ARN:
                resized_url = make_presigned_url(bucket, resized_key)
                bw_url = make_presigned_url(bucket, bw_key)

                message = f"""Image processing completed successfully.

Original:
s3://{bucket}/{key}

Original dimensions:
{original_width} x {original_height}

Processed dimensions:
{processed_width} x {processed_height}

Resized colour image:
{resized_url}

Black-and-white image:
{bw_url}

The download links expire in approximately 1 hour.

Status: SUCCESS
"""

                response = sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject="Srija Image Processing Completed",
                    Message=message
                )

                print("SNS notification sent")
                print("SNS MessageId:", response.get("MessageId"))

    return {
        "statusCode": 200,
        "body": json.dumps("Image processing completed successfully")
    }
