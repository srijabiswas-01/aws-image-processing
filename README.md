# Srija Flask + AWS Image Processor

## Architecture

Flask (local) -> S3 uploads/ -> S3 event -> SQS -> Lambda/Pillow ->
S3 processed/ -> SNS email

The Lambda creates:
- `processed/<name>_resized.jpg|png`
- `processed/<name>_bw.jpg|png`

SNS sends temporary S3 download links. Amazon SNS email does not attach binary
image files. Add Amazon SES later if an actual email attachment is required.

## 1. Install Flask dependencies

From this folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

The Flask app uses the AWS credentials already configured for the AWS CLI.

Optional environment values:

```powershell
$env:AWS_REGION="us-east-1"
$env:S3_BUCKET="srija-biswas"
$env:FLASK_SECRET_KEY="replace-with-a-random-secret"
```

## 2. Update Lambda

From the `lambda` folder:

```powershell
cd .\lambda
Compress-Archive `
  -Path .\lambda_function.py `
  -DestinationPath .\lambda_function.zip `
  -Force

aws lambda update-function-code `
  --function-name srija-image-processor `
  --zip-file fileb://lambda_function.zip `
  --region us-east-1
```

Your existing Pillow Lambda layer remains attached.

Wait for update completion:

```powershell
aws lambda wait function-updated `
  --function-name srija-image-processor `
  --region us-east-1
```

## 3. Run Flask

Return to the project folder:

```powershell
cd ..
py .\app.py
```

Open:

`http://127.0.0.1:5000`

## 4. IAM permission needed by the local Flask IAM user

The local IAM user must be able to:
- s3:PutObject on `uploads/*`
- s3:GetObject on `uploads/*` and `processed/*`
- s3:ListBucket for the bucket
- s3:DeleteObject on `uploads/*` and `processed/*` if dashboard delete is used


## 5. Notes

- The dashboard refreshes every 8 seconds.
- S3 objects stay private.
- Flask creates temporary pre-signed URLs for display.
- SNS email contains 1-hour temporary links.
- To send the actual image as a Gmail attachment, use Amazon SES instead of SNS.

# AWS Automated Image Processing Web Application

A cloud-based automated image processing system built using **Python Flask and AWS services**. The application allows users to upload images through a web interface and automatically processes them using an event-driven AWS architecture.

The system creates both a **resized colour version** and a **black-and-white version** of every uploaded image. Processed images are stored in Amazon S3, displayed through the Flask dashboard, and an Amazon SNS notification is sent to the configured email address when processing is completed.

---

## Project Overview

This project demonstrates how multiple AWS services can be integrated to build an automated, serverless image-processing workflow.

Instead of processing uploaded images directly inside the Flask application, Flask acts primarily as the user interface and upload mechanism. After an image is uploaded to Amazon S3, AWS automatically initiates the processing workflow.

The application uses:

- **Flask** for the local web application and dashboard
- **Amazon S3** for original and processed image storage
- **Amazon SQS** for asynchronous event/message handling
- **AWS Lambda** for serverless image processing
- **Pillow (PIL)** for resizing and black-and-white conversion
- **Amazon SNS** for email notifications
- **AWS IAM** for secure permissions between AWS services
- **Amazon CloudWatch** for Lambda execution logs and monitoring

No EC2 instance or relational database is required.

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
               \             /
                \           /
                 v         v
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

## Main Features

### 1. Web-Based Image Upload

Users can upload images through a simple Flask web interface.

Supported image formats include:

- JPG
- JPEG
- PNG

The uploaded image is stored automatically inside:

```text
s3://srija-biswas/uploads/
```

---

### 2. Event-Driven Processing

Amazon S3 is configured with an `ObjectCreated` event notification.

When a new image is uploaded under the `uploads/` prefix, S3 sends an event to the Amazon SQS queue.

This means the Flask application does not need to directly invoke Lambda.

The architecture remains loosely coupled:

```text
S3 → SQS → Lambda
```

---

### 3. Amazon SQS Queue

Amazon SQS acts as an intermediate messaging layer between Amazon S3 and AWS Lambda.

The queue improves reliability by allowing image-processing requests to wait until Lambda can process them.

Queue used by the project:

```text
srija-image-processing-queue
```

---

## Image Processing

AWS Lambda performs the actual image processing using the Python **Pillow** library.

For every uploaded image, Lambda generates two processed versions.

### Resized Colour Image

The original aspect ratio is preserved while the image is resized to fit within a maximum:

```text
800 × 800 pixels
```

For example:

```text
Original:
4016 × 6016

Processed:
534 × 800
```

JPEG images are also optimised using approximately:

```text
Quality = 85
```

This significantly reduces image file size while maintaining useful visual quality.

### Black-and-White Image

Lambda also creates a grayscale version of the resized image using Pillow.

Therefore, one uploaded image generates:

```text
Original
   |
   +---- Resized Colour
   |
   +---- Resized Black & White
```

---

## S3 Storage Structure

The application separates original and processed images using S3 prefixes.

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

This separation is important because only objects uploaded under:

```text
uploads/
```

trigger the processing workflow.

Objects created under:

```text
processed/
```

do not trigger Lambda again, preventing an infinite processing loop.

---

## Image Metadata

Lambda stores useful processing information as S3 object metadata.

Example:

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

Example values:

```text
original-width: 4016
original-height: 6016

processed-width: 534
processed-height: 800

processing-status: completed
variant: resized-colour
```

This allows the application to retain useful processing information without requiring a database.

---

## Flask Dashboard

The Flask application provides a dashboard where users can view the image-processing results.

The dashboard displays:

- Original uploaded image
- Resized colour image
- Black-and-white image
- Processing status
- Links to processed images
- Delete option

The dashboard automatically checks Amazon S3 to determine whether processing has completed.

Possible statuses include:

```text
Processing
Completed
```

Because S3 acts as the application's storage layer, no RDS or other relational database is required.

---

## Secure Image Access

Images do not need to be permanently public.

The Flask application generates **pre-signed Amazon S3 URLs** to display images securely.

These URLs provide temporary access to private S3 objects without making the entire bucket publicly accessible.

---

## Email Notification

After both processed images have successfully been uploaded to S3, AWS Lambda publishes a notification to an Amazon SNS topic.

SNS topic:

```text
srija-image-processing-notifications
```

The configured email subscriber receives a notification containing information such as:

```text
Image processing completed successfully.

Original dimensions:
4016 × 6016

Processed dimensions:
534 × 800

Resized Colour Image:
Temporary S3 Link

Black-and-White Image:
Temporary S3 Link

Status:
SUCCESS
```

The temporary image links allow the recipient to access the processed results securely.

> **Note:** Amazon SNS email notifications contain links to the images rather than attaching binary image files directly. Amazon SES can be integrated in the future if actual email attachments are required.

---

## IAM Security

AWS Identity and Access Management (IAM) is used to control access between the services.

The Lambda execution role requires permissions for:

```text
s3:GetObject
s3:PutObject

sqs:ReceiveMessage
sqs:DeleteMessage
sqs:GetQueueAttributes

sns:Publish
```

The Flask application's local AWS IAM credentials require appropriate S3 permissions for operations such as:

```text
s3:ListBucket
s3:GetObject
s3:PutObject
s3:DeleteObject
```

The project follows the principle of granting only the permissions required by each component.

---

## CloudWatch Monitoring

AWS Lambda automatically sends execution logs to Amazon CloudWatch.

The logs can be viewed using AWS CLI:

```powershell
aws logs tail /aws/lambda/srija-image-processor `
  --since 10m `
  --region us-east-1
```

Successful processing produces messages similar to:

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

CloudWatch makes it easier to identify problems with S3 downloads, Pillow processing, S3 uploads, or SNS notifications.

---

## Project Structure

```text
aws-image-processing/
│
├── app.py
│
├── requirements.txt
│
├── README.md
│
├── test.jpg
│
├── lambda/
│   ├── lambda_function.py
│   └── lambda_function.zip
│
├── policies/
│   ├── lambda-policy.json
│   ├── s3-notification.json
│   ├── sqs-policy.json
│   └── trust-policy.json
│
├── static/
│   └── style.css
│
├── templates/
│   ├── index.html
│   └── dashboard.html
│
└── pillow-layer/
```

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application and Lambda programming |
| Flask | Web interface and dashboard |
| Pillow | Image resizing and grayscale conversion |
| Amazon S3 | Image storage |
| Amazon SQS | Asynchronous event queue |
| AWS Lambda | Serverless image processing |
| Amazon SNS | Email notifications |
| AWS IAM | Access control and permissions |
| Amazon CloudWatch | Logging and monitoring |
| AWS CLI | AWS resource configuration and deployment |
| HTML/CSS | Front-end interface |

---

## Running the Flask Application

### Install dependencies

```powershell
py -m pip install -r requirements.txt
```

### Start Flask

From the project root:

```powershell
py .\app.py
```

The application will start at:

```text
http://127.0.0.1:5000
```

Open the address in a browser and upload an image.

---

## Deploying Updated Lambda Code

Move into the Lambda directory:

```powershell
cd .\lambda
```

Create the deployment ZIP:

```powershell
Compress-Archive `
  -Path .\lambda_function.py `
  -DestinationPath .\lambda_function.zip `
  -Force
```

Upload the code:

```powershell
aws lambda update-function-code `
  --function-name srija-image-processor `
  --zip-file fileb://lambda_function.zip `
  --region us-east-1
```

Wait for deployment:

```powershell
aws lambda wait function-updated `
  --function-name srija-image-processor `
  --region us-east-1
```

The Pillow dependency is supplied through the existing Lambda layer.

---

## Complete Workflow

When a user uploads an image, the following operations occur automatically:

```text
1. User selects an image in Flask
             ↓
2. Flask uploads the image to S3 uploads/
             ↓
3. S3 generates an ObjectCreated event
             ↓
4. Event is delivered to Amazon SQS
             ↓
5. SQS invokes AWS Lambda
             ↓
6. Lambda downloads the original image
             ↓
7. Pillow resizes the image
             ↓
8. Pillow generates a black-and-white version
             ↓
9. Both processed images are uploaded to S3 processed/
             ↓
10. Lambda publishes a message to Amazon SNS
             ↓
11. SNS sends an email notification
             ↓
12. Flask dashboard displays the processed images
```

---

## Benefits of the Architecture

The project demonstrates several important cloud-computing concepts:

- **Serverless processing** through AWS Lambda
- **Event-driven architecture** using S3 events
- **Asynchronous processing** through Amazon SQS
- **Object storage** using Amazon S3
- **Automated notifications** using Amazon SNS
- **Least-privilege access control** through IAM
- **Cloud monitoring** using CloudWatch
- **Separation of application and processing logic**
- **Automatic scaling without managing servers**
- **No relational database dependency**

The architecture can therefore handle image processing independently from the Flask web server.

---

## Future Improvements

The application can be extended with:

- Amazon SES for processed-image email attachments
- User authentication
- Multiple image uploads
- Additional image filters
- Custom resize dimensions
- Image rotation and cropping
- Watermarking
- Image format conversion
- Download buttons
- Processing history
- Dead-letter queue for failed processing
- CloudWatch alarms
- S3 lifecycle policies
- Hosted Flask deployment
- CloudFront for image delivery
- Improved dashboard analytics

---

## Conclusion

This project demonstrates a complete **event-driven AWS image-processing application** integrated with a Flask web interface. Users can upload images through Flask while AWS automatically manages asynchronous processing in the background.

Amazon S3 provides image storage, SQS manages processing events, Lambda and Pillow perform resizing and grayscale conversion, SNS provides email notifications, IAM secures communication between services, and CloudWatch provides operational monitoring.

The resulting architecture is modular, scalable and serverless for the image-processing component, while remaining simple enough to operate and test through a local Flask application and the AWS CLI.