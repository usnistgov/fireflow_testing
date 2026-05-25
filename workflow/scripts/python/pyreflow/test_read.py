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

    # read and write dataset (this will fail if pyreflow does not know how to
    # parse this particular brand of FCS file)
    core, uncore = conf.read_std_dataset(i)
    core.write_dataset(smk.output["fcs"])

    # dump diagnostics to json blob for reuse alter
    with open(dump_out, "w") as f:
        dump = {"path": str(i), "diag": uncore.dict}
        json.dump(dump, f, default=encode_bytes)

    # make sentinel to indicate that everything worked
    flag_out.touch()


main(snakemake)  # type: ignore
