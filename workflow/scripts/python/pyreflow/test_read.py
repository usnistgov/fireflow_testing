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
    fs = smk.config.test_files
    rconf = next(
        (
            c
            for c in fs
            if testname in c.src.file_names
            and id == (c.src.immport_id if repo == "immport" else c.src.fr_id)
        ),
    )

    core, _ = rconf.options.read_std_dataset(i)
    o.touch()
    core.write_dataset(smk.output["fcs"], skip_conversion_check=True)


main(snakemake)  # type: ignore
