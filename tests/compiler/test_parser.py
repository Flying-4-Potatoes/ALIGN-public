import pytest
from align.schema.parser import SpiceParser
from align.compiler.compiler import compiler_input
import pathlib
import os

ALIGN_HOME = pathlib.Path(__file__).resolve().parent.parent.parent

if "ALIGN_HOME" in os.environ:
    assert pathlib.Path(os.environ["ALIGN_HOME"]).resolve() == ALIGN_HOME
else:
    os.environ["ALIGN_HOME"] = str(ALIGN_HOME)

skip_dirs = [
]

examples_dir = ALIGN_HOME / "examples"
assert examples_dir.is_dir()
examples = [
    p
    for p in examples_dir.rglob("*.sp")
    if all(x not in skip_dirs for x in p.relative_to(examples_dir).parts)
]


@pytest.fixture
def get_parser():
    parser = SpiceParser()
    mydir = pathlib.Path(__file__).resolve().parent
    models = mydir.parent.parent / 'pdks' / 'FinFET14nm_Mock_PDK' / 'models.sp'
    with open(models) as f:
        lines = f.read()
    parser.parse(lines)
    return parser


@pytest.mark.parametrize("design", examples)
def test_all_examples(get_parser, design):
    with open(design) as f:
        lines = f.read()
    get_parser.parse(lines)


def test_simple_circuit():
    test_home = pathlib.Path(__file__).resolve().parent.parent
    test_path = test_home / "files" / "test_circuits" / "test2.sp"
    pdk_dir = test_home.parent / "pdks" / "FinFET14nm_Mock_PDK"
    config_path = pathlib.Path(__file__).resolve().parent.parent / "files"
    lib, _ = compiler_input(test_path, "test2", pdk_dir, config_path)
    circuit = lib.find("TEST2")

    assert len(circuit.elements) == 9
    assert len(circuit.nets) == 10
    assert circuit.name == "TEST2"
    assert len(circuit.pins) == 3

    assert (
        circuit.elements[0].name == "MM0"
    )  # can we directly use instance name instead of index?
    assert circuit.elements[0].model == "NMOS_RVT"
    model = lib.find(circuit.elements[0].model)
    assert model.base == "NMOS"
    assert circuit.elements[0].pins == {
        "B": "GND!",
        "D": "VOUT",
        "G": "NET5",
        "S": "GND!",
    }
    assert model.pins == ["D", "G", "S", "B"]
    assert model.parameters == {
        "L": "1",
        "M": "1",
        "NF": "1",
        "NFIN": "1",
        "W": "1",
        "PARALLEL": "1",
        "STACK": "1",
    }
    # TBF: Document base model
    assert model.prefix == ''
    assert circuit.elements[0].parameters == {
        "W": "2.7E-08",
        "L": "2E-08",
        "NFIN": "1",
        "NF": "1",
        "M": "1",
        "PARALLEL": "1",
        "STACK": "1",
    }

    assert circuit.elements[1].name == "MM2"
    assert circuit.elements[1].model == "N"
    assert circuit.elements[1].pins == {
        "D": "VOUT",
        "G": "NET2",
        "S": "NET3",
        "B": "GND!",
    }
    assert circuit.elements[1].parameters == {
        "W": "2.7E-08",
        "L": "2E-08",
        "NFIN": "1",
        "NF": "1",
        "M": "1",
        "PARALLEL": "1",
        "STACK": "1",
    }

    assert circuit.elements[2].name == "MM3"
    assert circuit.elements[2].model == "NFET"
    assert circuit.elements[2].pins == {
        "D": "VOUT",
        "G": "NET3",
        "S": "NET4",
        "B": "GND!",
    }
    assert circuit.elements[2].parameters == {
        "W": "2.7E-08",
        "L": "2E-08",
        "NFIN": "1",
        "NF": "1",
        "M": "1",
        "PARALLEL": "1",
        "STACK": "1",
    }

    assert circuit.elements[3].name == "RR0"
    assert circuit.elements[3].model == "RES"
    model = lib.find(circuit.elements[3].model)
    assert model.base == None  # Using base model
    assert model.pins == ["PLUS", "MINUS"]
    assert model.parameters == {"VALUE": "0", 'PARALLEL': '1', 'STACK': '1'}
    assert model.prefix == "R"
    assert circuit.elements[3].pins == {"PLUS": "VBIAS", "MINUS": "NET5"}
    assert circuit.elements[3].parameters == {"VALUE": "5000", 'PARALLEL': '1', 'STACK': '1'}

    assert circuit.elements[4].name == "CC0"
    model = lib.find(circuit.elements[4].model)
    assert circuit.elements[4].model == "CAP"
    assert model.base == None
    assert circuit.elements[4].pins == {"PLUS": "VIN", "MINUS": "NET5"}
    assert circuit.elements[4].parameters == {
        "VALUE": "1.0000000000000002E-14", 'PARALLEL': '1', 'STACK': '1'
    }  # TBF: remove multiple zeros

    assert circuit.elements[5].name == "LL0"
    assert circuit.elements[5].model == "IND"
    model = lib.find(circuit.elements[5].model)
    assert model.base == None
    assert circuit.elements[5].pins == {"PLUS": "VDD!", "MINUS": "VOUT"}
    assert circuit.elements[5].parameters == {
        "VALUE": "0.002", 'PARALLEL': '1', 'STACK': '1'
    }  # TBF: change to scientific nomenclature?

    assert circuit.elements[6].name == "RR1"
    assert circuit.elements[6].model == "RESISTOR"
    model = lib.find(circuit.elements[6].model)
    assert model.name == "RESISTOR"
    assert model.pins == ["PLUS", "MINUS"]
    assert model.parameters == {"R": "1", "VALUE": "0", 'PARALLEL': '1', 'STACK': '1'}
    assert circuit.elements[6].pins == {"PLUS": "VBIAS", "MINUS": "NET6"}
    assert circuit.elements[6].parameters == {"R": "5000", "VALUE": "0", 'PARALLEL': '1', 'STACK': '1'}

    assert circuit.elements[7].name == "CC1"
    assert circuit.elements[7].model == "CAPACITOR"
    model = lib.find(circuit.elements[7].model)
    assert model.name == "CAPACITOR"
    assert model.pins == ["PLUS", "MINUS"]
    assert model.parameters == {"C": "1", "VALUE": "0", 'PARALLEL': '1', 'STACK': '1'}
    assert circuit.elements[7].pins == {"PLUS": "VIN", "MINUS": "NET6"}
    assert circuit.elements[7].parameters == {
        "C": "1.0000000000000002E-14",
        "VALUE": "0", 'PARALLEL': '1', 'STACK': '1'
    }

    assert circuit.elements[8].name == "LL1"
    assert circuit.elements[8].model == "INDUCTOR"
    model = lib.find(circuit.elements[8].model)
    assert model.name == "INDUCTOR"
    assert model.pins == ["PLUS", "MINUS"]
    assert model.parameters == {"IND": "1", "VALUE": "0", 'PARALLEL': '1', 'STACK': '1'}
    assert circuit.elements[8].pins == {"PLUS": "VDD!", "MINUS": "NET6"}
    assert circuit.elements[8].parameters == {"IND": "0.002", "VALUE": "0", 'PARALLEL': '1', 'STACK': '1'}
