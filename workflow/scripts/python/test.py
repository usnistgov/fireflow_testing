import pyreflow as pf  # type: ignore
from typing import Any
from pathlib import Path


def main(smk: Any):
    i = Path(smk.input[0])
    o = Path(smk.output[0])
    pf.py_read_fcs_raw_text(i)
    o.touch()


main(snakemake)  # type: ignore
