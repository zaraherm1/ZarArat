FROM python:3.12-slim
WORKDIR /app
COPY bot.py keywords.json name_replies.json config.json ./
CMD ["python3", "bot.py"]
