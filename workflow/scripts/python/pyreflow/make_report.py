import pyreflow as pf
from typing import Any, NamedTuple
from pathlib import Path
import csv
import warnings
from common.config import FCSConfig


class Machine(NamedTuple):
    repo: str
    repo_id: str
    file_name: str
    cyt: str | None
    cytsn: str | None
    sys: str | None


def read_file(p: Path, conf: FCSConfig) -> Machine:
    testname = p.name
    repo = p.parent.parent.name
    id = p.parent.name

    rconf = (
        conf.test_files.immport
        if repo == "immport"
        else conf.test_files.flow_repository
    )
    opts = next((x.options for x in rconf[id] if x.name == testname))

    core, _ = opts.read_std_text(p)

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
