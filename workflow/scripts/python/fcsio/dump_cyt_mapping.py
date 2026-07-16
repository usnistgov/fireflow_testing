from typing import Any
from common.config import ALL_MACHINES


def main(smk: Any) -> None:
    with open(smk.output[0], "w") as f:
        header = ["vendor", "machine", "$CYT"]
        f.write("\t".join(header) + "\n")
        for mi, m in ALL_MACHINES.items():
            for c in m.cyt_values:
                f.write("\t".join([m.vendor.value, m.name, c]) + "\n")


main(snakemake)  # type: ignore
