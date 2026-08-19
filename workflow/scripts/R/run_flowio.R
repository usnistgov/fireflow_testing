suppressMessages(library(devtools))
suppressMessages(library(tidyverse))
library(future)                                                                                                                                                                                                    
library(furrr) 

## shortened versions of the checks from flowIO, see the source and README for
## full explanation of what is being checked
CHECK_NAMES <- c(
    "header_fmt",
    "offsets",
    "allowed_chars",
    "duplicity",
    "req_keywords",
    "std_keywords",
    "nonempty",
    "numeric_fmt",
    "keyword_comply"
)

# run flowIO checks on a single path and spit out a boolean array
#
# note, fail -> TRUE
run_check <- function(path) {
  chckAllFCS(path, pass_msg = FALSE, fail_msg = TRUE)[[1]]$result
}

plan(multicore, workers = snakemake@threads)

load_all(snakemake@input[["flowio"]])

files <- read_tsv(snakemake@input[["files"]], col_type = "c", col_names = "filepath") %>%
  pull(filepath)


# flowIO will automatically fail for 3.2 since it predates this version and
# automatically rejects what it thinks is a bad FCS file. Also, it will hang for
# a very long time on FACSDiscover files which have massive TEXT sections. Not
# worth it. Just cut these out (hmm, I kinda sound like Claude)
is_3_2 <- files %>%
  map_lgl(\(f) readChar(f, nchar = 6) == "FCS3.2")

files_not_3_2 <- files[!is_3_2]

results <- files_not_3_2 %>%
  future_map(
    \(f) tryCatch(run_check(f), error = \(e) e$message)
  )

error_mask <- map_lgl(results, is.character)

checks <- do.call(rbind, results[!error_mask])
colnames(checks) <- CHECK_NAMES

df_fail <- tibble(
  filepath = files_not_3_2[error_mask],
  error = unlist(results[error_mask]) %>%
    str_trim() %>%
    str_replace_all("\\n", "\\\\n") %>%
    str_replace_all("\\t", "\\\\t")
)

df_3_2 <- tibble(filepath = files[is_3_2]) %>%
  add_column(unparsable = FALSE) %>%
  add_column(is_3_2 = TRUE)

df_pass <- as_tibble(checks) %>%
  add_column(filepath = files_not_3_2[!error_mask]) %>%
  add_column(unparsable = FALSE) %>%
  add_column(is_3_2 = FALSE) %>%
  relocate(filepath)

df_all <- df_pass %>%
  bind_rows(
    df_fail %>%
      add_column(unparsable = TRUE) %>%
      add_column(is_3_2 = FALSE) %>%
      select(-error)
  ) %>%
  bind_rows(df_3_2) %>%
  mutate(across(-filepath, \(x) if_else(is.na(x), FALSE, x)))

df_all %>%
  write_tsv(snakemake@output[["results"]])

df_fail %>%
  write_tsv(snakemake@output[["errors"]])
