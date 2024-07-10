FROM python:3.11.7-alpine3.19

COPY icosagent /opt/icos/icosagent
COPY requirements.txt LICENSE dm.py /opt/icos/

WORKDIR /opt/icos/

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["./dm.py"]
