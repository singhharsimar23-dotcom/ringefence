import importlib.util
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

_spec = importlib.util.spec_from_file_location("fuzz_timesheet", Path(__file__).parent.parent / "fuzz" / "fuzz_timesheet.py")
fuzz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fuzz)

ROW = st.sampled_from(["ada", "noah", "lukas", "x", "", " ada ", "ada,1"]).flatmap(
    lambda c: st.text(max_size=12).map(lambda h: f"{c},{h}"))


@settings(max_examples=300, deadline=None)
@given(st.text(max_size=300))
def test_random_text_never_escapes(text):
    fuzz.check(text)


@settings(max_examples=300, deadline=None)
@given(st.lists(ROW, max_size=8).map(lambda rows: "contractor_id,hours\n" + "\n".join(rows)))
def test_table_shaped_text_never_escapes(text):
    fuzz.check(text)


def test_found_by_fuzzing_stray_cr_and_huge_field_are_rejections():
    import pytest

    from ringfence import inbox
    for text in ("contractor_id,hours\nada,\r0", "contractor_id,hours\nada," + "9" * 200_000):
        with pytest.raises(inbox.TimesheetError):
            inbox.parse_timesheet("kestrel", text)
