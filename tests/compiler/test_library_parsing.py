import pathlib
from align.schema.types import set_context
from align.schema.parser import SpiceParser
from align.schema import constraint


def test_basic_lib():
    parser = SpiceParser()
    align_home = pathlib.Path(__file__).resolve().parent.parent / "files"
    basic_lib_path = align_home / "basic_template.sp"
    with open(basic_lib_path) as f:
        lines = f.read()
    parser.parse(lines)
    user_lib_path = align_home / "user_template.sp"
    with open(user_lib_path) as f:
        lines = f.read()
    parser.parse(lines)
    library = parser.library

    assert len(library.find("DP_PMOS_B").elements) == 2
    assert len(library.find("CASCODED_CMC_PMOS").elements) == 4
    assert len(library.find("INV_B").elements) == 2
    assert len(library) == 78

    assert len(library.find("DP_PMOS_B").constraints) == 4
    dp_const = library.find("DP_PMOS_B").constraints
    with set_context(dp_const):
        x = constraint.SymmetricBlocks(direction="V", pairs=[["M1", "M2"]])
    assert x in dp_const
    assert dp_const[1].constraint == "symmetric_blocks"
    assert dp_const[1].pairs == [["M1", "M2"]]
