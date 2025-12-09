import pyreflow as pf  # type: ignore
from typing import Any
from pathlib import Path
import logging

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def main(smk: Any):
    i = Path(smk.input[0])
    o = Path(smk.output["flag"])
    repo = smk.wildcards.repo
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    opts = next(
        (
            x["options"]
            for x in smk.config["test_files"][repo][id]
            if x["name"] == testname
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
    as_tup("promote_to_standard")
    as_tup("demote_from_standard")
    as_tup("supp_text_correction")
    as_tup("data_correction")
    as_tup("analysis_correction")
    as_tup("text_data_correction")
    as_tup("text_analysis_correction")

    try:
        key = "substitute_standard_key_values"
        x = opts[key]
        opts[key] = (
            {k: tuple(z for z in v) for k, v in x[0].items()},
            {k: tuple(z for z in v) for k, v in x[1].items()},
        )
    except KeyError:
        pass

    core, _ = pf.api.fcs_read_std_dataset(i, **opts)
    o.touch()
    core.write_dataset(smk.output["fcs"], skip_conversion_check=True)


main(snakemake)  # type: ignore
