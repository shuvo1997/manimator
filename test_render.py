"""
Standalone render pipeline test — runs without the Qt UI.
Tests: code extraction, validation, manimgl subprocess render.
"""
import sys
import traceback
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))


def test_code_extraction():
    from app.core.code_extractor import extract_code_block, ensure_scene_class

    print("\n=== Test: Code Extraction ===")

    # Strategy 1: python fence
    resp1 = '```python\nfrom manimlib import *\n\nclass GeneratedScene(Scene):\n    def construct(self):\n        self.play(Write(Text("Hi")))\n```'
    code = extract_code_block(resp1)
    assert code and "GeneratedScene" in code, "Strategy 1 failed"
    print("  PASS  Strategy 1 (python fence)")

    # Strategy 2: generic fence
    resp2 = '```\nfrom manimlib import *\n\nclass GeneratedScene(Scene):\n    def construct(self):\n        pass\n```'
    code = extract_code_block(resp2)
    assert code and "GeneratedScene" in code, "Strategy 2 failed"
    print("  PASS  Strategy 2 (generic fence)")

    # Strategy 3: raw Python
    resp3 = "Here is the code:\nfrom manimlib import *\n\nclass GeneratedScene(Scene):\n    def construct(self):\n        pass\n\nThat should work!"
    code = extract_code_block(resp3)
    assert code and "GeneratedScene" in code, "Strategy 3 failed"
    assert "That should work" not in code, "Strategy 3 did not trim trailing prose"
    print("  PASS  Strategy 3 (raw Python + prose trimming)")

    # Strategy 4: thinking tags
    resp4 = "<think>I'll write a scene.</think>\nfrom manimlib import *\n\nclass GeneratedScene(Scene):\n    def construct(self):\n        pass"
    code = extract_code_block(resp4)
    assert code and "GeneratedScene" in code, "Strategy 4 (think tags) failed"
    assert "<think>" not in code, "Think tags not stripped"
    print("  PASS  Strategy 4 (think-tag stripping)")

    # ensure_scene_class rename
    code_wrong_name = "from manimlib import *\n\nclass MyScene(Scene):\n    def construct(self):\n        pass"
    fixed = ensure_scene_class(code_wrong_name)
    assert "class GeneratedScene(Scene)" in fixed, "Class rename failed"
    print("  PASS  ensure_scene_class rename")


def test_code_validator():
    from app.core.code_validator import validate_code

    print("\n=== Test: Code Validator ===")

    good_code = """from manimlib import *

class GeneratedScene(Scene):
    def construct(self):
        t = Text("Hello")
        self.play(Write(t))
        self.wait(1)
"""
    result = validate_code(good_code)
    assert result.is_safe, f"Valid code rejected: {result.violations}"
    print("  PASS  Valid code accepted")

    bad_code = """import os
from manimlib import *

class GeneratedScene(Scene):
    def construct(self):
        os.system("rm -rf /")
"""
    result = validate_code(bad_code)
    assert not result.is_safe, "Dangerous code was not rejected"
    print("  PASS  Forbidden import rejected")


def test_render_pipeline():
    from app.core.render_pipeline import RenderPipeline
    import subprocess

    print("\n=== Test: Render Pipeline ===")

    code = """from manimlib import *

class GeneratedScene(Scene):
    def construct(self):
        title = Text("Render Test", font_size=48)
        self.play(Write(title))
        self.wait(0.5)
"""
    pipeline = RenderPipeline()
    scene_file, temp_dir = pipeline.prepare_scene_file(code)
    print(f"  Scene file written: {scene_file}")

    cmd = pipeline.build_command(scene_file, quality="low")
    print(f"  Command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    print(f"  Exit code: {result.returncode}")
    if result.stdout:
        print(f"  stdout (last 5 lines):")
        for line in result.stdout.strip().splitlines()[-5:]:
            print(f"    {line}")
    if result.stderr:
        print(f"  stderr (last 10 lines):")
        for line in result.stderr.strip().splitlines()[-10:]:
            print(f"    {line}")

    if result.returncode != 0:
        raise AssertionError(f"manimgl exited with code {result.returncode}")

    video_path = pipeline.parse_output_path(result.stdout, result.stderr, temp_dir)
    assert video_path and video_path.exists(), f"Video file not found at {video_path}"
    size_kb = video_path.stat().st_size // 1024
    print(f"  PASS  Video rendered: {video_path}  ({size_kb} KB)")


def main():
    failures = []

    for test_fn in [test_code_extraction, test_code_validator, test_render_pipeline]:
        try:
            test_fn()
        except Exception as e:
            print(f"\n  FAIL  {test_fn.__name__}: {e}")
            traceback.print_exc()
            failures.append(test_fn.__name__)

    print("\n" + "=" * 50)
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
