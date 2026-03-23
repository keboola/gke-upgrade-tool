"""Simple parser for Terraform .tfvars files.

Reads key = value pairs and writes them back preserving
formatting, comments, blank lines, and alignment.
"""

import re

# Matches: key = "value" or key = value or key = true/false/number
_KV_PATTERN = re.compile(
    r'^(\s*)'           # leading whitespace
    r'([\w-]+)'         # key
    r'(\s*=\s*)'        # separator (preserves alignment)
    r'(.+?)'            # value
    r'(\s*(?:#.*)?)$'   # optional trailing comment
)


def read(filepath):
    """Parse a .tfvars file into an ordered dict of key->value,
    plus a list of raw lines for faithful rewriting.

    Returns (values_dict, lines) where:
    - values_dict: {key: string_value} (quotes stripped for string values)
    - lines: list of raw line strings (for write-back)
    """
    values = {}
    lines = []

    with open(filepath, "r", encoding="utf-8") as f:
        in_multiline = False
        for raw_line in f:
            line = raw_line.rstrip("\n")
            lines.append(line)

            if in_multiline:
                if line.strip() == "]":
                    in_multiline = False
                continue

            m = _KV_PATTERN.match(line)
            if m:
                key = m.group(2)
                raw_val = m.group(4).strip()

                # Detect multiline list values like [...\n
                if raw_val == "[" or (raw_val.startswith("[") and not raw_val.endswith("]")):
                    in_multiline = True
                    continue

                # Strip surrounding quotes
                if raw_val.startswith('"') and raw_val.endswith('"'):
                    values[key] = raw_val[1:-1]
                else:
                    values[key] = raw_val

    return values, lines


def write(filepath, values, lines):
    """Write a .tfvars file back, updating only changed values.

    Args:
        filepath: path to write
        values: dict of key->value (the modified values)
        lines: original lines list (from read())
    """
    output = []

    for line in lines:
        m = _KV_PATTERN.match(line)
        if m:
            key = m.group(2)
            if key in values:
                indent = m.group(1)
                separator = m.group(3)
                old_raw = m.group(4).strip()
                trailing = m.group(5)

                new_val = values[key]

                # Preserve quoting style
                if old_raw.startswith('"') and old_raw.endswith('"'):
                    new_raw = f'"{new_val}"'
                else:
                    new_raw = new_val

                output.append(f"{indent}{key}{separator}{new_raw}{trailing}")
                continue

        output.append(line)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(output) + "\n")
