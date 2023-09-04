FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install psutil && pip install flask && pip install prometheus-client && pip install flask_prometheus_metrics 

RUN pip install boto3 && pip install botocore 

EXPOSE 5001

CMD [ "python3", "./server.py" ]
