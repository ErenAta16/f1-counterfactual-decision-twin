from apexmind.paths import DataPaths


def test_data_paths_create_local_storage(tmp_path) -> None:
    paths = DataPaths.from_root(tmp_path / "research-data")

    paths.create()

    assert paths.fastf1_cache.is_dir()
    assert paths.processed.is_dir()
    assert paths.manifests.is_dir()
    assert paths.quality_reports.is_dir()
    assert paths.evaluation_reports.is_dir()
    assert paths.simulation_reports.is_dir()
    assert paths.decision_reports.is_dir()
