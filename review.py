import argparse
import asyncio
import sys
import os
import subprocess
from datetime import datetime
from openai import OpenAI

api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")

# Stop early if the key is missing or empty
if not api_key or api_key.strip() == "":
    print("Error: OPENROUTER_API_KEY is not set or empty.", file=sys.stderr)
    print("Please set it in your terminal session:", file=sys.stderr)
    print("  PowerShell: $env:OPENROUTER_API_KEY='sk-or-v1-...'", file=sys.stderr)
    print("  CMD:        set OPENROUTER_API_KEY=sk-or-v1-...", file=sys.stderr)
    sys.exit(1)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key.strip(),
)

def log_debug(message: str, debug_mode: bool):
    """Prints verbose debugging logs strictly to stderr as required."""
    if debug_mode:
        print(f"[DEBUG] {datetime.now().strftime('%H:%M:%S')} - {message}", file=sys.stderr)

def get_git_diff() -> str:
    """Retrieves staged git changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--staged"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e}", file=sys.stderr)
        sys.exit(1)

async def run_reviewer(name: str, system_prompt: str, code_input: str, debug_mode: bool):
    """Executes a single parallel reviewer model call."""
    log_debug(f"[{name}] Starting review analysis...", debug_mode)
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",  # Example fast, cost-effective model on OpenRouter
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Please review the following code/diff:\n\n{code_input}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        raw_json = response.choices[0].message.content
        log_debug(f"[{name}] Finished review. Raw JSON response received.", debug_mode)
        return raw_json
    except Exception as e:
        log_debug(f"[{name}] Error during execution: {str(e)}", debug_mode)
        return "{}"

async def main():
    parser = argparse.ArgumentParser(description="AI Code Review CLI Tool")
    parser.add_argument("--file", type=str, help="Review a specific file instead of git staged changes")
    parser.add_argument("--debug", action="store_true", help="Enable Debug Mode")
    parser.add_argument("--output", type=str, help="Custom output filename for HTML report")
    args = parser.parse_args()

    # 1. Input Handling
    if args.file:
        log_debug(f"Running in File Mode targeting: {args.file}", args.debug)
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            code_input = f.read()
    else:
        log_debug("Running in Git Mode (checking staged changes)...", args.debug)
        code_input = get_git_diff()
        if not code_input:
            print("No staged changes found to review. Stage changes using 'git add' first.", file=sys.stderr)
            sys.exit(0)

    # 2. Define Persona Prompts (Example: Security Auditor & Maintainability Critic)
    security_prompt = """You are a paranoid, strict Security Auditor. Scan the code for vulnerabilities, hardcoded secrets, and dangerous logic. 
    You MUST output valid JSON containing an array of issues under the key 'issues', with each item structured as:
    {"path": "string", "line": int, "severity": "info|warn|critical", "category": "security", "issue": "description"}"""

    maintainability_prompt = """You are an obsessive Maintainability Critic focused on Clean Code, DRY, and naming.
    You MUST output valid JSON containing an array of issues under the key 'issues', with each item structured as:
    {"path": "string", "line": int, "severity": "info|warn|critical", "category": "style", "issue": "description"}"""

    # 3. Phase 1: Parallel Reviews using asyncio.gather
    log_debug("Initiating Phase 1: Running parallel reviewer assistants...", args.debug)
    reviewer1_result, reviewer2_result = await asyncio.gather(
        run_reviewer("SecurityAuditor", security_prompt, code_input, args.debug),
        run_reviewer("MaintainabilityCritic", maintainability_prompt, code_input, args.debug)
    )

    log_debug("Reviewer 1 Raw JSON:\n" + reviewer1_result, args.debug)
    log_debug("Reviewer 2 Raw JSON:\n" + reviewer2_result, args.debug)

    # 4. Phase 2: Lead Developer (Judge) Synthesis & HTML Generation
    log_debug("Initiating Phase 2: Lead Developer synthesis and HTML report compilation...", args.debug)
    
    judge_prompt = """You are the Lead Developer / Judge. Review the JSON reports from the two review assistants, 
    de-duplicate overlapping issues, filter out hallucinations, and synthesize them into a single comprehensive HTML report 
    (complete with internal CSS styling, a clean modern look, and clear badges for severity levels). 
    Return ONLY the raw HTML string."""

    judge_response = client.chat.completions.create(
        model="openai/gpt-4o",  # Higher capability model for synthesis and formatting
        messages=[
            {"role": "system", "content": judge_prompt},
            {"role": "user", "content": f"Original Code/Diff:\n{code_input}\n\nReviewer 1 Report:\n{reviewer1_result}\n\nReviewer 2 Report:\n{reviewer2_result}"}
        ],
        temperature=0.3
    )

    html_content = judge_response.choices[0].message.content

    # Clean markdown code blocks if the LLM wrapped the HTML in them
    if html_content.startswith("```html"):
        html_content = html_content.split("```html")[1]
    if html_content.endswith("```"):
        html_content = html_content.rsplit("```", 1)[0]
    html_content = html_content.strip()

    # 5. Output Generation
    output_filename = args.output
    if not output_filename:
        timestamp = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        output_filename = f"review-{timestamp}.html"

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Review successfully completed! HTML report saved to: {output_filename}")

if __name__ == "__main__":
    asyncio.run(main())