import csv
import warnings
import pyreflow as pf
from typing import Any, NamedTuple
from pathlib import Path
from common.config import FCSConfig, RepoType, Machine, VendorName


class MachineMetadata(NamedTuple):
    repo: RepoType
    repo_id: str
    file_name: str
    vendor: VendorName
    machine: Machine
    cyt: str | None
    cytsn: str | None
    sys: str | None


def read_file(p: Path, conf: FCSConfig) -> MachineMetadata:
    testname = p.name
    repo = RepoType(p.parent.parent.name)
    id = p.parent.name
    parse = conf.find_file_options(repo, testname, id)
    opts = parse.options

    core, _ = opts.to_std_text_config().read_std_text(p)

    if isinstance(core, pf.CoreTEXT2_0):
        cytsn = None
    else:
        cytsn = core.cytsn

    machine = (
        conf.get_machine(core.cyt, parse.machine)
        if core.cyt != ""
        else (conf.machines[parse.machine] if parse.machine is not None else None)
    )
    assert machine is not None, f"could not find machine for {core.cyt} for {p}"
    vendor = conf.vendors[machine.vendor]

    return MachineMetadata(
        repo=repo,
        repo_id=id,
        file_name=testname,
        cyt=core.cyt,
        cytsn=cytsn,
        sys=core.sys,
        vendor=vendor,
        machine=machine,
    )


def main(smk: Any) -> None:
    o = Path(smk.output["machine_table"])

    warnings.simplefilter("ignore")

    with open(o, "w") as f:
        w = csv.writer(f, delimiter="\t")

        header = [
            "vendor",
            "machine",
            "spectral",
            "imaging",
            "sorting",
            "$CYT",
            "$CYTSN",
            "$SYS",
            "repo_type",
            "repo_id",
            "file_name",
        ]

        w.writerow(header)
        for i in smk.input:
            p = Path(i)
            r = read_file(p, smk.config)
            m = r.machine
            w.writerow(
                [
                    r.vendor,
                    m.name,
                    m.spectral,
                    m.imaging,
                    m.sorting,
                    r.cyt,
                    r.cytsn,
                    r.sys,
                    r.repo.value,
                    r.repo_id,
                    r.file_name,
                ]
            )


main(snakemake)  # type: ignore
