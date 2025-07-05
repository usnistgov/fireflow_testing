import pyreflow as pf  # type: ignore
from typing import Any
from pathlib import Path
import warnings
import logging

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


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
        opts["replace_standard_key_values"] = [
            (str(x[0]), str(x[1])) for x in opts["replace_standard_key_values"]
        ]
    except KeyError:
        pass

    def as_tup(key: str):
        try:
            x = opts[key]
            opts[key] = (x[0], x[1])

        except KeyError:
            pass

    as_tup("prim_text_correction")
    as_tup("supp_text_correction")
    as_tup("data_correction")
    as_tup("analysis_correction")
    as_tup("text_data_correction")
    as_tup("text_analysis_correction")

    pf.fcs_read_std_dataset(i, **opts)
    o.touch()


main(snakemake)  # type: ignore
