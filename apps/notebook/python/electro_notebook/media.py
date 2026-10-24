"""A cell's sound and files: ``audio`` plays a signal (or a WAV file) under the cell, ``download`` offers a file
Python wrote (it lives only as long as the page) to be saved."""

from __future__ import annotations

import array
import base64
import io
import os
import wave


def audio(data, rate: int | None = None) -> dict:
    """A player under the cell: ``data`` a file's name (a WAV) or samples at ``rate`` per second — a list or an
    array, of a channel, or rows of channels (as ``wavfile.read`` gives them) — made as loud as it goes."""
    if isinstance(data, str | os.PathLike):
        with open(data, "rb") as f:
            return {"type": "audio", "data": base64.b64encode(f.read()).decode()}
    if rate is None:
        raise ValueError("audio(samples, rate): how many samples a second")
    channels, frames = _frames(data)
    peak = max((abs(v) for v in frames), default=0.0) or 1.0
    pcm = array.array("h", (round(v / peak * 32767) for v in frames))
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(pcm.tobytes())
    return {"type": "audio", "data": base64.b64encode(out.getvalue()).decode()}


def _frames(data) -> tuple[int, list[float]]:
    """The channels, and the samples one frame after another (each frame its channels in turn)."""
    rows = data.tolist() if hasattr(data, "tolist") else list(data)
    if rows and isinstance(rows[0], list | tuple):
        return len(rows[0]), [float(v) for row in rows for v in row]
    return 1, [float(v) for v in rows]


def download(name: str) -> dict:
    """A file Python wrote (``wavfile.write("out.wav", …)``), to be saved from under the cell."""
    with open(name, "rb") as f:
        data = f.read()
    return {"type": "file", "name": os.path.basename(name), "data": base64.b64encode(data).decode()}
