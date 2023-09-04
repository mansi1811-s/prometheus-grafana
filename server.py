from flask import Flask
from flask import render_template,request
import boto3
import botocore
import prometheus_client
import psutil
import time
import threading
from botocore.exceptions import ClientError
from prometheus_client import start_http_server,Histogram, Gauge, Counter, Summary

client = boto3.client('s3')

app = Flask(__name__)

request_total = Counter('myapp_requests_total','Total number of requests received')
http_requests_duration_seconds = Gauge('myapp_http_requests_duration_seconds', 'Duration of HTTP requests')
memory_usage = Gauge('myapp_memory_usage_bytes', 'Memory Usage in Bytes') 
cpu_usage_percent = Gauge('myapp_cpu_usage_percent', 'CPU Usage Percentage')


@app.route("/")
def home():
    request_total.inc()
    start_time = time.time()
    time.sleep(0.1)
    http_requests_duration_seconds.set(time.time() - start_time)
    return render_template('index.html')

@app.route("/metrics")
def metrics(): 
    memory_usage.set(psutil.virtual_memory().used)
    cpu_usage_percent.set(psutil.cpu_percent())
    return prometheus_client.generate_latest()

#List S3 buckets
@app.route('/listing')
def listing():
    list_buckets=client.list_buckets()
    buckets=list_buckets["Buckets"]
    return render_template('result.html',buckets=buckets)

# Create a new S3 bucket 
@app.route('/create_bucket', methods=['POST']) 
def create_bucket():
   #retrieve value of bucket_name from the HTML form
   bucket_name = request.form['bucket_name'] 
   try:
      client.create_bucket(Bucket=bucket_name,
                            CreateBucketConfiguration={
             'LocationConstraint': 'ap-south-1' })
      return render_template('status.html', message='Bucket created successfully')
   except client.exceptions.BucketAlreadyExists:
      return render_template('status.html',message=f"s3 bucket{bucket_name} already exists")
   except client.exceptions.BucketAlreadyOwnedByYou:
      return render_template('status.html',message=f"S3 bucket {bucket_name} already owned by you")
   except botocore.exceptions.ClientError as e:
      return render_template('status.html',message=e)
   

#Upload file to s3 bucket
@app.route('/upload_file', methods=['POST'])
def upload_file():
   #retrieve value of bucket_name from the HTML form  
   bucket_name=request.form['bucket_name']
   try:
      file=request.files['file']
      file_name=file.filename
      client.upload_fileobj(file, bucket_name,file_name)
   except botocore.exceptions.ClientError as error:
      return render_template('status.html',message=error)

   return render_template('status.html',message='File uploaded successfully')


#Create folder inside a bucket
@app.route('/create_folder' , methods=['POST'])
def create_folder():
   try:
      bucket_name = request.form['bucket_name']
      directory_name = request.form['directory_name']
      client.put_object(Bucket=bucket_name, Key=(directory_name+'/'))
      return render_template('status.html',message='Folder created succesfully')
   except ClientError as e:
       message= e.response["Error"]['Code']
       return render_template('status.html',message=message)


#Delete S3 bucket
@app.route('/delete_bucket', methods=['POST'])
def delete_bucket():
#retrieve value of del_buck from the HTML form
    del_buck = request.form['del_buck']
    result = None
    try:
      s3 = boto3.resource("s3")
      bucket = s3.Bucket(del_buck)
      bucket.objects.all().delete()
      bucket.delete()
      return render_template('status.html', message='Bucket deleted successfully')
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            return render_template('status.html', message=f'The bucket {del_buck} does not exist.')
        else:
            return render_template('status.html', message=f'An error occurred: {e}')
    
#Delete objects
def del_all_obj(del_buck):
    
        response=client.list_objects_v2(Bucket=del_buck)
        files=response["Contents"]
        files_del=[]
        for f in files:
            files_del.append({"Key": f["Key"]})

        if "Contents" in response:
            response=client.delete_objects(
            Bucket=del_buck,
            Delete={"Objects" : files_del}
            )

        response = client.delete_bucket(Bucket=del_buck  )
        

#Delete files in a bucket
@app.route('/del_file',methods=['POST'])
def del_file():
      bucket_name=request.form['bucket_name']
      file_name=request.form['file_name']
      try: 
         response = client.delete_object(
            Bucket=bucket_name,
            Key=file_name)
         return render_template('status.html',message="File deleted succesfully")
      except ClientError as e:
         if e.response['Error']['Code'] == 'NoSuchBucket':
            return render_template('status.html', message=f'The bucket {bucket_name} does not exist.')
         elif e.response['Error']['Code'] == 'NoSuchKey':
            return render_template('status.html', message=f'The file {file_name} does not exist in the bucket {bucket_name}.')
        


#Copy files from one bucket to another
@app.route('/copy',methods=['POST'])
def copy():
   src_bucket=request.form['src_bucket']
   src_file=request.form['src_file']
   des_bucket=request.form['des_bucket']
   des_file=request.form['des_file']

   copy_source = {
         'Bucket': src_bucket, 
         'Key': src_file
    }
   try:
      response = client.copy_object(
         Bucket=des_bucket,
         CopySource=copy_source,
         Key=des_file   
      )
      return render_template('status.html',message="Object copied")
   except ClientError as e:
      if e.response['Error']['Code'] == 'NoSuchBucket':
         return render_template('status.html', message=f'The bucket {src_bucket} or {des_bucket} does not exist.')
      elif e.response['Error']['Code'] == 'NoSuchKey':
         return render_template('status.html', message=f'The file {src_file} does not exist in the bucket {src_bucket}.')



#Move files within S3 bucket
@app.route('/move',methods=['POST'])
def move():
   src_bucket=request.form['src_bucket']
   src_file=request.form['src_file']
   des_bucket=request.form['des_bucket']
   des_file=request.form['des_file']

   copy_source = {
            'Bucket': src_bucket, 
            'Key': src_file
      }
   try:
      response = client.copy_object(
         Bucket=des_bucket,
         CopySource=copy_source,
         Key=des_file     
      )
      client.delete_object(Bucket=src_bucket,Key=src_file)
      return render_template('status.html',message="Object moved successfully")
   except ClientError as e:
      if e.response['Error']['Code'] == 'NoSuchBucket':
         return render_template('status.html', message=f'The bucket {src_bucket} or {des_bucket} does not exist.')
      elif e.response['Error']['Code'] == 'NoSuchKey':
         return render_template('status.html', message=f'The file {src_file} does not exist in the bucket {src_bucket}.')


#List objects
@app.route('/get_Objects',methods=['POST'])
def get_Objects():
   bucket_name=request.form['bucket_name']
   s3 = boto3.resource('s3')

   my_bucket = s3.Bucket(bucket_name)
   obj=[]
   try:
      for my_bucket_object in my_bucket.objects.all():
         obj.append(my_bucket_object.key)
      return render_template('objlist.html',obj=obj)
   except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            return render_template('status.html', message=f'The bucket {bucket_name} does not exist.')
        else:
            return render_template('status.html', message=f'An error occurred: {e}')

if __name__ == "__main__":
   app.run(host="0.0.0.0",port=("5001"), debug=True)