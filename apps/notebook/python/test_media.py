"""A cell's sounds and files (``media``, ``cells.audio``/``download``): a player and a file to save, under the cell
where they are called."""

import base64
import io
import json
import wave

from electro_notebook import cells


def _wav(output: dict) -> wave.Wave_read:
    return wave.open(io.BytesIO(base64.b64decode(output["data"])))


def test_samples_play_as_a_wav_as_loud_as_it_goes():
    out = json.loads(cells.run("audio([0, 0.25, 0, -0.5], 8000)\nprint('po')"))
    sound = next(o for o in out if o["type"] == "audio")
    w = _wav(sound)
    assert (w.getnchannels(), w.getframerate(), w.getnframes()) == (1, 8000, 4)
    assert min(int.from_bytes(w.readframes(4)[6:8], "little", signed=True), 0) == -32767


def test_rows_of_channels_play_in_stereo_and_a_file_plays_as_it_is(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    stereo = json.loads(cells.run("audio([[0, 1], [1, 0]], 44100)"))[0]
    assert _wav(stereo).getnchannels() == 2
    with open("dzwiek.wav", "wb") as f:
        f.write(base64.b64decode(stereo["data"]))
    played = json.loads(cells.run('audio("dzwiek.wav")'))[0]
    assert played["data"] == stereo["data"]


def test_a_file_python_wrote_is_offered_to_save(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = json.loads(cells.run('with open("wynik.txt", "w") as f:\n    f.write("42")\ndownload("wynik.txt")'))
    assert out == [{"type": "file", "name": "wynik.txt", "data": base64.b64encode(b"42").decode()}]
