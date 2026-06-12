import re

def parse_diff_positions(diff_text: str) -> dict:
    """
    Parses a standard Git diff patch text and extracts valid line positions
    that the GitHub PR Review Comment API accepts.
    Maps: (filename, file_line_number) -> webhook_diff_position_index
    """
    file_mappings = {}
    current_file = None
    
    lines = diff_text.splitlines()
    diff_position_index = 0
    current_file_line = 0

    for line in lines:
        # Track file name switches
        if line.startswith("+++ b/"):
            current_file = line[6:]
            file_mappings[current_file] = {}
            diff_position_index = 0
            continue
            
        if current_file is None:
            continue

        # Track hunk headers: @@ -old_start,old_len +new_start,new_len @@
        hunk_match = re.match(r"^@@ -\d+,\d+ \+(\d+),\d+ @@", line)
        if hunk_match:
            current_file_line = int(hunk_match.group(1)) - 1
            diff_position_index += 1
            continue

        # Increment diff index positions for contents inside hunks
        if line.startswith("+") or line.startswith("-") or line.startswith(" "):
            diff_position_index += 1
            if not line.startswith("-"):
                current_file_line += 1
            if line.startswith("+"):
                # Map the actual destination line to the position index inside the git diff patch
                file_mappings[current_file][current_file_line] = diff_position_index

    return file_mappings
