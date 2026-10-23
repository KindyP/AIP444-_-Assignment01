import os
import subprocess
from pathlib import Path
from ripgrepy import Ripgrepy

def read_file(file_path: str, start_line: int = None, end_line: int = None) -> str:
    """Reads a local file from disk using standard library only, with optional line boundaries."""
    path = Path(file_path)
    if not path.exists():
        return f"Error: File {file_path} not found."
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Handle line slicing
        total_lines = len(lines)
        if start_line is not None or end_line is not None:
            start = max(0, (start_line - 1) if start_line else 0)
            end = min(total_lines, end_line if end_line else total_lines)
            lines = lines[start:end]
            
        content = "".join(lines)
        # Optional safeguard for massive files to preserve token limits
        if len(content) > 15000:
            content = content[:15000] + "\n... [File truncated due to size]"
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

def run_ripgrep(search_pattern: str, path: str = ".") -> str:
    """Wraps ripgrep to search the codebase recursively."""
    try:
        rg = Ripgrepy(search_pattern, path)
        results = rg.run().as_dict.get("matches", [])
        
        output = []
        for match in results:
            file_name = match.get("file", {}).get("text")
            line_num = match.get("line_number")
            line_text = match.get("lines", {}).get("text", "").strip()
            output.append(f"{file_name}:{line_num}: {line_text}")
            
        if not output:
            return f"No matches found for pattern: {search_pattern}"
        
        # Truncate if results are overwhelmingly large
        result_str = "\n".join(output)
        if len(result_str) > 10000:
            result_str = result_str[:10000] + "\n... [Results truncated]"
        return result_str
    except Exception as e:
        # Fallback to standard subprocess if ripgrepy fails
        try:
            res = subprocess.run(["rg", search_pattern, path], capture_output=True, text=True, timeout=5)
            return res.stdout if res.stdout else f"No matches or error: {res.stderr}"
        except Exception as sub_e:
            return f"Ripgrep execution failed: {str(sub_e)}"
