from flask import Flask
from threading import Thread
import logging

logger = logging.getLogger("OrlandoBot.KeepAlive")

app = Flask("OrlandoBot")


@app.route("/")
def home():
    return "Orlando Moderation Bot is running!"


@app.route("/health")
def health():
    return {"status": "online", "service": "Orlando Moderation Bot"}


def run():
    app.run(host="0.0.0.0", port=8080)


def start():
    t = Thread(target=run, daemon=True)
    t.start()
    logger.info("Keep-alive web server started on port 8080")
