import csv
import warnings
import pyreflow as pf
from typing import Any, NamedTuple
from pathlib import Path
from common.config import FCSConfig, RepoType


class Machine(NamedTuple):
    repo: str
    repo_id: str
    file_name: str
    cyt: str | None
    cytsn: str | None
    sys: str | None


def read_file(p: Path, conf: FCSConfig) -> Machine:
    testname = p.name
    repo = RepoType(p.parent.parent.name)
    id = p.parent.name
    opts = conf.find_file_options(repo, testname, id)

    core, _ = opts.to_std_text_config().read_std_text(p)

    if isinstance(core, pf.CoreTEXT2_0):
        cytsn = None
    else:
        cytsn = core.cytsn

    return Machine(
        repo=repo,
        repo_id=id,
        file_name=testname,
        cyt=core.cyt,
        cytsn=cytsn,
        sys=core.sys,
    )


def main(smk: Any) -> None:
    o = Path(smk.output["machine_table"])

    warnings.simplefilter("ignore")

    with open(o, "w") as f:
        w = csv.writer(f, delimiter="\t")

        w.writerow([*Machine._fields])
        for i in smk.input:
            p = Path(i)
            result = read_file(p, smk.config)
            w.writerow([*result])


main(snakemake)  # type: ignore
