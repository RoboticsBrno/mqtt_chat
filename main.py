#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime

import aiomqtt
from rich.markup import escape
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label, TextLog
from typing_extensions import TypedDict

from animals import ANIMALS

MQTT_HOST = "mqtt.lan"
MQTT_TOPIC = "robotabor2023/chat"

COLORS = [
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "bright_white",
]

MY_ID = uuid.getnode()
MY_COLOR = COLORS[MY_ID % len(COLORS)]
MY_ANIMAL = ANIMALS[MY_ID % len(ANIMALS)]

LOGGER = logging.getLogger(__name__)


class MqttMessage(TypedDict):
    id: int
    color: str
    animal: str
    message: str


class ChatApp(App[None]):
    CSS = """
#message-bar {
    height: auto;
}
#my-name {
    content-align-vertical: middle;
    height: 100%;
}
"""

    def __init__(self, client: aiomqtt.Client) -> None:
        super().__init__()
        self._client = client

        self._log_file = open("./log.txt", "r+")

    def compose(self) -> ComposeResult:
        with Vertical():
            yield TextLog(
                wrap=True,
                markup=True,
                auto_scroll=False,
                max_lines=5000,
            )
            with Horizontal(id="message-bar"):
                yield Label(
                    f"<[bold {MY_COLOR}]{escape(MY_ANIMAL)}[/bold {MY_COLOR}]>",
                    id="my-name",
                )
                yield Input(placeholder="Napis zpravu...")
            yield Label(expand=True, id="error")

    def on_mount(self, _event: events.Mount) -> None:
        self.query_one(Input).focus()
        self.query_one(TextLog).write(self._log_file.read(), scroll_end=True)

    def on_message(self, msg: MqttMessage) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        if msg["color"] not in COLORS:
            msg["color"] = "white"

        ex = ""
        if msg["id"] == MY_ID:
            ex = "underline"

        line = f"[grey]{ts}[/grey] <[bold {ex} {msg['color']}]{escape(msg['animal'])}[/bold {ex} {msg['color']}]>: {escape(msg['message'])}"
        self._log_file.write(line + "\n")
        self._log_file.flush()

        tl = self.query_one(TextLog)
        tl.write(
            line,
            scroll_end=(
                msg["animal"] == MY_ANIMAL or tl.scroll_offset.y == tl.max_scroll_y
            ),
        )

    def _on_publish_done(self, task: "asyncio.Task[None]") -> None:
        ex = task.exception()
        if ex is not None:
            self.query_one(
                "#error", Label
            ).renderable = f"[bold red]Error: failed to send message: {ex}[/bold red]"

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#error", Label).renderable = ""
        if not event.value:
            return

        msg: MqttMessage = {
            "id": MY_ID,
            "color": MY_COLOR,
            "animal": MY_ANIMAL,
            "message": event.value.replace("\\n", "\n"),
        }

        task = asyncio.create_task(
            self._client.publish(MQTT_TOPIC, json.dumps(msg).encode("utf-8"))
        )
        task.add_done_callback(self._on_publish_done)

        event.input.value = ""


async def reader_routine(client: aiomqtt.Client, app: ChatApp) -> None:
    async with client.messages() as messages:
        await client.subscribe(MQTT_TOPIC)
        async for raw_msg in messages:
            if not isinstance(raw_msg.payload, bytes):
                continue

            try:
                msg: MqttMessage = json.loads(raw_msg.payload)
                app.on_message(msg)
            except Exception:
                LOGGER.exception("failed to decode message %s", raw_msg.payload)
                continue


async def main() -> None:
    async with aiomqtt.Client(MQTT_HOST) as client:
        app = ChatApp(client)
        asyncio.create_task(reader_routine(client, app))
        await app.run_async()


if __name__ == "__main__":
    # https://github.com/sbtinstruments/aiomqtt#note-for-windows-users
    # Change to the "Selector" event loop if platform is Windows
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        from asyncio import WindowsSelectorEventLoopPolicy  # type: ignore
        from asyncio import set_event_loop_policy

        set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
