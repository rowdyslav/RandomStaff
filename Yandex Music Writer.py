from yandex_music import Client
from yandex_music.exceptions import NotFoundError
import keyboard

TOKEN = "y0_AgAAAABKJfemAAG8XgAAAADlag4Wys_dz1tpSZy3POtIg0dVEQCaLWs"
client = Client(TOKEN).init()


def get_actual_track():
    last_queue = client.queue(client.queues_list()[0].id)
    actual_track = last_queue.get_current_track().fetch_track()
    return actual_track


def get_track_text(track):
    try:
        text = iter(
            track.get_lyrics("TEXT").fetch_lyrics().replace("\n\n", "\n").split("\n")
        )
    except NotFoundError:
        print("Текст песни отсутствует")
        text = iter("\n" * 99999)
    return text


def main():
    last_track = get_actual_track()
    text = get_track_text(last_track)
    while True:
        keyboard.wait("num lock")
        now_track = get_actual_track()
        if now_track != last_track:
            text = get_track_text(now_track)
            last_track = now_track
        keyboard.write(next(text))


if __name__ == "__main__":
    main()
