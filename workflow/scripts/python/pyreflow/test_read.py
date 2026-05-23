from typing import Any
from pathlib import Path
import logging
from common.config import RepoType

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def main(smk: Any) -> None:
    i = Path(smk.input[0])
    o = Path(smk.output["flag"])
    repo = RepoType(smk.wildcards.repo)
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    opts = smk.config.find_file_options(repo, testname, id).options

    core, _ = opts.read_std_dataset(i)
    o.touch()
    core.write_dataset(smk.output["fcs"])


main(snakemake)  # type: ignore
