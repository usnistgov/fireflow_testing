import re
import csv
import warnings
import pyreflow as pf
from typing import Any, NamedTuple
from pathlib import Path
from datetime import date
from common.config import (
    FCSConfig,
    RepoType,
    Machine,
    ALL_MACHINES,
    VendorId,
    MachineId,
)


class MachineMetadata(NamedTuple):
    repo: RepoType
    repo_id: str
    file_name: str
    vendor: str
    machine: Machine | None
    cyt: str | None
    cytsn: str | None
    sys: str | None
    software: str | None
    date: date | None


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

    machineid: MachineId | None = (
        conf.get_machine(core.cyt, parse.machine) if core.cyt != "" else parse.machine
    )
    vendorid = ALL_MACHINES[machineid].vendor if machineid is not None else None

    software = None
    if vendorid in [VendorId.BD, VendorId.CYTEK]:
        try:
            software = core.nonstandard_keywords["CREATOR"]
        except KeyError:
            pass
    elif vendorid in [VendorId.AGILENT]:
        try:
            software = core.nonstandard_keywords["#NCCreator"]
        except KeyError:
            pass
    elif machineid is MachineId.THERMO_ATTUNE:
        software = core.cyt
    elif machineid in [MachineId.BC_CYAN, MachineId.BC_XDP, MachineId.BC_ASTRIOS]:
        if core.sys is not None:
            software = core.sys.split(" / ")[0]
    elif vendorid in [VendorId.COULTER]:
        try:
            software = core.nonstandard_keywords["SWVER"]
        except KeyError:
            pass
    elif machineid is MachineId.BC_FC500:
        software = core.sys
    elif vendorid in [VendorId.SBT]:
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
        vendor=vendorid.value if vendorid is not None else "unknown",
        machine=ALL_MACHINES[machineid] if machineid is not None else None,
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
            "machine_type",
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
                    m.name if m is not None else "unknown",
                    r.software,
                    m.machine_type.value if m is not None else "unknown",
                    m.sorting if m is not None else "unknown",
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
