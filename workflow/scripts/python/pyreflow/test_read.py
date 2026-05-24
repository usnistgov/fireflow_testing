import base64
import json
from typing import Any
from pathlib import Path
import logging
from common.config import RepoType

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def encode_bytes(obj: Any) -> str:
    if isinstance(obj, bytes):
        return "base64:" + base64.b64encode(obj).decode("ascii")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def main(smk: Any) -> None:
    i = Path(smk.input[0])
    flag_out = Path(smk.output["flag"])
    dump_out = Path(smk.output["dump"])
    repo = RepoType(smk.wildcards.repo)
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    conf = smk.config.find_file_options(repo, testname, id).merged_conf

    core, uncore = conf.read_std_dataset(i)
    flag_out.touch()
    core.write_dataset(smk.output["fcs"])

    with open(dump_out, "w") as f:
        json.dump(uncore.dict, f, default=encode_bytes)


main(snakemake)  # type: ignore
