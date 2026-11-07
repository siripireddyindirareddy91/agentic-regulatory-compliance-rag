"""Original-file storage: durable database default, optional private S3 bucket."""
import os,base64,hashlib
def store(blob,tenant,document_id):
    bucket=os.getenv('S3_BUCKET')
    if not bucket:return base64.b64encode(blob).decode()
    import boto3
    key='institutions/'+tenant+'/documents/'+document_id+'/'+hashlib.sha256(blob).hexdigest()
    boto3.client('s3',endpoint_url=os.getenv('S3_ENDPOINT_URL') or None).put_object(Bucket=bucket,Key=key,Body=blob,ServerSideEncryption='AES256',ContentType='application/octet-stream')
    return 's3://'+bucket+'/'+key
def load(value):
    if not value.startswith('s3://'):return base64.b64decode(value)
    import boto3
    bucket,key=value[5:].split('/',1)
    if bucket!=os.getenv('S3_BUCKET'):raise ValueError('Storage bucket configuration does not match document')
    return boto3.client('s3',endpoint_url=os.getenv('S3_ENDPOINT_URL') or None).get_object(Bucket=bucket,Key=key)['Body'].read(11*1024*1024)
