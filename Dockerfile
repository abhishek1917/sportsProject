FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_DEBUG=false

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py tailwind install \
    && python manage.py tailwind build \
    && python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["bash", "start.sh"]
