import json
import shutil
import textwrap
from .utils import get_test_id, build_example, run_example


def test_dcl():
    name = f'ckt_{get_test_id()}'
    netlist = textwrap.dedent(f"""\
        .subckt {name} vbias2 vccx
        mp29     v4 vbias2 v2     vccx p w=2.16e-6 m=1 nf=12
        mp33 vbias2 vbias2 vbias1 vccx p w=1.44e-6 m=1 nf=8
        .ends {name}
        """)
    constraints = [
        {"constraint": "PowerPorts", "ports": ["vccx"]}
    ]
    example = build_example(name, netlist, constraints)
    ckt_dir, run_dir = run_example(example, cleanup=False)

    with (run_dir / '1_topology' / '__primitives__.json').open('rt') as fp:
        primitives = json.load(fp)
        for key, _ in primitives.items():
            assert key.startswith('PMOS') or key.startswith('DCL'), f"Incorrect subcircuit identification {key}"

    shutil.rmtree(run_dir)
    shutil.rmtree(ckt_dir)
