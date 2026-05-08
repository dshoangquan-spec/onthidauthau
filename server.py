#!/usr/bin/env python3
"""Local proxy server: Browser -> NotebookLM query -> Return answer.
   Start with: python3 server.py
   Then open index.html (or the GitHub Pages URL) and click 'Xem giai thich'.
"""

import json
import subprocess
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

NOTEBOOKLM_DIR = os.path.expanduser("~/.claude/skills/notebooklm")
NOTEBOOK_ID = "luật-đấu-thầu-&-mua-sắm-y-tế"
PORT = 8765

class ExplainHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/explain":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except:
            self.send_json({"error": "Invalid JSON"}, 400)
            return

        question = data.get("question", "")
        correct = data.get("correct_answer", "")
        if not question:
            self.send_json({"error": "Missing question"}, 400)
            return

        prompt = (
            f"Câu hỏi: {question}\n"
            f"Đáp án đúng: {correct}\n\n"
            "Hãy giải thích ngắn gọn tại sao đáp án này đúng, "
            "trích dẫn ĐIỀU KHOẢN CỤ THỂ (Điều X, Khoản Y) từ các văn bản pháp luật trong tài liệu. "
            "Trả lời bằng tiếng Việt, không quá 200 từ."
        )

        print(f"\n📤 Querying NotebookLM: {question[:80]}...")
        try:
            result = subprocess.run(
                ["python3", "scripts/run.py", "ask_question.py",
                 "--question", prompt,
                 "--notebook-id", NOTEBOOK_ID],
                cwd=NOTEBOOKLM_DIR,
                capture_output=True, text=True, timeout=120
            )

            output = result.stdout
            # Extract the answer from the script output
            answer = self.extract_answer(output)
            if not answer:
                answer = output.strip()[-2000:]  # fallback

            print(f"✅ Got answer ({len(answer)} chars)")
            self.send_json({"answer": answer})

        except subprocess.TimeoutExpired:
            self.send_json({"error": "Query timed out (120s)"}, 504)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def extract_answer(self, output):
        """Extract the answer text from notebooklm ask_question.py output."""
        lines = output.split("\n")
        capture = False
        answer_lines = []
        for line in lines:
            if "✅ Got answer!" in line or "======" in line and capture:
                if answer_lines:
                    break
            if capture:
                # Skip the divider lines
                if line.strip() == "=" * 60:
                    break
                if line.strip().startswith("Question:"):
                    continue
                if "EXTREMELY IMPORTANT" in line:
                    break
                answer_lines.append(line)
            if "✅ Got answer!" in line:
                capture = True
        return "\n".join(answer_lines).strip()

    def send_cors(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        print(f"  {args[0]}")


if __name__ == "__main__":
    print("=" * 55)
    print("  📚 NotebookLM Proxy Server")
    print(f"  Port: {PORT}")
    print(f"  Notebook: {NOTEBOOK_ID}")
    print("  Press Ctrl+C to stop")
    print("=" * 55)
    server = HTTPServer(("0.0.0.0", PORT), ExplainHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
        server.server_close()
