import os
from dotenv import load_dotenv

# Load env variables before importing our app
load_dotenv()

from app.services.llm_service import analyze_diff

def main():
    print("Loading sample_buggy_code.py...")
    try:
        with open("sample_buggy_code.py", "r") as f:
            file_content = f.read()
    except FileNotFoundError:
        print("Error: sample_buggy_code.py not found.")
        return

    # Simulate a git diff
    mock_diff = f"""
diff --git a/sample_buggy_code.py b/sample_buggy_code.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/sample_buggy_code.py
@@ -0,0 +1,18 @@
{chr(10).join(['+' + line for line in file_content.split(chr(10))])}
"""

    print("Simulated Diff Length:", len(mock_diff))
    print("Calling LLM Service for analysis...")
    
    try:
        response = analyze_diff(mock_diff)
        print("\n--- LLM ANALYSIS RESULTS ---")
        print("Summary:\n", response.summary)
        print("\nComments:")
        for comment in response.comments:
            print(f"- [{comment.issue_type}] {comment.file_path}:{comment.line_number}")
            print(f"  Comment: {comment.comment}")
            if comment.suggested_fix:
                print(f"  Suggested Fix:\n```python\n{comment.suggested_fix}\n```")
    except Exception as e:
        import tenacity
        if isinstance(e, tenacity.RetryError):
            print(f"Error during analysis: {e.last_attempt.exception()}")
        else:
            print(f"Error during analysis: {e}")

if __name__ == "__main__":
    main()
