from typing import Any, NamedTuple
from pathlib import Path
import logging
from multiprocessing import Pool
from pyreflow.pydantic import PyreflowReadStdDatasetConfig
from common.config import FCSConfig


logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


class RunConfig(NamedTuple):
    conf: PyreflowReadStdDatasetConfig
    original: Path
    std: Path


def test_double_parse(r: RunConfig) -> None:
    conf = r.conf

    # alter the conf in the same was a test_read
    conf.allow_missing_time = "silent"

    std_opts = PyreflowReadStdDatasetConfig(
        time_meas_pattern=conf.time_meas_pattern,
        allow_other_feature=conf.allow_other_feature,
        allow_missing_time=conf.allow_missing_time,
    )

    try:
        core_orig, _ = conf.read_std_dataset(r.original)
        core_std, _ = std_opts.read_std_dataset(r.std)
        assert core_orig == core_std
    except Exception as e:
        msg = f"error for original '{r.original}' and std '{r.std}'"
        raise ExceptionGroup(msg, [e])


def main(smk: Any) -> None:
    sconf: FCSConfig = smk.config
    o = Path(smk.output[0])

    with open(smk.input["original"], "r") as f:
        original_paths = [Path(p.rstrip()) for p in f]

    with open(smk.input["std"], "r") as f:
        std_paths = [Path(p.rstrip()) for p in f]

    assert len(original_paths) == len(std_paths)

    runs = [
        RunConfig(sconf.find_file_options(o)[0].merged_conf, o, s)
        for o, s in zip(original_paths, std_paths)
    ]

    with Pool(smk.threads) as p:
        p.map(test_double_parse, runs)

    # make sentinal file to tell smk we won
    o.touch()


main(snakemake)  # type: ignore
