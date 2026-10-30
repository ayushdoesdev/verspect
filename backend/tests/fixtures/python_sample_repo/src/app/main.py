from fastapi import FastAPI, BackgroundTasks
import requests
from pydantic import BaseModel

app = FastAPI()


class User(BaseModel):
    name: str


def send_email(background_tasks: BackgroundTasks) -> None:
    background_tasks.add_task(lambda: None)


def fetch() -> None:
    requests.get("https://example.com")
