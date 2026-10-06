FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# dataset đã có trong data/; nếu thiếu thì dựng lại từ data/raw (không cần mạng)
RUN [ -f data/vietnamese_dbpedia.nt ] || (python -m vidbpedia build && python -m vidbpedia postprocess)

EXPOSE 7860

CMD ["python", "-m", "vidbpedia", "serve", "--host", "0.0.0.0", "--port", "7860"]
