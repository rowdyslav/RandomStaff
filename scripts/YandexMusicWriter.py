from typing import Iterator

from environs import Env
from keyboard import wait, write
from yandex_music import Client, Track
from yandex_music.exceptions import NotFoundError

ENV = Env()
ENV.read_env()

CLIENT: Client = Client(ENV.str("YANDEX_MUSIC_TOKEN")).init()
BIND: str = "num lock"


def get_actual_track() -> Track:
    last_queue = CLIENT.queue(CLIENT.queues_list()[0].id)
    actual_track = last_queue.get_current_track().fetch_track()
    return actual_track


def get_track_text(track: Track) -> Iterator[str]:
    try:
        text = iter(
            track.get_lyrics("TEXT").fetch_lyrics().replace("\n\n", "\n").split("\n")
        )
    except NotFoundError:
        print("Текст песни отсутствует")
        text = iter("\n" * 99999)
    return text


def main() -> None:
    last_track = get_actual_track()
    text = get_track_text(last_track)
    while True:
        wait(BIND)
        now_track = get_actual_track()
        if now_track != last_track:
            text = get_track_text(now_track)
            last_track = now_track
        write(next(text))


if __name__ == "__main__":
    main()
