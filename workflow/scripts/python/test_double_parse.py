import pyreflow as pf  # type: ignore
from typing import Any
from pathlib import Path
import logging

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def main(smk: Any):
    fr_id = smk.wildcards.fr_id
    testname = smk.wildcards.testname
    i_orig = Path(smk.input["original"])
    i_std = Path(smk.input["std"])
    o = Path(smk.output[0])
    opts = next(
        (x["options"] for x in smk.config["test_files"][fr_id] if x["name"] == testname)
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

    try:
        std_opts = {"time_meas_pattern": opts["time_meas_pattern"]}
    except KeyError:
        std_opts = {}

    core_orig, _ = pf.api.fcs_read_std_dataset(i_orig, **opts)
    core_orig.truncate_data(True)

    core_std, _ = pf.api.fcs_read_std_dataset(i_std, **std_opts)
    assert core_orig == core_std
    o.touch()


main(snakemake)  # type: ignore
