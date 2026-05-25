import base64
import json
from typing import Any
from pathlib import Path
import logging
from pyreflow.api import fcs_write_datasets
from common.config import RepoType

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def encode_bytes(obj: Any) -> str:
    if isinstance(obj, bytes):
        return "base64:" + base64.b64encode(obj).decode("ascii")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def main(smk: Any) -> None:
    fcs_path = Path(smk.input[0])
    flag_out = Path(smk.output["flag"])
    dump_out = Path(smk.output["dump"])
    repo = RepoType(smk.wildcards.repo)
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    conf = smk.config.find_file_options(repo, testname, id).merged_conf

    # read and write dataset (this will fail if pyreflow does not know how to
    # parse this particular brand of FCS file)
    datasets = conf.read_std_datasets(fcs_path)
    cores = [d[0] for d in datasets]
    uncores = [d[1] for d in datasets]
    fcs_write_datasets(smk.output["fcs"], cores)

    # dump diagnostics to json blob for reuse alter
    with open(dump_out, "w") as f:
        dump = [
            {"path": str(fcs_path), "dataset": dataset_index, "diag": u.dict}
            for dataset_index, u in enumerate(uncores)
        ]
        json.dump(dump, f, default=encode_bytes)

    # make sentinel to indicate that everything worked
    flag_out.touch()


main(snakemake)  # type: ignore
