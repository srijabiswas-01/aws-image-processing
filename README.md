# Srija Flask + AWS Image Processor

A cloud-based, event-driven image processing application built with **Python Flask** and **AWS services**.

The system allows users to upload images through a Flask web application, stores them in Amazon S3, processes them automatically using AWS Lambda and Pillow, and generates both a **resized colour image** and a **black-and-white image**.

Processed images are displayed on a Flask dashboard, while Amazon SNS sends an email notification containing temporary download links.

---

## Project Overview

This project demonstrates how a Flask application can be integrated with multiple AWS services to create a reliable, automated, and serverless image-processing workflow.

The application uses:

- **Python Flask** for the web interface
- **Amazon S3** for image storage
- **Amazon SQS** for asynchronous message handling
- **AWS Lambda** for serverless processing
- **Pillow (PIL)** for image transformation
- **Amazon SNS** for email notifications
- **AWS IAM** for access control
- **Amazon CloudWatch** for monitoring and logs
- **AWS CLI** for deployment and configuration

No EC2 instance or relational database is required.

---

## Application Screenshots

### Upload Page

The upload interface allows users to select a JPG, JPEG, or PNG image and upload it directly to the Amazon S3 `uploads/` folder.

![Image Upload Page](screenshots/upload-page.png)

### Image Processing Dashboard

The dashboard displays the original image together with the generated resized and black-and-white versions.

It also shows the processing status and provides options to access or delete images.

![Image Processing Dashboard](screenshots/dashboard.png)

---

## System Architecture

```text
                   USER
                     |
                     v
             +---------------+
             |   Flask Web   |
             |  Application  |
             +---------------+
                     |
                     | Upload
                     v
             +---------------+
             |   Amazon S3   |
             |   uploads/    |
             +---------------+
                     |
                ObjectCreated
                     |
                     v
             +---------------+
             |  Amazon SQS   |
             |     Queue     |
             +---------------+
                     |
                     v
             +---------------+
             |  AWS Lambda   |
             |    Pillow     |
             +---------------+
                /         \
               /           \
              v             v
      Resized Colour    Black & White
               \           /
                \         /
                 v       v
             +---------------+
             |   Amazon S3   |
             |  processed/   |
             +---------------+
                     |
                     v
             +---------------+
             |  Amazon SNS   |
             +---------------+
                     |
                     v
             Email Notification
```

---

## Workflow

The complete processing flow is:

```text
Flask
   ↓
Amazon S3 uploads/
   ↓
S3 ObjectCreated Event
   ↓
Amazon SQS
   ↓
AWS Lambda
   ↓
Pillow Image Processing
   ↓
Amazon S3 processed/
   ↓
Amazon SNS
   ↓
Email Notification
```

When a user uploads an image:

1. Flask uploads the original image to Amazon S3.
2. S3 generates an `ObjectCreated` event.
3. The event is delivered to Amazon SQS.
4. AWS Lambda receives the SQS message.
5. Lambda downloads the image from S3.
6. Pillow resizes the image.
7. Pillow creates a black-and-white version.
8. Lambda uploads both processed images to S3.
9. Lambda publishes a notification to Amazon SNS.
10. SNS sends an email containing temporary S3 links.
11. The Flask dashboard displays the processed images.

---

## Main Features

### Web-Based Upload

Users can upload:

- JPG
- JPEG
- PNG

Uploaded files are stored under:

```text
s3://srija-biswas/uploads/
```

---

### Automatic Image Processing

AWS Lambda processes each uploaded image using Pillow.

For every original image, two files are created:

```text
processed/<name>_resized.jpg
processed/<name>_bw.jpg
```

or, for PNG images:

```text
processed/<name>_resized.png
processed/<name>_bw.png
```

---

## Resized Colour Image

The uploaded image is resized while maintaining its aspect ratio.

The maximum output size is:

```text
800 × 800 pixels
```

Example:

```text
Original:
4016 × 6016

Processed:
534 × 800
```

JPEG files are saved with approximately:

```text
Quality = 85
```

This reduces file size while maintaining good visual quality.

---

## Black-and-White Processing

Lambda creates a grayscale version of the resized image.

Therefore, a single uploaded image produces:

```text
Original Image
     |
     +---- Resized Colour Image
     |
     +---- Black-and-White Image
```

---

## Amazon S3 Structure

The bucket separates uploaded and processed images using prefixes.

```text
srija-biswas/
│
├── uploads/
│   ├── image_12345678.jpg
│   └── photo_87654321.png
│
└── processed/
    ├── image_12345678_resized.jpg
    ├── image_12345678_bw.jpg
    ├── photo_87654321_resized.png
    └── photo_87654321_bw.png
```

Only objects created inside:

```text
uploads/
```

trigger the processing pipeline.

Objects created inside:

```text
processed/
```

do not trigger Lambda again.

This prevents recursive Lambda execution.

---

## Amazon SQS

Amazon SQS acts as an intermediate messaging layer between S3 and Lambda.

Queue:

```text
srija-image-processing-queue
```

Using SQS provides asynchronous processing and reduces direct dependency between Amazon S3 and AWS Lambda.

Architecture:

```text
S3 → SQS → Lambda
```

---

## AWS Lambda

AWS Lambda performs the image-processing operation.

The function:

- Reads the SQS message
- Extracts the S3 object information
- Downloads the original image
- Corrects image orientation
- Resizes the image
- Creates a grayscale version
- Uploads both processed versions
- Generates temporary S3 links
- Publishes an SNS notification

Lambda function:

```text
srija-image-processor
```

---

## Pillow Lambda Layer

The Pillow library is provided using an AWS Lambda Layer.

This keeps the main Lambda deployment package smaller and separates third-party dependencies from the application code.

The project uses Python 3.12-compatible Pillow libraries.

---

## Image Metadata

Processed images can include useful metadata such as:

```text
original-width
original-height
processed-width
processed-height
original-size
processed-size
processing-status
variant
```

Example:

```text
original-width: 4016
original-height: 6016
processed-width: 534
processed-height: 800
processing-status: completed
variant: resized-colour
```

This provides processing information without requiring a relational database.

---

## Flask Dashboard

The dashboard displays:

- Original uploaded image
- Resized colour image
- Black-and-white image
- Processing status
- Temporary image links
- Delete option

Possible processing states include:

```text
Processing
Completed
```

The dashboard refreshes automatically every:

```text
8 seconds
```

---

## Secure Image Access

S3 images remain private.

The Flask application creates temporary **pre-signed S3 URLs** that allow users to view the images without making the bucket publicly accessible.

This provides temporary authenticated access to private S3 objects.

---

## Email Notification

After image processing is completed, AWS Lambda publishes a message to Amazon SNS.

SNS topic:

```text
srija-image-processing-notifications
```

A typical notification contains:

```text
Image processing completed successfully.

Original dimensions:
4016 × 6016

Processed dimensions:
534 × 800

Resized Colour Image:
Temporary S3 link

Black-and-White Image:
Temporary S3 link

Status:
SUCCESS
```

The generated links are temporary and expire automatically.

> Amazon SNS email notifications contain links rather than binary image attachments. Amazon SES can be added later if actual email attachments are required.

---

## IAM Security

AWS IAM controls access between the services.

### Lambda Execution Role

The Lambda execution role requires permissions such as:

```text
s3:GetObject
s3:PutObject

sqs:ReceiveMessage
sqs:DeleteMessage
sqs:GetQueueAttributes

sns:Publish
```

### Local Flask IAM User

The AWS credentials used by Flask require:

```text
s3:ListBucket
s3:GetObject
s3:PutObject
s3:DeleteObject
```

for the required `uploads/` and `processed/` prefixes.

The project follows the principle of least privilege.

---

## CloudWatch Monitoring

AWS Lambda sends execution logs to Amazon CloudWatch.

Logs can be viewed using:

```powershell
aws logs tail /aws/lambda/srija-image-processor `
  --since 10m `
  --region us-east-1
```

Example successful output:

```text
Processing image: uploads/example.jpg

Original dimensions:
4016x6016

Resized image uploaded:
s3://srija-biswas/processed/example_resized.jpg

Black-and-white image uploaded:
s3://srija-biswas/processed/example_bw.jpg

SNS notification sent
```

CloudWatch helps diagnose:

- Lambda errors
- S3 access problems
- Pillow processing errors
- SQS issues
- SNS publishing failures

---

## Project Structure

```text
aws-image-processing/
│
├── app.py
├── README.md
├── requirements.txt
├── test.jpg
│
├── lambda/
│   ├── lambda_function.py
│   ├── lambda_function.zip
│   ├── PIL/
│   ├── pillow.libs/
│   └── pillow-12.2.0.dist-info/
│
├── pillow-layer/
│   ├── pillow-layer.zip
│   └── python/
│
├── policies/
│   ├── lambda-policy.json
│   ├── s3-notification.json
│   ├── sqs-attributes.json
│   ├── sqs-policy.json
│   └── trust-policy.json
│
├── screenshots/
│   ├── upload-page.png
│   └── dashboard.png
│
├── static/
│   └── style.css
│
└── templates/
    ├── index.html
    └── dashboard.html
```

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend development |
| Flask | Web application and dashboard |
| Pillow | Image processing |
| Amazon S3 | Object storage |
| Amazon SQS | Message queue |
| AWS Lambda | Serverless image processing |
| Amazon SNS | Email notification |
| AWS IAM | Access management |
| Amazon CloudWatch | Logs and monitoring |
| AWS CLI | AWS resource management |
| HTML | User interface |
| CSS | Application styling |

---

# Installation

## 1. Clone the Repository

```powershell
git clone https://github.com/srijabiswas-01/aws-image-processing.git
```

Move into the project directory:

```powershell
cd aws-image-processing
```

---

## 2. Create a Virtual Environment

```powershell
py -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## 3. Install Dependencies

```powershell
py -m pip install -r requirements.txt
```

---

## 4. Configure AWS CLI

The application uses AWS credentials already configured for the AWS CLI.

Check the configuration:

```powershell
aws configure list
```

Optional environment variables:

```powershell
$env:AWS_REGION="us-east-1"

$env:S3_BUCKET="srija-biswas"

$env:FLASK_SECRET_KEY="replace-with-a-random-secret"
```

---

# Running the Flask Application

From the project root:

```powershell
py .\app.py
```

The development server starts at:

```text
http://127.0.0.1:5000
```

Open the address in a browser.

---

# Deploying the Lambda Function

Move into the Lambda directory:

```powershell
cd .\lambda
```

Create the deployment package:

```powershell
Compress-Archive `
  -Path .\lambda_function.py `
  -DestinationPath .\lambda_function.zip `
  -Force
```

Upload the new Lambda code:

```powershell
aws lambda update-function-code `
  --function-name srija-image-processor `
  --zip-file fileb://lambda_function.zip `
  --region us-east-1
```

Wait for Lambda to finish updating:

```powershell
aws lambda wait function-updated `
  --function-name srija-image-processor `
  --region us-east-1
```

Return to the project root:

```powershell
cd ..
```

The existing Pillow Lambda Layer remains attached to the function.

---

# Testing the Application

Start Flask:

```powershell
py .\app.py
```

Open:

```text
http://127.0.0.1:5000
```

Upload a new image.

The expected S3 objects should be similar to:

```text
uploads/example_12345678.jpg

processed/example_12345678_resized.jpg
processed/example_12345678_bw.jpg
```

Check the processed folder:

```powershell
aws s3 ls s3://srija-biswas/processed/ `
  --region us-east-1
```

Check Lambda logs:

```powershell
aws logs tail /aws/lambda/srija-image-processor `
  --since 10m `
  --region us-east-1
```

---

# Benefits of the Architecture

This project demonstrates:

- Event-driven cloud architecture
- Serverless image processing
- Asynchronous message handling
- Automated S3 events
- Secure IAM permissions
- Cloud monitoring
- Temporary pre-signed URL generation
- Automatic email notifications
- Separation between web and processing layers
- No EC2 dependency
- No RDS dependency
- Automatic scaling of the Lambda processing layer

---

# Future Improvements

Potential improvements include:

- Amazon SES email attachments
- User authentication
- Multiple-image upload
- Batch image processing
- Custom resize dimensions
- Cropping
- Rotation
- Watermarking
- Additional filters
- Image format conversion
- Direct download buttons
- Processing history
- SQS dead-letter queue
- CloudWatch alarms
- S3 lifecycle policies
- CloudFront image delivery
- Hosted Flask deployment
- Dashboard analytics

---

# Conclusion

The **Srija Flask + AWS Image Processor** demonstrates a complete event-driven cloud image-processing workflow.

The Flask web application provides a simple user interface for uploading and viewing images, while Amazon S3 stores the original and processed files. Amazon SQS provides asynchronous messaging, AWS Lambda and Pillow perform image transformations, Amazon SNS provides email notifications, IAM secures access between services, and CloudWatch provides operational monitoring.

The architecture is modular, scalable, secure, and demonstrates practical integration of multiple AWS services without requiring EC2 or a relational database.