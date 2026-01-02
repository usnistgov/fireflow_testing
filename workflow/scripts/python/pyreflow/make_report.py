import re
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
    software: str | None
    date: str | None


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

    mres = (
        conf.get_machine(core.cyt, parse.machine)
        if core.cyt != ""
        else (
            (parse.machine, conf.machines[parse.machine])
            if parse.machine is not None
            else None
        )
    )
    assert mres is not None, f"could not find machine for {core.cyt} for {p}"
    machineid = mres[0]
    machine = mres[1]
    vendor = conf.vendors[machine.vendor]

    software = None
    if machine.vendor in ["bd", "cytek"]:
        try:
            software = core.nonstandard_keywords["CREATOR"]
        except KeyError:
            pass
    elif machine.vendor in ["at"]:
        try:
            software = core.nonstandard_keywords["#NCCreator"]
        except KeyError:
            pass
    elif machineid == "tfs_attune":
        software = core.cyt
    elif machineid in ["bc_cyan", "bc_xdp", "bc_astrios"]:
        if core.sys is not None:
            software = core.sys.split(" / ")[0]
    elif machine.vendor in ["bc"]:
        try:
            software = core.nonstandard_keywords["SWVER"]
        except KeyError:
            pass
    elif machineid == "bc_fc500":
        software = core.sys
    elif machineid in ["sbt_helios", "sbt_cytof2", "sbt_cytof1"]:
        if (
            core.cyt is not None
            and re.search("[0-9]+\\.[0-9]+\\.[0-9]+", core.cyt) is not None
        ):
            software = core.cyt

    return MachineMetadata(
        repo=repo,
        repo_id=id,
        file_name=testname,
        cyt=core.cyt,
        cytsn=cytsn,
        sys=core.sys,
        vendor=vendor,
        machine=machine,
        software=software,
        date=core.date,
    )


def main(smk: Any) -> None:
    o = Path(smk.output["machine_table"])

    warnings.simplefilter("ignore")

    with open(o, "w") as f:
        w = csv.writer(f, delimiter="\t")

        header = [
            "vendor",
            "machine",
            "software",
            "spectral",
            "imaging",
            "sorting",
            "$DATE",
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
                    r.software,
                    m.spectral,
                    m.imaging,
                    m.sorting,
                    r.date,
                    r.cyt,
                    r.cytsn,
                    r.sys,
                    r.repo.value,
                    r.repo_id,
                    r.file_name,
                ]
            )


main(snakemake)  # type: ignore
