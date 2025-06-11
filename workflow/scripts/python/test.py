import pyreflow as pf  # type: ignore
from typing import Any
from pathlib import Path


def main(smk: Any):
    i = Path(smk.input[0])
    o = Path(smk.output[0])
    opts = next(
        (
            x["options"]
            for x in smk.config["test_files"]
            if x["name"] == smk.wildcards.testname
        )
    )
    try:
        vo = None
        match opts["version_override"]:
            case "FCS2.0":
                vo = pf.Version.FCS2_0
            case "FCS3.0":
                vo = pf.Version.FCS3_0
            case "FCS3.1":
                vo = pf.Version.FCS3_1
            case "FCS3.2":
                vo = pf.Version.FCS3_2
            case _:
                assert False, "invalid version"

        opts["version_override"] = vo
    except KeyError:
        pass

    try:
        x = opts["text_data_correction"]
        opts["text_data_correction"] = (x[0], x[1])
    except KeyError:
        pass

    try:
        x = opts["data_correction"]
        opts["data_correction"] = (x[0], x[1])
    except KeyError:
        pass

    pf.fcs_read_std_dataset(i, **opts)
    o.touch()


main(snakemake)  # type: ignore
