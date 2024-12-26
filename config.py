from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    MYSQL_CONFIG = {
        "host": os.getenv("MYSQL_HOST"),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE")
    }

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")