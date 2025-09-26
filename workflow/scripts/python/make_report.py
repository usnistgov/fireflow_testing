import pyreflow as pf
from typing import Any, NamedTuple
from pathlib import Path
import csv
import warnings


class Machine(NamedTuple):
    fr_id: str
    file_name: str
    cyt: str | None
    cytsn: str | None
    sys: str | None


def read_file(p: Path, conf: Any) -> Machine:
    testname = p.name
    fr_id = p.parent.name
    opts = next(
        (x["options"] for x in conf["test_files"][fr_id] if x["name"] == testname)
    )

    def as_tup(key: str):
        try:
            x = opts[key]
            opts[key] = (x[0], x[1])

        except KeyError:
            pass

    as_tup("text_correction")
    as_tup("ignore_standard_keys")
    as_tup("promote_to_standard")
    as_tup("demote_from_standard")
    as_tup("supp_text_correction")
    as_tup("data_correction")
    as_tup("analysis_correction")
    as_tup("text_data_correction")
    as_tup("text_analysis_correction")

    core, _ = pf.api.fcs_read_std_text(p, **opts)

    if isinstance(core, pf.CoreTEXT2_0):
        cytsn = None
    else:
        cytsn = core.cytsn

    return Machine(
        fr_id=fr_id,
        file_name=testname,
        cyt=core.cyt,
        cytsn=cytsn,
        sys=core.sys,
    )


def main(smk: Any):
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
