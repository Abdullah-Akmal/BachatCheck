import pytest

from ingestion.cli import main


def test_list_runs() -> None:
    assert main(["list"]) == 0


def test_unknown_source_exits_2() -> None:
    assert main(["run", "nope"]) == 2


def test_requires_command() -> None:
    with pytest.raises(SystemExit):
        main([])
