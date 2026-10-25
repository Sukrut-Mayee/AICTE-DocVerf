"""services/worker/pipeline.py end to end on two freshly rendered applications.

The second application's first lab photo is overwritten with the first's, so the shared duplicate
index must catch it. No OCR (both are digital PDFs), no VLM, no issuer: their URLs point at a
closed port, which exercises the degraded paths."""

import shutil

import pytest
from docverf.config import get_settings
from docverf.schemas import DocType
from docverf.synthetic.generate import generate_dataset
from docverf.synthetic.render import find_browser

from services.api.pipeline import PipelineRepository
from services.worker.pipeline import Run, _manifest, run

pytestmark = pytest.mark.skipif(find_browser() is None, reason="no Chrome / Edge to render PDFs")

CLOSED = "http://127.0.0.1:9"


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    out = tmp_path_factory.mktemp("synthetic")
    generate_dataset(out, n_apps=2)
    photo = {
        app: next(d for d in _manifest(out / app) if d.doc_type is DocType.LAB_PHOTO)
        for app in ("app001", "app002")
    }
    shutil.copyfile(out / "app001" / photo["app001"].path, out / "app002" / photo["app002"].path)
    return out, photo


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # ELA heatmaps go to ./data/out/forensics
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ledger.db'}")
    monkeypatch.setenv("MOCK_ISSUER_URL", CLOSED)
    monkeypatch.setenv("OLLAMA_URL", CLOSED)
    monkeypatch.setenv("ANCHOR_CONTRACT_ADDRESS", "")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_two_applications_end_to_end(synthetic, env):
    synthetic_dir, photo = synthetic
    out = env / "pipeline"
    assert run(synthetic_dir, out) == 0

    repo = PipelineRepository(out)
    for app_id in ("app001", "app002"):
        data = repo.load(app_id).data
        assert data.meta["source"] == "pipeline"
        assert data.meta["vlm"]["available"] is False
        assert data.meta["extraction"][f"{app_id}_land_deed"] == "text_layer"
        assert data.meta["extraction"][f"{app_id}_application_form"] == "portal_json"
        assert {d.doc_id for d in data.documents} == {
            d.doc_id for d in _manifest(synthetic_dir / app_id)
        }
        deed = next(e for e in data.extractions if e.doc_type is DocType.LAND_DEED)
        assert {"owner_name", "survey_no", "area"} <= set(deed.fields)
        assert data.audit is not None and data.audit.tx is None
        assert data.meta["anchor"]["anchored"] is False
        noc = next(c for c in data.checks if c.check == "issuer_lookup")
        assert noc.doc_id == f"{app_id}_noc" and noc.verification_status == "source_unavailable"

    first, second = (repo.load(a).data for a in ("app001", "app002"))
    assert not [f for f in first.findings if f.type == "duplicate"]
    duplicates = [f for f in second.findings if f.type == "duplicate"]
    assert len(duplicates) == 1
    assert duplicates[0].doc_ids == [photo["app002"].doc_id]
    assert duplicates[0].evidence["duplicate_of"] == {
        "app_id": "app001",
        "doc_id": photo["app001"].doc_id,
    }
    assert second.audit.seq > first.audit.seq  # one chain across applications


def test_subset_still_indexes_earlier_applications(synthetic, env):
    synthetic_dir, photo = synthetic
    out = env / "subset"
    assert run(synthetic_dir, out, apps=["app002"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["app002.json"]
    data = PipelineRepository(out).load("app002").data
    assert [f.doc_ids for f in data.findings if f.type == "duplicate"] == [[photo["app002"].doc_id]]


def test_one_failing_application_does_not_stop_the_run(synthetic, env, monkeypatch):
    synthetic_dir, _ = synthetic
    out = env / "failing"
    process = Run.process

    def flaky(self, app_id):
        if app_id == "app001":
            raise RuntimeError("simulated failure")
        return process(self, app_id)

    monkeypatch.setattr(Run, "process", flaky)
    assert run(synthetic_dir, out) == 1  # one failure -> non-zero exit in main()
    assert sorted(p.name for p in out.glob("*.json")) == ["app002.json"]
