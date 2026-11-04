FROM python:3.12-slim
WORKDIR /app
COPY bot.py keywords.json name_replies.json ./
CMD ["python3", "bot.py"]
