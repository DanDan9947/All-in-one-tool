from pathlib import Path

from app.config import Settings
from app.services.conversion_store import ConversionResultStore, safe_file_stem


def test_store_publishes_and_expires_result(work_dir):
    store = ConversionResultStore(work_dir / "conversions", ttl_seconds=-1)
    store.initialize()
    job_dir = store.create_job_dir()
    source = job_dir / "output.xlsx"
    source.write_bytes(b"xlsx")

    artifact = store.publish(source, 'bad<>:"name.pdf', "xlsx")

    assert artifact.file_name == "bad____name.xlsx"
    assert artifact.path.is_file()
    assert store.get(artifact.token) is None
    assert not artifact.path.exists()


def test_store_initialize_clears_only_managed_files(work_dir):
    root = work_dir / "conversions"
    root.mkdir()
    (root / "result-old.xlsx").write_bytes(b"old")
    (root / "keep.txt").write_bytes(b"keep")
    job = root / "job-old"
    job.mkdir()

    ConversionResultStore(root, ttl_seconds=30).initialize()

    assert not (root / "result-old.xlsx").exists()
    assert not job.exists()
    assert (root / "keep.txt").exists()


def test_safe_file_stem_has_fallback():
    assert safe_file_stem("...") == "converted"


def test_default_pdf_result_ttl_is_thirty_seconds():
    assert Settings().pdf_result_ttl_seconds == 30
