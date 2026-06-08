from typing import Any
from pathlib import Path
import logging
from pyreflow.pydantic import PyreflowReadStdDatasetConfig
from common.config import RepoType

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def main(smk: Any) -> None:
    i_orig = Path(smk.input["original"])
    i_std = Path(smk.input["std"])
    o = Path(smk.output[0])

    repo = RepoType(smk.wildcards.repo)
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    conf = smk.config.find_file_options(repo, testname, id).merged_conf
    opts = smk.config.find_file_options(repo, testname, id).options

    std_opts = PyreflowReadStdDatasetConfig(
        time_meas_pattern=opts.time_meas_pattern,
        allow_other_feature=opts.allow_other_feature,
        nonstandard_measurement_pattern=opts.nonstandard_measurement_pattern,
    )

    core_orig, _ = conf.read_std_dataset(i_orig)

    core_std, _ = std_opts.read_std_dataset(i_std)
    assert core_orig == core_std
    o.touch()


main(snakemake)  # type: ignore
