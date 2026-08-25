from datetime import datetime, timezone
import time


def test_video_compression_job_lifecycle(client, monkeypatch):
    manager = client.app.state.video_compression_manager

    def fake_compress(job):
        job.duration_seconds = 3.0
        job.progress = 50
        job.output_path.write_bytes(b"compressed-mp4")
        job.output_size = job.output_path.stat().st_size
        job.progress = 100
        job.status = "completed"
        job.token = "result-token"
        job.expires_at = datetime.now(timezone.utc).replace(year=2099)
        manager._tokens[job.token] = job.job_id

    monkeypatch.setattr(manager, "_compress", fake_compress)
    created = client.post(
        "/api/v1/video-compressions",
        files={"file": ("sample.mov", b"fake-video", "video/quicktime")},
        data={"preset": "balanced"},
    )
    assert created.status_code == 201
    job_id = created.json()["data"]["jobId"]

    body = None
    for _ in range(20):
        body = client.get(f"/api/v1/video-compressions/{job_id}").json()["data"]
        if body["status"] == "completed":
            break
        time.sleep(0.01)
    assert body is not None
    assert body["status"] == "completed"
    assert body["progress"] == 100
    download = client.get("/api/v1/video-compressions/results/result-token")
    assert download.status_code == 200
    assert download.content == b"compressed-mp4"


def test_video_compression_rejects_unsupported_extension(client):
    response = client.post(
        "/api/v1/video-compressions",
        files={"file": ("sample.avi", b"video", "video/x-msvideo")},
        data={"preset": "balanced"},
    )
    assert response.status_code == 415
    assert response.json()["code"] == "INVALID_VIDEO_FORMAT"


def test_video_compression_can_be_cancelled(client):
    manager = client.app.state.video_compression_manager
    job_id, path = manager.allocate_upload(".mp4")
    path.write_bytes(b"video")
    from app.services.video_compression import VideoCompressionOptions

    manager.register(job_id, path, "sample.mp4", VideoCompressionOptions("balanced"))
    response = client.delete(f"/api/v1/video-compressions/{job_id}")
    assert response.status_code == 204
    assert manager.get(job_id).status == "cancelled"
    assert not path.exists()
