"""Head-less Streamlit test: renders the app and exercises the controls."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def render():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def check(at, label):
    if at.exception:
        for exc in at.exception:
            print(f"[{label}] EXCEPTION: {exc.value}")
            import traceback

            traceback.print_exception(type=exc.value, value=exc.value, tb=exc.__traceback__)
        raise SystemExit(1)
    blanks = 0
    for md in at.markdown:
        value = md.value
        if "<div" in value:
            for line in value.split("\n")[1:]:
                if line.strip() == "":
                    blanks += 1
    if blanks:
        print(f"[{label}] WARNING: {blanks} blank line(s) inside a raw HTML block")
    print(f"[{label}] ok - {len(at.markdown)} markdown blocks, {len(at.dataframe)} dataframes")


def body_text(at):
    return "\n".join(md.value for md in at.markdown)


def has_result(at):
    """True when a pipeline result (not the idle placeholder) is on screen."""
    text = body_text(at)
    return 'class="mh-trace"' in text and 'class="mh-idle"' not in text


def run_button(at):
    for btn in at.button:
        if btn.label == "Run pipeline":
            return btn
    raise SystemExit("Run pipeline button not found")


if __name__ == "__main__":
    at = render()
    check(at, "initial render")

    # the pipeline must NOT run on its own
    if has_result(at):
        print("[initial render] FAIL - a result was rendered without pressing Run pipeline")
        raise SystemExit(1)
    if 'class="mh-idle"' not in body_text(at):
        print("[initial render] FAIL - the idle placeholder is missing")
        raise SystemExit(1)
    print("[initial render] ok - nothing ran, idle placeholder shown")

    # pressing the button runs it
    run_button(at).click().run()
    check(at, "after Run pipeline")
    if not has_result(at):
        print("[after Run pipeline] FAIL - no result after pressing the button")
        raise SystemExit(1)
    print("[after Run pipeline] ok - the trace is on screen")

    # changing a setting must clear the result and must NOT re-run
    at.slider[0].set_value(1).run()
    check(at, "k=1")
    if has_result(at):
        print("[k=1] FAIL - the old result was still on screen")
        raise SystemExit(1)
    if "Ready to run again" not in body_text(at):
        print("[k=1] FAIL - the 'settings changed' notice is missing")
        raise SystemExit(1)
    print("[k=1] ok - the result was cleared and nothing re-ran automatically")

    # switch to the Chroma RAG mode and a small k
    at.radio[0].set_value("Chroma RAG").run()
    check(at, "chroma mode")
    at.slider[0].set_value(1).run()
    check(at, "k=1 chroma")
    run_button(at).click().run()
    check(at, "chroma k=1 run")
    if not has_result(at):
        print("[chroma k=1 run] FAIL - no result after pressing the button")
        raise SystemExit(1)

    # every scenario - each entry differs from the one before it, so every
    # selection is a real change that must clear the result without running
    for key in ["s2", "s3", "s4", "s5", "custom", "s1"]:
        at.selectbox[0].set_value(key).run()
        check(at, f"scenario {key}")
        if has_result(at):
            print(f"[scenario {key}] FAIL - selecting a scenario ran the pipeline")
            raise SystemExit(1)
        run_button(at).click().run()
        check(at, f"scenario {key} run")
        if not has_result(at):
            print(f"[scenario {key} run] FAIL - no result after pressing the button")
            raise SystemExit(1)
    print("[scenarios] ok - no scenario auto-ran, every explicit run produced a result")

    # toggles
    at.toggle[0].set_value(True).run()
    check(at, "hallucination on")
    run_button(at).click().run()
    check(at, "hallucination on run")
    if not has_result(at):
        print("[hallucination on run] FAIL - no result after pressing the button")
        raise SystemExit(1)

    # a hand-typed custom question must be planned and answered
    at = render()
    at.selectbox[0].set_value("custom").run()
    at.text_input[0].set_value("What is the capital of France?").run()
    check(at, "typed custom question")
    run_button(at).click().run()
    check(at, "typed custom question run")
    text = body_text(at)
    if 'class="mh-final"' not in text:
        print("[typed custom question run] FAIL - no final answer block")
        raise SystemExit(1)
    if "Paris" not in text:
        print("[typed custom question run] FAIL - the answer 'Paris' is not on screen")
        raise SystemExit(1)
    if "UNKNOWN" in text:
        print("[typed custom question run] FAIL - a typed question fell back to UNKNOWN")
        raise SystemExit(1)
    print("[typed custom question run] ok - the typed question was answered")

    # the persisted index must be visible in the sidebar
    text = body_text(at)
    if "chroma_db" not in text:
        print("[index panel] FAIL - the index store path is not shown")
        raise SystemExit(1)
    if not any(btn.label == "Rebuild vector index" for btn in at.button):
        print("[index panel] FAIL - the 'Rebuild vector index' button is missing")
        raise SystemExit(1)
    print("[index panel] ok - the store path and the rebuild control are on screen")

    print("ALL APP TESTS PASSED")
