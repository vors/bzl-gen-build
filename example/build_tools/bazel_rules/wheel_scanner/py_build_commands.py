import sys
import json
import os
import zipfile

BATCH_SIZE = 2000

PRELUDE = """
#!/bin/bash

set -efo pipefail

set +x
trap 'echo ERROR in ${BASH_SOURCE[0]}, failed to run command, line with error: $LINENO' ERR

OUTPUT_BASE="$(bazel info output_base)"
"""
TEMPLATE = """

echo -n "Running scan of 3rdparty files in batches, working on batch {output_idx}, with {target_count} targets in it"

START_BATCH=$(date +%s)


set +e
bazel build {targets} \
  --aspects build_tools/bazel_rules/wheel_scanner/wheel_scanner.bzl%wheel_scanner_aspect \
  --output_groups=+wheel_scanner_out \
  --override_repository=external_build_tooling_gen=${{BZL_GEN_BUILD_TOOLS_PATH}} \
  --show_result=1000000 2> /tmp/cmd_out
RET=$?
if [ "$RET" != "0" ]; then
    cat /tmp/cmd_out
    exit $RET
fi

set +o pipefail
inner_idx=0
for f in `cat $OUTPUT_BASE/command.log |
  grep ".*\.json$" |
  sed -e 's/^[^ ]*//' |
  sed -e 's/^[^A-Za-z0-9/]*//' |
  sed 's/^ *//;s/ *$//'`; do
  if [ -f "$f" ]; then
    TARGET_PATH="${{BZL_BUILD_GEN_EXTERNAL_FILES_PATH}}/{output_idx}_${{inner_idx}}_wheel_scanner.json"
    cp $f $TARGET_PATH
    inner_idx=$((inner_idx + 1))
  fi
done

set -o pipefail
END_BATCH=$(date +%s)

echo "...complete in $(($END_BATCH-$START_BATCH)) seconds"
"""


def __transform_target(t):
    return "@%s//:pkg" % (t.lstrip("//external:"))

def write_command(file, output_idx, command_list):
    file.write(
        TEMPLATE.format(
            targets=" ".join([t for t in command_list if t.endswith("pkg")]),
            output_idx=output_idx,
            target_count=len(command_list),
        )
    )


if __name__ == "__main__":
    input_file = sys.argv[1]
    output_file_path = sys.argv[2]
    external_targets = []
    output_idx = 0
    with open(input_file, "r") as file1:
        with open(output_file_path, "w") as output_file:
            output_file.write(PRELUDE)
            for line in file1.readlines():
                external_targets.append(line.strip())
                if len(external_targets) > BATCH_SIZE:
                    write_command(output_file, output_idx, external_targets)
                    output_idx += 1
                    external_targets = []
            if len(external_targets) > 0:
                write_command(output_file, output_idx, external_targets)
                output_idx += 1
