Testing environment for [fireflow](https://github.com/usnistgov/fireflow).

The main purpose (so far) is to verify that `fireflow` has support for opening a
large variety of files conveniently (that is, by only using configuration flags
to repair non-compliance).

Note that data integrity (that is, ensuring that the data in the file is the
same data that is actually presented) is at least partly covered by the unit
tests in `fireflow` itself.

# Obtaining files

See [the config](config/config.yml) for a list of all files currently being
tested. Under `test_files`, the next layer of keys correspond to Flow Repository
(FR) IDs, and the layer of keys under this correspond to file names in each FR
dataset. Each FR dataset must be obtained manually and unzipped into
`resources/fcs/<FR_ID>` with the listed FCS files in the root of this directory.

# Running pipeline

Ensure you have `mamba` (or `conda` for the patient) installed.

Clone this repo and navigate to the root. Run the following:

``` bash
mamba env create -f env.yml
```

Then run the pipeline:


``` bash
snakemake -c 20 --use-conda --configfile=config/config.yml all
```

# Interpreting results

Any files that "fail" parsing will produce a failed snakemake job. This means
that they would not be fully standardized given the data they contain and the
provided options.

A list of all tested machines with their serial numbers and software can be seen
at `results/reports/machines.tsv`.

Files which have been standardized can be viewed at `results/read_test/fcs`.
Each of these should be identical to the original except that every
non-compliant issue has been fixed.

# Limitations

Flow Repository is currently quite finicky and not permitting downloads. Will
likely switch to ImmPort after figuring out their API.
