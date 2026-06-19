import shlex
from pathlib import Path

import pytest
from click.testing import CliRunner

from netlist_crawler.cli import main


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _readme_cli_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    for line in README.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("netlist-crawler "):
            commands.append(shlex.split(stripped)[1:])
    return commands


README_COMMANDS = _readme_cli_commands()


def _redirect_repo_outputs(args: list[str], tmp_path: Path) -> list[str]:
    redirected = list(args)
    for flag in ("-o", "--output"):
        if flag not in redirected:
            continue
        index = redirected.index(flag)
        if index + 1 < len(redirected):
            redirected[index + 1] = str(tmp_path / Path(redirected[index + 1]).name)
    return redirected


@pytest.mark.parametrize(
    "args",
    README_COMMANDS,
    ids=lambda args: " ".join(args),
)
def test_readme_netlist_crawler_commands_stay_runnable(args: list[str], tmp_path: Path) -> None:
    assert README_COMMANDS, "README should document at least one netlist-crawler command"

    result = CliRunner().invoke(main, _redirect_repo_outputs(args, tmp_path))

    assert result.exit_code == 0, result.output
