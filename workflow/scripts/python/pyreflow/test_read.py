from typing import Any
from pathlib import Path
import logging

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def main(smk: Any) -> None:
    i = Path(smk.input[0])
    o = Path(smk.output["flag"])
    repo = smk.wildcards.repo
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    rconf = (
        smk.config.test_files.immport
        if repo == "immport"
        else smk.config.test_files.flow_repository
    )
    opts = next((x.options for x in rconf[id] if x.name == testname))

    core, _ = opts.read_std_dataset(i)
    o.touch()
    core.write_dataset(smk.output["fcs"], skip_conversion_check=True)


main(snakemake)  # type: ignore
