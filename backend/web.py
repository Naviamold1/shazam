from backend.recognizer import SongCandidate, SongRecognizer, _handle_recorded_audio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

with open("backend/index.html", "r") as f:
    HTML = f.read()

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


@app.websocket("/ws")
async def send(websocket: WebSocket):
    await websocket.accept()
    recognizer = SongRecognizer()
    try:
        while True:
            data = await websocket.receive_bytes()
            print("received data!")
            path = _handle_recorded_audio(data)
            try:
                candidates = recognizer.recognize_file(path)
            finally:
                path.unlink(missing_ok=True)

            await websocket.send_json(
                {
                    "type": "match",
                    "candidates": [_candidate_to_json(candidate) for candidate in candidates],
                }
            )
    except WebSocketDisconnect:
        print("websocket disconnected")


def _candidate_to_json(candidate: SongCandidate):
    return {
        "song_id": candidate.song_id,
        "title": candidate.title,
        "votes": candidate.votes,
        "confidence": candidate.confidence,
        "offset": candidate.offset,
    }
