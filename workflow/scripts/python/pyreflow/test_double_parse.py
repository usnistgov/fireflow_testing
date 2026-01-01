from typing import Any
from pathlib import Path
import logging
from pyreflow.pydantic import PyreflowReadStdDatasetConfig

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def main(smk: Any) -> None:
    repo = smk.wildcards.repo
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    i_orig = Path(smk.input["original"])
    i_std = Path(smk.input["std"])
    o = Path(smk.output[0])
    fs = smk.config.test_files
    rconf = next(
        (
            c
            for c in fs
            if testname in c.src.file_names
            and id == (c.src.immport_id if repo == "immport" else c.src.fr_id)
        )
    )
    opts = rconf.options

    std_opts = PyreflowReadStdDatasetConfig(time_meas_pattern=opts.time_meas_pattern)

    core_orig, _ = opts.read_std_dataset(i_orig)
    core_orig.truncate_data(True)

    core_std, _ = std_opts.read_std_dataset(i_std)
    assert core_orig == core_std
    o.touch()


main(snakemake)  # type: ignore
