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

    def as_tup(key: str):
        try:
            x = opts[key]
            opts[key] = (x[0], x[1])

        except KeyError:
            pass

    as_tup("text_correction")
    as_tup("ignore_standard_keys")
    as_tup("supp_text_correction")
    as_tup("data_correction")
    as_tup("analysis_correction")
    as_tup("text_data_correction")
    as_tup("text_analysis_correction")

    pf.fcs_read_std_dataset(i, **opts)
    o.touch()


main(snakemake)  # type: ignore
