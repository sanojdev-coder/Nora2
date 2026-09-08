FROM python:3.10-slim

WORKDIR /app

COPY poc/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY poc /app

EXPOSE 4021

CMD ["python", "main.py"]
