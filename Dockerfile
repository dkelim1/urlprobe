FROM python:3.10

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . . 

RUN apt-get update && \
    apt-get install -yq tzdata && \
    ln -fs /usr/share/zoneinfo/Asia/Singapore /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

ENV TZ="Asia/Singapore"

EXPOSE 8000

CMD [ "python", "./urlprobe.py" ]